import numpy as np
import pandas as pd
import pytest

from fdekit.probe.contracts import ContractCheck, check_payload, retry_idempotency_check, timezone_audit
from fdekit.probe.edi import parse_x12, smoke_report, validate_transaction
from fdekit.sim import SimConfig, capacity_check, little, mm_c_wait, run_sim, sizing_sweep
from fdekit.spc.xmr import compute_limits, degradation_alarm, nelson_rules


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
