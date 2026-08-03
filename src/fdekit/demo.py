"""Diagnostico completo punta a punta sobre el CD sintetico.

Es la demo que se muestra: en un comando, del log crudo al A3 con numeros. Cada
seccion corresponde a una de las nueve herramientas, en el orden en que se usan
en un despliegue real.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .a3 import build_a3_from_findings
from .baseline import BaselineSpec, diff_in_diff, parallel_trends_check, pre_post
from .baseline import icc_from_log, required_days, sd_from_log
from .dataquality import audit_master, audit_summary, link_defects_to_rework, sampling_plan, stratified_sample
from .gemba import GembaSession, Observation
from .layout import Layout
from .probe import ContractCheck, check_payload, retry_idempotency_check, timezone_audit
from .probe.edi import smoke_report
from .processmining import (
    EventLog,
    activity_durations,
    bottlenecks,
    conformance,
    pareto_coverage,
    rework_summary,
    to_mermaid,
    variants,
)
from .sim import calibrate_from_log, sizing_sweep
from .spc import compute_limits, degradation_alarm, plot_xmr
from .standardwork import JobBreakdown, runbook_template
from .synth import DCConfig, generate_dc
from .timestudy.cycles import cycle_time_stats, operator_variation, standard_work_gap, takt_analysis
from .timestudy.spaghetti import plot_heatmap, plot_spaghetti, slotting_opportunity, travel_stats

# El flujo tal como lo describe el cliente en el kickoff. Siempre es mas limpio
# que la realidad — esa brecha es el primer hallazgo del proyecto.
DECLARED_FLOW = ["ORDER_RELEASED", "PICK", "CONSOLIDATE", "PACK", "QC", "SHIP"]


def _edi_envelope(st_code: str, body: list[str], ctrl: str, se_count: int | None = None) -> str:
    isa = (
        "ISA*00*          *00*          *ZZ*FDEKIT         *ZZ*CLIENTEWMS     "
        "*260302*0700*U*00401*000000001*0*P*:~"
    )
    assert len(isa) == 106, f"ISA mal formado: {len(isa)} chars"
    gs = f"GS*OW*FDEKIT*CLIENTEWMS*20260302*0700*{ctrl}*X*004010~"
    st = f"ST*{st_code}*{ctrl}~"
    n = se_count if se_count is not None else len(body) + 2
    se = f"SE*{n}*{ctrl}~"
    return isa + gs + st + "".join(s + "~" for s in body) + se + f"GE*1*{ctrl}~" + "IEA*1*000000001~"


def _sample_edi() -> dict[str, str]:
    ok_940 = _edi_envelope(
        "940",
        ["W05*N*SO12345", "N1*ST*CLIENTE SPA*92*000123", "W01*10*EA*S00042", "W76*10*120*LB*45*CF"],
        "0001",
    )
    bad_945 = _edi_envelope(
        "945",
        ["W06*N*SO12345*260302", "N1*ST*CLIENTE SPA", "W12*CC*10*10*EA*S00042"],
        "0002",
        se_count=9,  # declara 9, trae 5, y falta W03
    )
    bad_856 = _edi_envelope(
        "856",
        ["BSN*00*ASN001*20260302*0700", "HL*1**S", "HL*2*1*O", "CTT*3"],
        "0003",
    )
    return {"940_ok.edi": ok_940, "945_roto.edi": bad_945, "856_ctt_desalineado.edi": bad_856}


def _json_safe(obj):
    """Convierte NaN/Inf a null antes de serializar.

    `hallazgos.json` salia con `NaN` literal —que JSON no admite— porque las
    observaciones de gemba sin cuantificar llevan `duration_s=None` y pandas las
    vuelve NaN al pasar por un DataFrame. Python lo escribe igual y lo relee
    igual, asi que el kit no se enteraba; cualquier parser estricto de afuera si.

    El acompanante es `allow_nan=False` en el `dumps`: convertir aca y prohibir
    alla significa que si en el futuro se cuela un no-finito por otro camino,
    el demo revienta en vez de escribir un archivo invalido en silencio.
    """
    import math

    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, np.floating):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def _chunk_medians(values: pd.Series, n_chunks: int) -> list[float]:
    v = np.asarray(values, float)
    return [float(np.median(c)) for c in np.array_split(v, n_chunks) if len(c)]


def _gemba_demo(out: Path) -> dict:
    s = GembaSession(out / "gemba_turno_1.jsonl", site="CD Pudahuel", observer="FDE")
    s.add(
        Observation(
            area="Picking pasillo 7",
            activity="Buscar SKU no encontrado en ubicacion",
            waste_type="MOVIMIENTO",
            description="El WMS manda a una ubicacion vacia; el picker recorre el pasillo buscando.",
            duration_s=75,
            frequency_per_shift=38,
            # Ya esta en el log como PICK_EXCEPTION_LOCATION: no suma a L1.
            in_event_log=True,
            shift="manana",
            operator_quote="Cuando no esta, me acuerdo donde suele estar. El sistema no.",
            five_whys=[
                "La ubicacion del maestro esta vencida",
                "Se movio el SKU en un reslotting y no se actualizo",
                "El reslotting se hizo en planilla, fuera del WMS",
                "No hay proceso de cierre del reslotting",
                "Nadie mide cuantas ubicaciones estan mal",
            ],
            root_cause="Reslotting fuera del sistema, sin cierre ni verificacion",
            countermeasure_idea="Ciclo de conteo de ubicaciones + bloquear reslotting fuera del WMS",
        )
    )
    s.add(
        Observation(
            area="Packing",
            activity="Rehacer carton por dimensiones erradas",
            waste_type="DEFECTO",
            description="El carton sugerido no cierra; se rehace con carton mayor.",
            duration_s=190,
            frequency_per_shift=26,
            # Ya esta en el log como CARTON_REWORK: no suma a L1.
            in_event_log=True,
            shift="manana",
            operator_quote="El sistema siempre me manda la caja chica para estos.",
            root_cause="Dimensiones del maestro no corresponden al producto fisico",
            countermeasure_idea="Auditoria y correccion del maestro, priorizando clase A",
        )
    )
    s.add(
        Observation(
            area="Liberacion de olas",
            activity="Espera de pedidos liberados sin picker disponible",
            waste_type="ESPERA",
            description="La ola de las 10:00 libera 400 pedidos con 9 pickers en piso.",
            duration_s=430,
            frequency_per_shift=180,
            # Ya esta en el log: es la espera de la transicion dominante
            # ORDER_RELEASED -> PICK, que `bottlenecks` cuantifica aparte. Es la
            # observacion mas grande del Pareto y la que mas dano haria sumada
            # dos veces.
            in_event_log=True,
            shift="manana",
            root_cause="Politica de liberacion por lote grande, no nivelada contra capacidad",
            countermeasure_idea="Nivelar liberacion (heijunka) contra dotacion real del turno",
        )
    )
    s.add(
        Observation(
            area="Picking — inicio de ola",
            activity="Buscar carro de picking disponible",
            waste_type="MOVIMIENTO",
            description=(
                "Al liberarse la ola el picker recorre packing y recepcion buscando "
                "un carro libre; los carros no tienen posicion asignada."
            ),
            duration_s=150,
            frequency_per_shift=22,
            # NO deja rastro en el WMS: no hay transaccion que emitir por buscar
            # un carro. Es el unico tipo de hallazgo que gemba aporta a L1, y la
            # razon por la que la herramienta 1 existe teniendo el log.
            in_event_log=False,
            shift="manana",
            operator_quote="El carro lo encuentro, pero primero doy la vuelta entera.",
            root_cause="Los carros no tienen ubicacion de retorno definida",
            countermeasure_idea="Zona de carros marcada en piso + retorno al final de cada ola",
        )
    )
    s.add(
        Observation(
            area="Recepcion",
            activity="Doble digitacion de guia",
            waste_type="SOBREPROCESO",
            description="Se digita en el WMS y despues en una planilla de control paralela.",
            in_event_log=False,
            shift="tarde",
        )
    )
    (out / "gemba_checklist.md").write_text(s.checklist(), encoding="utf-8")
    return {
        "observations": len(s),
        "pareto": s.pareto().to_dict("records"),
        "unquantified": s.unquantified().to_dict("records"),
        # Lo que efectivamente entra a L1: solo lo cuantificado Y declarado
        # fuera del log. El resto del Pareto se discute con el supervisor pero
        # no se cobra, porque ya lo cuenta `timestudy`.
        "value_input": s.value_input(),
    }


def run_full_diagnosis(outdir: str | Path = "out", seed: int = 7, quiet: bool = False) -> dict:
    """Corre las nueve herramientas y escribe los artefactos en `outdir`."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    lay = Layout()

    def say(msg: str):
        if not quiet:
            print(msg)

    # ---------------------------------------------------------- 0. datos
    say("[0/9] generando CD sintetico...")
    dc = generate_dc(DCConfig(seed=seed, layout=lay))
    log = EventLog(dc.events)
    dc.events.to_csv(out / "event_log.csv", index=False)
    dc.master.to_csv(out / "master_wms.csv", index=False)
    say(f"      {dc.summary()}")

    results: dict = {"dataset": dc.summary()}

    # ---------------------------------------------------------- 1. gemba
    say("[1/9] gemba estructurado...")
    results["gemba"] = _gemba_demo(out)

    # ------------------------------------------------- 2. estudio de tiempos
    say("[2/9] estudio de tiempos y espagueti...")
    results["cycle_times"] = cycle_time_stats(log)
    results["takt"] = takt_analysis(log)
    results["travel"] = travel_stats(log, lay)
    results["slotting"] = slotting_opportunity(log, dc.master, lay)
    results["operator_variation"] = operator_variation(log, "PICK", "PICK-").to_dict("records")
    results["standard_work_gap"] = standard_work_gap(log, "PICK", "PICK-")
    plot_spaghetti(log, lay, n_orders=30, path=str(out / "spaghetti.png"))
    plot_heatmap(log, lay, path=str(out / "heatmap.png"))

    # ------------------------------------------------- 3. process mining
    say("[3/9] mineria de procesos...")
    conf = conformance(log, DECLARED_FLOW)
    results["conformance"] = conf
    results["pareto_coverage"] = pareto_coverage(log)
    results["variants"] = variants(log, top=10, collapse_repeats=True).to_dict("records")
    bn = bottlenecks(log, top=8)
    results["bottlenecks"] = bn.to_dict("records")
    results["activity_durations"] = activity_durations(log).to_dict("records")
    results["rework"] = rework_summary(log).to_dict("records")
    (out / "dfg.mmd").write_text(to_mermaid(log, min_freq_pct=0.5), encoding="utf-8")

    # ------------------------------------------------- 4. datos maestros
    say("[4/9] auditoria de datos maestros...")
    plan = sampling_plan(len(dc.master), margin_of_error=0.04, expected_defect_rate=0.20)
    sample = stratified_sample(dc.master, plan["sample_size"], seed=seed)
    measured = dc.truth[dc.truth["sku_id"].isin(sample["sku_id"])]  # la medicion fisica en terreno
    audit = audit_master(sample, measured)
    # La poblacion por clase deshace la sobre-representacion deliberada de la
    # clase A que hace `stratified_sample`. Sin esto la tasa reportada es la de
    # la muestra sesgada y no la del catalogo.
    dq = audit_summary(
        audit,
        population=len(dc.master),
        population_by_class=dc.master["abc_class"].value_counts().to_dict(),
    )
    link = link_defects_to_rework(audit, dc.events, dc.order_lines)
    results["sampling_plan"] = plan
    results["data_quality"] = dq
    results["defects_to_rework"] = link
    audit.to_csv(out / "auditoria_maestros.csv", index=False)

    # ------------------------------------------------- 5. simulacion
    say("[5/9] simulacion y dimensionamiento...")
    simcfg = calibrate_from_log(log, dc.config.n_pickers, dc.config.n_packers)
    results["sim_config_calibrated"] = simcfg.__dict__
    sweep = sizing_sweep(simcfg, range(max(2, simcfg.n_pickers - 3), simcfg.n_pickers + 5), replications=3)
    results["sizing_sweep"] = sweep.to_dict("records")
    sweep.to_csv(out / "dimensionamiento.csv", index=False)

    # ------------------------------------------------- 6. linea base
    say("[6/9] linea base y contrafactual...")
    spec = BaselineSpec(
        metric_name="Tiempo de ciclo del pedido (mediana)",
        metric_definition="median(ts(SHIP) - ts(ORDER_RELEASED)) por pedido, en minutos",
        data_source="wms.task_events",
        unit_of_analysis="pedido",
        direction="lower_is_better",
        target_change_pct=-15.0,
        baseline_window_days=21,
        control_group="Zona B (pasillos 7-12), sin cambio de slotting",
        known_confounders=("peak de fin de mes", "contratacion de temporada", "promocion"),
        owner_client_side="Jefe de operaciones CD",
    )
    (out / "spec_linea_base.md").write_text(spec.to_markdown(), encoding="utf-8")
    results["baseline_spec_issues"] = spec.validate()

    panel, did, naive, trends = _baseline_experiment(seed)
    panel.to_csv(out / "panel_experimento.csv", index=False)

    # El ICC sale de la ventana historica, no de una constante. Es el parametro
    # de mayor apalancamiento del dimensionamiento —multiplica la muestra por
    # ~17 con 300 pedidos al dia— y estaba puesto a mano en 0,02. No necesita
    # ningun sensor: necesita el log que el cliente ya tiene.
    #
    # La ventana historica aca es el periodo PRE, que es lo que existe cuando
    # hay que dimensionar. Los dos grupos corren con la misma configuracion en
    # el pre, asi que no hay nivel que remover; en un log real donde el pre
    # incluya un peak conocido, `strata` es el argumento para sacarlo.
    pre = panel[panel["period"] == "pre"]
    icc = icc_from_log(pre["cycle_min"], pre["day_seed"])
    results["icc_medido"] = icc

    cyc = log.case_durations()["cycle_time_s"] / 60
    sd = sd_from_log(cyc)
    results["baseline_sizing"] = required_days(
        sd=sd,
        effect=0.15 * float(cyc.median()),
        units_per_day=dc.config.n_orders,
        icc=icc["icc_for_design"] if icc["usable"] else 0.0,
    )
    # Si el ICC no se pudo medir, el dimensionamiento corre con 0 —el unico
    # valor que no inventa correlacion— y lo dice. Un `days_per_group` calculado
    # sobre un ICC ausente es el numero que hace que un piloto "significativo"
    # no se replique.
    results["baseline_sizing"]["icc_source"] = (
        f"medido sobre {icc['n_groups']} dias de la ventana pre "
        f"(IC95 {icc['ci_low']}-{icc['ci_high']})"
        if icc["usable"]
        else f"NO MEDIDO — se uso 0: {icc['reason']}"
    )
    if icc["usable"]:
        # Cuantos dias hacen falta en cada extremo del IC del ICC. El punto solo
        # es la misma clase de numero que el 0,02 que vino a reemplazar: el
        # dimensionamiento es tan sensible al ICC que un intervalo de 0,017 a
        # 0,22 mueve la ventana de medicion de semanas a meses. Es la cifra que
        # hay que llevar a la reunion donde se compromete el cronograma.
        results["baseline_sizing"]["days_per_group_por_ic_del_icc"] = {
            "icc_low": required_days(
                sd=sd,
                effect=0.15 * float(cyc.median()),
                units_per_day=dc.config.n_orders,
                icc=max(0.0, icc["ci_low"]),
            )["days_per_group"],
            "icc_high": required_days(
                sd=sd,
                effect=0.15 * float(cyc.median()),
                units_per_day=dc.config.n_orders,
                icc=max(0.0, icc["ci_high"]),
            )["days_per_group"],
        }

    results["pre_post_naive"] = naive
    results["parallel_trends"] = trends
    results["diff_in_diff"] = did

    # ------------------------------------------------- 7. sonda integracion
    say("[7/9] sonda de integracion...")
    edi = smoke_report(_sample_edi())
    results["edi_smoke"] = edi.to_dict("records")
    edi.to_csv(out / "edi_smoke.csv", index=False)

    contract = ContractCheck(
        name="POST /shipments",
        required={"shipment_id": str, "order_id": str, "weight_kg": float, "eta": str, "status": str},
        nullable=("eta",),
        enums={"status": ("CREATED", "IN_TRANSIT", "DELIVERED")},
        datetime_fields=("eta",),
    )
    payload = {
        "shipment_id": "SH-1",
        "order_id": 774,  # tipo equivocado
        "weight_kg": 12.4,
        "eta": "2026-03-02T18:00:00",  # sin zona horaria
        "status": "EN_TRANSITO",  # fuera del enum
        "carrier_ref": "X",  # campo no declarado
    }
    results["contract_check"] = check_payload(payload, contract)
    results["timezone_audit"] = timezone_audit(dc.events, ["timestamp"]).to_dict("records")
    results["idempotency"] = retry_idempotency_check(
        dc.events, ["case_id", "activity", "timestamp"]
    )

    # ------------------------------------------------- 8. trabajo estandar
    say("[8/9] trabajo estandar y runbook...")
    jb = _job_breakdown()
    results["twi_issues"] = jb.validate()
    (out / "twi_desglose.md").write_text(jb.to_markdown(), encoding="utf-8")
    (out / "runbook.md").write_text(
        runbook_template("Agente de excepciones de picking", "CD Pudahuel"), encoding="utf-8"
    )

    # ------------------------------------------------- 9. SPC
    say("[9/9] control estadistico y monitor de degradacion...")
    good = generate_dc(DCConfig(seed=seed + 50, layout=lay, slotting="abc", dim_error_rate=0.04))
    good_cyc = EventLog(good.events).case_durations()["cycle_time_s"] / 60
    baseline_series = _chunk_medians(good_cyc, 30)
    monitoring_series = _chunk_medians(cyc, 20)  # el proceso volvio al estado degradado

    alarm = degradation_alarm(baseline_series, monitoring_series, direction="lower_is_better")
    results["degradation_alarm"] = {k: v for k, v in alarm.items() if k != "detail"}
    results["degradation_alarm"]["n_detail_rows"] = len(alarm["detail"])
    plot_xmr(
        baseline_series + monitoring_series,
        compute_limits(baseline_series),
        title="Tiempo de ciclo mediano — linea base congelada (30) + monitoreo (20)",
        path=str(out / "xmr.png"),
    )

    # ------------------------------------------------- A3
    a3 = build_a3_from_findings(
        title="Reproceso de packing y espera de picking en CD Pudahuel",
        owner="FDE",
        site="CD Pudahuel",
        conformance=conf,
        bottleneck_row=bn.iloc[0].to_dict(),
        dq=dq,
        link=link,
        travel=results["travel"],
        charts=["spaghetti.png", "heatmap.png", "xmr.png"],
    )
    results["a3_issues"] = a3.validate()
    (out / "A3.md").write_text(a3.to_markdown(), encoding="utf-8")

    (out / "hallazgos.json").write_text(
        json.dumps(
            _json_safe(results), indent=2, ensure_ascii=False, default=str, allow_nan=False
        ),
        encoding="utf-8",
    )
    say(f"\nArtefactos escritos en {out.resolve()}")
    return results


