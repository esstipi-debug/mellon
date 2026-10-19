import numpy as np
import pandas as pd
import pytest

from fdekit.probe.contracts import ContractCheck, check_payload, retry_idempotency_check, timezone_audit
from fdekit.probe.edi import parse_x12, smoke_report, validate_transaction
from fdekit.sim import SimConfig, capacity_check, little, mm_c_wait, run_sim, sizing_sweep
from fdekit.spc.xmr import (
    MAX_BASELINE_FLAGGED_FRACTION,
    baseline_stability,
    compute_limits,
    degradation_alarm,
    nelson_rules,
)


# ------------------------------------------------------------------- SPC


def test_limites_requieren_linea_base_minima():
    with pytest.raises(ValueError, match="al menos 8"):
        compute_limits([1, 2, 3])


def test_tasa_de_falsa_alarma_es_baja():
    """Un proceso estable dispara la regla 1 muy rara vez — ese es el punto del
    grafico de control frente a un umbral fijo. La tasa teorica es 0.27% por
    punto; con sigma estimado de rangos moviles sube un poco. Sobre 2% el equipo
    aprende a ignorar la alarma en tres semanas."""
    rng = np.random.default_rng(42)
    lim = compute_limits(rng.normal(100, 5, 300))

    puntos = alarmas = 0
    for _ in range(30):
        m = rng.normal(100, 5, 30)
        puntos += len(m)
        v = nelson_rules(m, lim)
        alarmas += 0 if v.empty else int((v["rule"] == 1).sum())

    assert alarmas / puntos < 0.02


def test_regla_1_detecta_punto_fuera_de_control():
    base = [100] * 10 + [101, 99, 100, 102, 98]
    lim = compute_limits(base)
    viol = nelson_rules([100, 100, 400], lim)
    assert 1 in set(viol["rule"])


def test_regla_2_detecta_corrimiento_sostenido():
    rng = np.random.default_rng(2)
    lim = compute_limits(rng.normal(100, 5, 40))
    viol = nelson_rules([104] * 12, lim)
    assert 2 in set(viol["rule"])


def test_alarma_distingue_degradacion_de_mejora():
    rng = np.random.default_rng(3)
    base = rng.normal(100, 5, 40)

    peor = degradation_alarm(base, [115] * 15, direction="lower_is_better")
    assert "DEGRADACION" in peor["verdict"]

    mejor = degradation_alarm(base, [85] * 15, direction="lower_is_better")
    assert "DEGRADACION" not in mejor["verdict"]


def test_limites_congelados_no_se_recalculan():
    """El error mas comun al implementar SPC: recalcular limites sobre la
    ventana de monitoreo hace que la degradacion se vuelva la nueva normalidad."""
    rng = np.random.default_rng(4)
    base = rng.normal(100, 5, 40)
    r = degradation_alarm(base, [120] * 15, direction="lower_is_better")
    assert r["limits"]["center"] == pytest.approx(float(np.mean(base)), abs=1e-3)
    assert r["shift_sigmas"] > 3


# Linea base estable: el chequeo que `degradation_alarm` corre antes de fijar limites.
# Una ola en la linea base hace que los limites describan la ola y no el proceso.


def test_linea_base_estable_no_se_niega():
    """Un proceso estable pasa el chequeo y sus limites se fijan. El criterio es la
    fraccion de puntos marcados, no la presencia de una regla: con 30 puntos alguna
    regla 1-3 dispara en el 14% de los graficos de un proceso estable."""
    rng = np.random.default_rng(5)
    r = degradation_alarm(rng.normal(100, 5, 30), [120] * 15, direction="lower_is_better")
    assert r["baseline_stable"] is True
    assert r["limits"] is not None
    assert "DEGRADACION" in r["verdict"]


def test_un_punto_suelto_no_invalida_la_linea_base():
    rng = np.random.default_rng(6)
    base = rng.normal(100, 5, 30)
    base[10] = 140  # un punto a 8 sigma: una senal que se investiga, no una ola
    assert baseline_stability(base)["stable"] is True