def _baseline_experiment(seed: int) -> tuple[pd.DataFrame, dict, dict]:
    """Experimento con grupo de control y estacionalidad real.

    El periodo post tiene 15% mas volumen (peak). El grupo tratado recibe el
    reslotting ABC y la correccion del maestro; el control no. El pre/post naive
    SUBESTIMA la mejora porque el peak empeora a los dos grupos. DiD lo corrige.
    """
    lay = Layout()
    NORMAL, PEAK = 700, 805  # el periodo post trae 15% mas volumen: el peak pega a los dos grupos
    REPS = 3  # dias por celda

    # Fechas reales por dia de medicion. Sin una columna de tiempo el panel no
    # se puede someter a `parallel_trends_check`, y sin ese chequeo el DiD se
    # reporta como valido sin haber verificado el unico supuesto que lo sostiene.
    PRE_START = pd.Timestamp("2026-03-02")
    POST_START = pd.Timestamp("2026-03-16")
    CUTOFF = pd.Timestamp("2026-03-09")

    # Con una sola corrida por celda el estimador queda dominado por el ruido
    # entre turnos — la mediana del tiempo de ciclo varia 30% de un dia a otro
    # en un sistema cerca de saturacion. Por eso se promedian varios dias por
    # celda; es exactamente lo que hay que hacer en terreno y la razon por la
    # que la ventana de linea base son semanas y no dias.
    cells = {
        ("control", "pre"): dict(n_orders=NORMAL),
        ("control", "post"): dict(n_orders=PEAK),
        ("treat", "pre"): dict(n_orders=NORMAL),
        # El tratamiento: reslotting ABC + correccion de datos maestros.
        ("treat", "post"): dict(n_orders=PEAK, slotting="abc", dim_error_rate=0.05),
    }

    frames = []
    s = seed
    for (grp, per), kw in cells.items():
        base = PRE_START if per == "pre" else POST_START
        for rep in range(REPS):
            s += 1
            c = EventLog(generate_dc(DCConfig(seed=s, layout=lay, **kw)).events).case_durations()
            frames.append(
                pd.DataFrame(
                    {
                        "case_id": c["case_id"],
                        "cycle_min": c["cycle_time_s"] / 60,
                        "group": grp,
                        "period": per,
                        "day_seed": s,
                        "day": base + pd.Timedelta(days=rep),
                    }
                )
            )
    panel = pd.concat(frames, ignore_index=True)

    naive = pre_post(
        panel.loc[(panel["group"] == "treat") & (panel["period"] == "pre"), "cycle_min"],
        panel.loc[(panel["group"] == "treat") & (panel["period"] == "post"), "cycle_min"],
    )
    did = diff_in_diff(panel, "cycle_min", "group", "period")
    # El chequeo va ANTES de que nadie mire el estimador. Si los grupos ya
    # divergian en el periodo pre, el DiD esta sesgado y hay que decirlo antes
    # de que lo diga el analista del cliente.
    trends = parallel_trends_check(panel, "cycle_min", "group", "day", CUTOFF)
    return panel, did, naive, trends