@pytest.mark.parametrize("forma", ["escalon", "tendencia"])
def test_escalon_y_tendencia_en_la_linea_base_se_niegan(forma):
    rng = np.random.default_rng(8)
    if forma == "escalon":
        base = np.r_[rng.normal(60, 5, 15), rng.normal(80, 5, 15)]
    else:
        base = np.linspace(50, 90, 30) + rng.normal(0, 4, 30)
    r = degradation_alarm(base, [85] * 15, direction="lower_is_better")
    assert r["limits"] is None
    assert r["baseline_fraction_flagged"] > MAX_BASELINE_FLAGGED_FRACTION
    assert r["verdict"].startswith("SIN LIMITES")
    assert "DEGRADACION" not in r["verdict"]


def test_linea_base_con_la_ola_del_cd_se_niega():
    """La linea base que usaba la demo: medianas de 30 bloques de pedidos de un dia,
    con la ola de liberacion adentro. Sus limites salian de la ola y el monitoreo se
    juzgaba contra ella. Ahora el grafico se niega a fijarlos."""
    from fdekit.processmining import EventLog
    from fdekit.synth import DCConfig, generate_dc

    good = generate_dc(DCConfig(seed=57, slotting="abc", dim_error_rate=0.04))
    ciclo = EventLog(good.events).case_durations()["cycle_time_s"].to_numpy() / 60
    bloques = [float(np.median(c)) for c in np.array_split(ciclo, 30)]

    r = degradation_alarm(bloques, [200] * 20, direction="lower_is_better")
    assert r["limits"] is None
    assert r["baseline_fraction_flagged"] > MAX_BASELINE_FLAGGED_FRACTION
    assert r["verdict"].startswith("SIN LIMITES")


def test_la_linea_base_estable_casi_nunca_se_niega():
    """Tasa de falsos rechazos sobre procesos estables. Medida en 4000 corridas con
    30 puntos i.i.d.: ninguna supero el umbral. El test deja margen para el muestreo."""
    rng = np.random.default_rng(7)
    negadas = sum(not baseline_stability(rng.normal(100, 5, 30))["stable"] for _ in range(300))
    assert negadas / 300 < 0.02


def test_el_demo_se_juzga_contra_una_linea_base_estable(findings):
    """Lo que muestra la demo tiene que ser un veredicto calculado, no una negativa.
    Su linea base son dias sanos, su monitoreo son dias degradados, y la alarma sale
    de esa diferencia y no de una ola dentro de la linea base."""
    alarm = findings["degradation_alarm"]
    assert alarm["baseline_stable"] is True
    assert alarm["limits"] is not None
    assert alarm["verdict"].startswith("DEGRADACION")


def test_cli_spc_no_dibuja_limites_sobre_una_linea_base_con_ola(tmp_path, capsys):
    """El CLI imprime la negativa y no dibuja el grafico: un XmR con limites que el
    propio chequeo declara invalidos no es un diagnostico."""
    from fdekit.cli import main

    serie = np.r_[np.linspace(7, 140, 15), np.linspace(140, 54, 15), [200.0] * 10]
    csv, png = tmp_path / "serie.csv", tmp_path / "xmr.png"
    pd.DataFrame({"minutos": serie}).to_csv(csv, index=False)

    assert main(["spc", "--values", str(csv), "--baseline", "30", "--plot", str(png)]) == 0
    assert not png.exists()
    salida = capsys.readouterr()
    assert '"verdict": "SIN LIMITES' in salida.out
    assert "sin grafico" in salida.err


def test_cli_spc_con_linea_base_estable_dibuja_el_grafico(tmp_path, capsys):
    from fdekit.cli import main

    rng = np.random.default_rng(9)
    serie = np.r_[rng.normal(100, 5, 30), rng.normal(120, 5, 10)]
    csv, png = tmp_path / "serie.csv", tmp_path / "xmr.png"
    pd.DataFrame({"minutos": serie}).to_csv(csv, index=False)

    assert main(["spc", "--values", str(csv), "--baseline", "30", "--plot", str(png)]) == 0
    assert png.exists()
    assert '"baseline_stable": true' in capsys.readouterr().out


# ------------------------------------------------------------------- SIM


def test_ley_de_little():
    assert little(throughput=10, cycle_time=2)["wip"] == 20
    assert little(wip=20, cycle_time=2)["throughput"] == 10
    with pytest.raises(ValueError):
        little(wip=1, throughput=2, cycle_time=3)


def test_capacidad_declara_no_da_cuando_la_demanda_supera():
    r = capacity_check(demand_per_hour=500, service_time_s=120, servers=5)
    assert r["utilization"] > 1
    assert "no da" in r["verdict"]


def test_mmc_inestable_cuando_rho_supera_1():
    assert mm_c_wait(arrival_rate=10, service_rate=1, servers=5)["stable"] is False


def test_mmc_la_espera_crece_con_la_utilizacion():
    poco = mm_c_wait(0.5, 1, 3)["wq_s"]
    mucho = mm_c_wait(2.7, 1, 3)["wq_s"]
    assert mucho > poco


def test_simulacion_mas_pickers_reduce_ciclo():
    cfg = SimConfig(n_pickers=4, n_packers=6, arrival_rate_per_h=40, horizon_h=3.0, warmup_h=0.3)
    pocos = run_sim(cfg)
    muchos = run_sim(SimConfig(**{**cfg.__dict__, "n_pickers": 10}))
    assert muchos.mean_cycle_min < pocos.mean_cycle_min
    assert muchos.picker_utilization < pocos.picker_utilization


def test_barrido_de_dimensionamiento_es_monotono():
    cfg = SimConfig(n_pickers=6, n_packers=8, arrival_rate_per_h=45, horizon_h=3.0, warmup_h=0.3)
    sweep = sizing_sweep(cfg, range(4, 9), replications=2)
    assert sweep["mean_cycle_min"].is_monotonic_decreasing
    assert sweep["picker_util"].is_monotonic_decreasing


# ------------------------------------------------------------------ PROBE


ISA = (
    "ISA*00*          *00*          *ZZ*FDEKIT         *ZZ*CLIENTEWMS     "
    "*260302*0700*U*00401*000000001*0*P*:~"
)


def _msg(st, body, se_n=None, ctrl="0001"):
    n = se_n if se_n is not None else len(body) + 2
    return (
        ISA
        + f"GS*OW*A*B*20260302*0700*{ctrl}*X*004010~"
        + f"ST*{st}*{ctrl}~"
        + "".join(s + "~" for s in body)
        + f"SE*{n}*{ctrl}~GE*1*{ctrl}~IEA*1*000000001~"
    )


def test_isa_define_los_separadores():
    assert len(ISA) == 106
    msg = parse_x12(_msg("940", ["W05*N*SO1"]))
    assert msg.element_sep == "*" and msg.seg_term == "~" and msg.sub_sep == ":"


def test_separadores_no_estandar():
    """El socio comercial que usa | y \\n existe, y rompe a todo el que asumio
    asteriscos."""
    raw = ISA.replace("*", "|").replace("~", "\n")
    msg = parse_x12(raw + "GS|OW|A|B|20260302|0700|1|X|004010\nST|940|1\nW05|N|SO1\nSE|3|1\n")
    assert msg.element_sep == "|"
    assert msg.transaction_sets() == ["940"]


def test_940_valido_no_tiene_errores():
    body = ["W05*N*SO12345", "N1*ST*CLIENTE", "W01*10*EA*S1", "W76*10*120*LB*45*CF"]
    hallazgos = validate_transaction(parse_x12(_msg("940", body)))
    assert [h for h in hallazgos if h.severity == "ERROR"] == []


def test_falta_segmento_obligatorio():
    hallazgos = validate_transaction(parse_x12(_msg("940", ["W05*N*SO1", "N1*ST*C"])))
    codes = {h.code for h in hallazgos if h.severity == "ERROR"}
    assert "SEG001" in codes


def test_conteo_se01_desalineado():
    body = ["W05*N*SO1", "N1*ST*C", "W01*10*EA*S1", "W76*10*120*LB*45*CF"]
    hallazgos = validate_transaction(parse_x12(_msg("940", body, se_n=99)))
    assert "TRX002" in {h.code for h in hallazgos}


def test_ctt_desalineado_en_856():
    body = ["BSN*00*ASN1*20260302*0700", "HL*1**S", "HL*2*1*O", "CTT*7"]
    hallazgos = validate_transaction(parse_x12(_msg("856", body)))
    assert "SEG002" in {h.code for h in hallazgos}