def _job_breakdown() -> JobBreakdown:
    jb = JobBreakdown(
        task="Resolver una excepcion de ubicacion en picking",
        role="Picker / lider de turno",
        site="CD Pudahuel",
        author="FDE",
        tools_required=["Terminal RF", "acceso a consulta de inventario", "etiquetas de ubicacion"],
        safety_notes=["No subir al nivel 3 o 4 sin escalera certificada."],
        escalation="Lider de turno -> supervisor CD -> guardia FDE (canal #cd-pudahuel, 24/7 en las 4 semanas post go-live)",
    )
    jb.add(
        "Confirmar que la ubicacion esta realmente vacia",
        ["Mirar los tres niveles del modulo, no solo el indicado"],
        ["El 30% de las excepciones son producto en el nivel de arriba o de al lado"],
        target_time_s=20,
    )
    jb.add(
        "Registrar la excepcion en el RF antes de buscar",
        ["Marcar 'no encontrado' en el terminal, no seguir de largo"],
        ["Si no se registra, el sistema nunca aprende y el error se repite manana"],
        target_time_s=15,
    )
    jb.add(
        "Consultar ubicaciones alternativas del SKU",
        ["Usar la consulta de inventario, no la memoria"],
        ["La memoria funciona para los SKU que uno conoce; el turno de noche no los conoce"],
        target_time_s=25,
    )
    jb.add(
        "Tomar el producto y confirmar la ubicacion real en el RF",
        ["Escanear la etiqueta de la ubicacion donde SI estaba"],
        ["Es el unico dato que permite corregir el maestro; sin el, la excepcion se repite"],
        target_time_s=20,
    )
    jb.add(
        "Continuar la ruta desde donde quedo",
        ["Volver a la secuencia del RF, no reordenar a criterio propio"],
        ["Reordenar rompe la optimizacion de ruta y agrega caminata al resto de la ola"],
        target_time_s=10,
    )
    return jb