def test_fecha_yymmdd_genera_advertencia():
    body = ["W06*N*SO1*260302", "N1*ST*C", "W12*CC*1*1*EA*S1", "W03*1"]
    hallazgos = validate_transaction(parse_x12(_msg("945", body)))
    assert "FMT001" in {h.code for h in hallazgos}


def test_smoke_report_ordena_errores_primero():
    r = smoke_report({"ok.edi": _msg("940", ["W05*N*S", "N1*ST*C", "W01*1*EA*S", "W76*1*1*LB*1*CF"]),
                      "roto.edi": _msg("940", ["W05*N*S"])})
    assert r.iloc[0]["severity"] == "ERROR"


def test_contrato_detecta_tipo_enum_y_timestamp_naive():
    c = ContractCheck(
        name="t",
        required={"id": str, "n": float, "when": str, "status": str},
        enums={"status": ("A", "B")},
        datetime_fields=("when",),
    )
    h = check_payload({"id": 1, "n": 2.0, "when": "2026-03-02T10:00:00", "status": "Z"}, c)
    detalles = " ".join(x["detail"] for x in h)
    assert "se esperaba str" in detalles
    assert "sin zona horaria" in detalles
    assert "fuera del enum" in detalles


def test_contrato_acepta_timestamp_con_offset():
    c = ContractCheck(name="t", required={"when": str}, datetime_fields=("when",))
    h = check_payload({"when": "2026-03-02T10:00:00-03:00"}, c)
    assert not [x for x in h if x["severity"] == "ERROR"]


def test_timezone_audit_marca_naive():
    df = pd.DataFrame({"ts": pd.to_datetime(["2026-03-02 08:00", "2026-03-02 09:00"])})
    r = timezone_audit(df, ["ts"])
    assert r.loc[0, "issue"] == "ERROR"
    assert "naive" in r.loc[0, "detail"]


def test_idempotencia_detecta_duplicados():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    r = retry_idempotency_check(df, ["a", "b"])
    assert r["duplicate_rows"] == 2
    assert "no es idempotente" in r["verdict"]


def test_calibrate_from_log_saca_los_parametros_del_log_real():
    """Su propio docstring dice que sin este paso el simulador es ciencia
    ficcion, y no tenia ningun test. La tasa de llegada y el horizonte se
    derivan del log; los tiempos de servicio se reconstruyen desde el recurso."""
    from fdekit.processmining import EventLog
    from fdekit.sim import calibrate_from_log
    from fdekit.synth import DCConfig, generate_dc

    dc = generate_dc(DCConfig(seed=4, n_orders=300, n_pickers=5, n_packers=6))
    log = EventLog(dc.events)
    cfg = calibrate_from_log(log, n_pickers=5, n_packers=6)

    assert (cfg.n_pickers, cfg.n_packers) == (5, 6)
    cases = log.case_durations()
    span_h = (cases["end"].max() - cases["start"].min()).total_seconds() / 3600
    assert cfg.arrival_rate_per_h == pytest.approx(log.n_cases / span_h, rel=0.02)
    assert cfg.horizon_h == pytest.approx(span_h, rel=0.02)
    # Tiempos de servicio plausibles, no los defaults de la dataclass.
    assert 30 < cfg.pick_time_median_s < 2000
    assert 0.1 <= cfg.pick_time_sigma <= 1.2


def test_calibrate_from_log_cae_a_los_defaults_sin_recursos():
    """Un log sin columna de recurso no puede reconstruir el tiempo de servicio.
    Cae al fallback en vez de reventar, porque el resto de la calibracion —tasa
    de llegada y horizonte— sigue siendo util."""
    import pandas as pd

    from fdekit.processmining import EventLog
    from fdekit.sim import calibrate_from_log

    t0 = pd.Timestamp("2026-08-01 08:00")
    df = pd.DataFrame([
        {"case_id": f"o{i}", "activity": a, "timestamp": t0 + pd.Timedelta(minutes=i * 5 + j)}
        for i in range(20) for j, a in enumerate(("ORDER_RELEASED", "PICK", "SHIP"))
    ])
    cfg = calibrate_from_log(EventLog(df), n_pickers=3, n_packers=2)
    assert cfg.pick_time_median_s == 300.0  # el fallback declarado
    assert cfg.arrival_rate_per_h > 0
