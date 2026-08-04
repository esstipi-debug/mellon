"""CLI del kit.

    fdekit demo                  diagnostico completo -> out/
    fdekit synth --out data/     genera el CD sintetico
    fdekit mine  --log x.csv     process mining sobre un log real
    fdekit travel --log x.csv    espagueti y caminata
    fdekit dq --master m.csv --measured p.csv
    fdekit sim --log x.csv --pickers 9 --packers 4
    fdekit spc --values v.csv --baseline 30
    fdekit probe --edi carpeta/
    fdekit templates --out docs/ plantillas A3, TWI, runbook, spec
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def _print(obj):
    if isinstance(obj, pd.DataFrame):
        print(obj.to_string(index=False))
    else:
        print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _load_log(path: str):
    from .processmining import EventLog

    df = pd.read_csv(path)
    return EventLog(df)


# ---------------------------------------------------------------- comandos


def cmd_demo(a):
    from .demo import run_full_diagnosis

    run_full_diagnosis(a.out, seed=a.seed)
    return 0


def cmd_synth(a):
    from .synth import DCConfig, generate_dc

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dc = generate_dc(DCConfig(seed=a.seed, n_orders=a.orders, n_skus=a.skus))
    dc.events.to_csv(out / "event_log.csv", index=False)
    dc.master.to_csv(out / "master_wms.csv", index=False)
    dc.truth.to_csv(out / "truth_fisica.csv", index=False)
    dc.order_lines.to_csv(out / "order_lines.csv", index=False)
    print(dc.summary())
    print(f"escrito en {out.resolve()}")
    return 0


def cmd_mine(a):
    from .processmining import (
        bottlenecks,
        conformance,
        pareto_coverage,
        rework_summary,
        to_mermaid,
        variants,
    )

    log = _load_log(a.log)
    print(f"\n== {len(log):,} eventos / {log.n_cases:,} casos / {len(log.activities)} actividades ==\n")

    print("-- variantes principales --")
    _print(variants(log, top=a.top, collapse_repeats=True))
    print("\n-- cobertura de Pareto --")
    _print(pareto_coverage(log))
    print("\n-- cuellos de botella (por tiempo total perdido) --")
    _print(bottlenecks(log))
    print("\n-- reproceso --")
    _print(rework_summary(log))

    if a.declared:
        print("\n-- conformidad contra el flujo declarado --")
        _print(conformance(log, a.declared.split(",")))
    if a.mermaid:
        Path(a.mermaid).write_text(to_mermaid(log), encoding="utf-8")
        print(f"\nDFG escrito en {a.mermaid}")
    return 0


def cmd_travel(a):
    from .layout import Layout
    from .timestudy.spaghetti import plot_heatmap, plot_spaghetti, travel_stats

    log = _load_log(a.log)
    lay = Layout()
    _print(travel_stats(log, lay))
    if a.plots:
        out = Path(a.plots)
        out.mkdir(parents=True, exist_ok=True)
        plot_spaghetti(log, lay, path=str(out / "spaghetti.png"))
        plot_heatmap(log, lay, path=str(out / "heatmap.png"))
        print(f"graficos en {out.resolve()}")
    return 0


# Multiplo del paso mas grueso de la grilla que se acepta como distancia de un
# punto medido a la ubicacion mas cercana. El default sale de la GEOMETRIA y no
# de un numero fijo: en un CD de `aisle_pitch=3` un metro de error es ruido, y
# en una maqueta de escritorio de `bay_pitch=0.1` es estar en la otra punta.
# Dos pasos porque un punto entre dos ubicaciones vecinas dista a lo sumo medio
# paso, y hace falta margen para el error de la homografia (criterio del spec:
# 5 cm) mas el jitter del marcador; mas de dos pasos ya no es "cayo entre dos
# ubicaciones", es "cayo afuera de la grilla".
FACTOR_MAX_DISTANCE = 2.0


def umbral_anonimato(valor: str) -> int:
    """Tipo de `--k`: entero >= 1, validado en el parser y no aguas abajo.

    `AnonymityGate.__post_init__` ya rechaza k<1, asi que esto no es la unica
    defensa -- es la que hace que el error salga TEMPRANO, con el formato de
    argparse ("argument --k: ...") y antes de leer un solo CSV. Con la
    validacion solo en el dataclass, `--k 0` recorre todo el pipeline, procesa
    el video y falla recien al emitir, que es el momento en que menos se
    entiende que el problema estaba en la linea de comandos.
    """
    try:
        k = int(valor)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"el umbral de anonimato tiene que ser un entero, llego '{valor}'"
        ) from None
    if k < 1:
        raise argparse.ArgumentTypeError(
            f"el umbral de anonimato tiene que ser >= 1, llego {k}. k=1 es el "
            "minimo y significa 'emito el agregado aunque cubra una sola "
            "persona'; k=0 no baja el umbral, apaga la compuerta. Usar --k 1 si "
            "esa es la intencion (queda registrado en anonymity_k)."
        )
    return k


def max_distance_por_defecto(layout) -> float:
    """Limite de confianza derivado de la geometria declarada.

    Existe porque `nearest_location` acepta `max_distance_m=None` y ese `None`
    DESACTIVA el chequeo entero: un punto a 500 m fuera de planta se pega en
    silencio a la esquina del layout, cuenta como parada real, aporta sus
    metros al total y la cobertura informa 100%. Todo el trabajo de detectar
    puntos fuera de planta existia y no se ejecutaba nunca en el pipeline real,
    porque `run_field` no pasaba el parametro. Un chequeo que hay que acordarse
    de activar es un chequeo que no existe: ahora siempre se pasa un numero, y
    `--max-distance` sirve para SOBREESCRIBIRLO, no para habilitarlo.
    """
    return FACTOR_MAX_DISTANCE * max(layout.aisle_pitch, layout.bay_pitch)


def run_field(
    detections,
    refs,
    out,
    fps,
    t0,
    today,
    layout=None,
    frames_total=None,
    log=None,
    max_distance_m=None,
    k=3,
) -> dict:
    """Demo de mesa: CSV de detecciones -> espagueti medido + residual.

    `t0` y `today` son argumentos (regla 4): esta funcion nunca mira el reloj,
    asi que el mismo `t0` siempre da el mismo resultado. `out` se crea si no
    existe.

    `layout` tambien es argumento: un escritorio de un metro no es un CD de
    doce pasillos, y fijar el layout por defecto haria que la taza cayera en
    "pasillo 2 modulo 2". El numero seguiria saliendo, y no querria decir
    nada.

    `frames_total` -- el denominador de la cobertura -- sale de una de dos
    fuentes, en este orden:

    1. La linea de metadatos `# frames_total=<int>` en el CSV de detecciones
       (la que escribe `vision.write_detections`).
    2. El parametro `frames_total` de esta funcion, si el CSV no la trae.

    Si ninguna de las dos esta, esta funcion falla en vez de adivinar:
    derivarlo del frame maximo visto en las detecciones daria siempre 100% de
    cobertura -- el tramo sin detecciones desaparece del calculo en vez de
    contar como cuadros sin ver, y eso vacia el modulo de cobertura entero,
    que es la pieza que sostiene la honestidad de toda la medicion (regla 3).

    `log` es el log del WMS: el modelo contra el que se compara. Con el, esta
    funcion produce EL ENTREGABLE que el README promete -- "la diferencia entre
    los dos es el hallazgo" -- llamando a `groundtruth.compare_travel` y
    metiendo su resultado entero bajo la clave `residual`. Sin el, `residual`
    es `None` y `residual_reason` dice POR QUE: que no se paso un modelo contra
    el cual comparar. La ausencia silenciosa del campo se lee como "no hubo
    residual"; un `None` con motivo se lee como lo que es.

    `max_distance_m` es el limite de confianza espacial. Su default sale de la
    geometria (`max_distance_por_defecto`), nunca es `None`: ver ahi por que.

    `k` es el umbral de anonimato de la regla 10, aplicado en el borde de
    salida (`privacy.gate_output`). El conteo de sujetos es la cantidad de
    PISTAS reconstruidas: un marcador, un carro, una persona.

    EL PNG TAMBIEN ES SALIDA A DISCO, y por eso la decision de la compuerta se
    calcula ANTES de dibujar. Antes de este arreglo `plot_spaghetti` escribia
    el archivo mientras se armaba el diccionario, o sea antes de
    `gate_output`: con k=3 y una sola pista, el JSON retenia `locations` con
    su motivo y en el mismo directorio quedaba el PNG con el recorrido
    completo del unico sujeto. El grafico ES el itinerario -- retener la lista
    de ubicaciones y dibujarla al lado es no retener nada. Si el agregado no
    llega al umbral no se escribe el archivo, y `espagueti_path` sale `None`
    con su motivo, igual que `locations`.
    """
    import csv as _csv
    from pathlib import Path

    from .field.homography import FloorHomography
    from .field.privacy import AnonymityGate, gate_output, new_session_salt
    from .field.tracks import build_tracks, load_detections, track_distance_m, tracks_to_eventlog
    from .layout import Layout
    from .timestudy.spaghetti import plot_spaghetti

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    with open(refs, encoding="utf-8", newline="") as fh:
        filas = list(_csv.DictReader(fh))
    if len(filas) != 4:
        raise ValueError(
            f"el CSV de referencias necesita exactamente cuatro filas (esquinas "
            f"del piso con coordenadas conocidas), llegaron {len(filas)}"
        )

    homografia = FloorHomography.from_points(
        [(float(f["x_px"]), float(f["y_px"])) for f in filas],
        [(float(f["x_m"]), float(f["y_m"])) for f in filas],
    )

    dets, frames_total_csv = load_detections(detections)
    if frames_total_csv is not None:
        frames_total_resuelto = frames_total_csv
    elif frames_total is not None:
        frames_total_resuelto = frames_total
    else:
        raise ValueError(
            "el CSV de detecciones no declara el total de cuadros del video "
            "(falta la linea '# frames_total=<int>'), y no se paso "
            "frames_total explicito: sin ninguno de los dos no hay como "
            "calcular la cobertura sin inventar un numero. Regenerar el CSV "
            "con vision.write_detections (que ahora recibe frames_total) o "
            "pasar --frames en la linea de comandos."
        )

    lay = layout or Layout()
    limite_m = max_distance_m if max_distance_m is not None else max_distance_por_defecto(lay)

    tracks, cobertura = build_tracks(
        dets, homografia, fps=fps, salt=new_session_salt(), frames_total=frames_total_resuelto
    )
    medido, cobertura = tracks_to_eventlog(
        tracks, lay, t0=t0, coverage=cobertura, max_distance_m=limite_m
    )

    # La compuerta se resuelve ANTES de dibujar: el PNG es salida a disco.
    compuerta = AnonymityGate(k=k)
    if compuerta.allows(len(tracks)):
        destino_png = out / "espagueti_medido.png"
        plot_spaghetti(medido, lay, path=str(destino_png))
        espagueti_path = str(destino_png)
        espagueti_reason = None
    else:
        espagueti_path = None
        espagueti_reason = _ESPAGUETI_RETENIDO.format(n=len(tracks), k=k)

    residual, residual_reason = _residual_contra_el_modelo(
        log, tracks, lay, cobertura, today=today
    )

    salida = {
        "tracks": len(tracks),
        "measured_m_in_window": round(
            sum(track_distance_m(p) for p in tracks.values()), 1
        ),
        "stops": int(len(medido)),
        # Las ubicaciones dependen de la geometria que se paso, y por eso van
        # en la salida: son lo que deja ver si el layout declarado es el
        # correcto. Con un solo sujeto son tambien su itinerario completo, y
        # por eso el borde de salida las retiene bajo el umbral k (regla 10).
        "locations": sorted(medido.df["location"].dropna().unique().tolist()),
        "max_distance_m": round(limite_m, 3),
        "coverage_note": cobertura.note(),
        # El grafico sigue la misma regla que `locations`: es el itinerario del
        # sujeto dibujado, asi que bajo el umbral no se escribe y el campo dice
        # por que en vez de desaparecer.
        "espagueti_path": espagueti_path,
        "espagueti_withheld_reason": espagueti_reason,
        "residual": residual,
        "residual_reason": residual_reason,
        "today": today.isoformat(),
    }
    # Borde unico (spec seccion 6): nada sale de esta funcion sin pasar por aca.
    return gate_output(salida, n_subjects=len(tracks), gate=compuerta)


_ESPAGUETI_RETENIDO = (
    "'espagueti_medido.png' no se escribio: el agregado cubre {n} sujeto(s) y "
    "el umbral de anonimato es k={k}. El grafico de espagueti ES el itinerario "
    "completo de esa persona, dibujado -- retener 'locations' en el JSON y "
    "dejar el PNG al lado en el mismo directorio no retiene nada (spec seccion "
    "6: toda salida a disco pasa por el borde). Para obtenerlo: ampliar la "
    "ventana hasta tener al menos k sujetos, o bajar el umbral a proposito con "
    "--k 1 asumiendo lo que eso significa."
)


_SIN_MODELO = (
    "no hay residual porque no se paso el modelo contra el cual comparar: "
    "`fdekit field` mide el recorrido, y el hallazgo es la DIFERENCIA contra "
    "lo que el WMS dice que deberia haber sido. Pasar el log del WMS con "
    "--log <ruta.csv> para obtenerlo."
)


def _residual_contra_el_modelo(log, tracks, layout, coverage, today):
    """Compara la medicion contra el log del WMS, si es que se paso uno.

    Devuelve `(residual, motivo)`. `groundtruth.compare_travel` existia desde
    la tarea 8 y no la llamaba nadie fuera de sus tests: el branch declaraba
    que el entregable es un residual medido y ningun comando lo producia. Aca
    se enchufa.

    El resultado entra ENTERO -- `residual_pct`, `modeled_m_per_order`,
    `measured_m_per_order`, `residual_flag`, `residual_flag_reason`,
    `dock_legs_pct_of_modeled`, `track_pct` -- porque el porcentaje solo invita
    a leerse al reves: el modelo es un piso, asi que un residual chico es una
    medicion sospechosa, no un modelo preciso, y eso lo dice el flag, no el
    numero.
    """
    if log is None:
        return None, _SIN_MODELO

    from .groundtruth import compare_travel

    resultado = compare_travel(_load_log(log), tracks, layout, coverage, today=today)
    return resultado, resultado["residual_flag_reason"]


def cmd_field(a):
    """El reloj se lee UNA sola vez, aca en el borde, y nunca en el analisis.

    `run_field` recibe t0 y today como argumentos (regla 4). Esta funcion es
    el unico lugar del camino que tiene permitido mirar el reloj.
    """
    import datetime as _dt

    from .layout import Layout

    out = run_field(
        detections=a.detections,
        refs=a.refs,
        out=a.out,
        fps=a.fps,
        t0=pd.Timestamp.now(),
        today=_dt.date.today(),
        layout=Layout(
            aisles=a.aisles, bays=a.bays, aisle_pitch=a.aisle_pitch, bay_pitch=a.bay_pitch
        ),
        frames_total=a.frames,
        log=a.log,
        max_distance_m=a.max_distance,
        k=a.k,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_dq(a):
    from .dataquality import audit_master, audit_summary, sampling_plan

    master = pd.read_csv(a.master)
    if a.plan_only:
        _print(sampling_plan(len(master), margin_of_error=a.moe, expected_defect_rate=a.expected))
        return 0
    if not a.measured:
        print("falta --measured (la medicion fisica en terreno)", file=sys.stderr)
        return 2
    audit = audit_master(master, pd.read_csv(a.measured))
    _print(audit_summary(audit, population=len(master)))
    if a.out:
        audit.to_csv(a.out, index=False)
        print(f"\ndetalle en {a.out}")
    return 0


def cmd_sim(a):
    from .sim import calibrate_from_log, sizing_sweep

    log = _load_log(a.log)
    cfg = calibrate_from_log(log, a.pickers, a.packers)
    print("-- parametros calibrados desde el log --")
    _print(cfg.__dict__)
    print("\n-- barrido de dimensionamiento --")
    _print(sizing_sweep(cfg, range(max(2, a.pickers - 3), a.pickers + 5), replications=a.reps))
    return 0


def cmd_spc(a):
    from .spc import compute_limits, degradation_alarm, plot_xmr

    values = pd.read_csv(a.values).iloc[:, 0].astype(float).tolist()
    base, mon = values[: a.baseline], values[a.baseline :]
    if not mon:
        print("no hay puntos de monitoreo despues de la linea base", file=sys.stderr)
        return 2
    _print(degradation_alarm(base, mon, direction=a.direction))
    if a.plot:
        plot_xmr(values, compute_limits(base), title="XmR", path=a.plot)
        print(f"grafico en {a.plot}")
    return 0


def cmd_probe(a):
    from .probe.edi import smoke_report

    files = sorted(Path(a.edi).glob("*.edi")) + sorted(Path(a.edi).glob("*.x12"))
    if not files:
        print(f"sin archivos .edi/.x12 en {a.edi}", file=sys.stderr)
        return 2
    msgs = {f.name: f.read_text(encoding="utf-8", errors="replace") for f in files}
    _print(smoke_report(msgs))
    return 0


def cmd_value(a):
    from .value import (
        ARCHETYPES,
        ValueCase,
        build_archetype,
        cost_to_serve,
        gainshare_terms,
        findings_contract,
        levers_from_findings,
        model_ladder,
        price_band,
    )

    findings = json.loads(Path(a.findings).read_text(encoding="utf-8"))
    keys = [a.archetype] if a.archetype != "todos" else sorted(ARCHETYPES)

    # Regla 3. Una palanca a la que le falta un bloque de entrada sale mas
    # chica y no se distingue de una entera: el VAN se imprime igual de
    # creible. `_reject_preannualized` cubre los nombres de clave viejos, no el
    # bloque que nunca vino — que es el caso normal apenas el `hallazgos.json`
    # lo produce algo que no sea `fdekit demo`.
    _contrato = findings_contract(findings)
    if _contrato["parciales"]:
        print(f"AVISO: {_contrato['nota']}\n")

    if a.calibration == "generico":
        print(
            "AVISO: calibracion 'generico' = priors de LATAM sin validar. Sirve para probar "
            "el modelo, no para cotizar. Usar --calibration chile.\n"
        )

    if a.regimes:
        from .value import REGIMES, STAFFING_MODELS, regime_table

        _print(pd.DataFrame(regime_table()))
        print("\nModelos de dotacion (JUICIO, no medicion):")
        for k, v in STAFFING_MODELS.items():
            print(f"  {k:<28} {v['delta'][0]:+.2f} a {v['delta'][1]:+.2f}   {v['desc']}")
        print(
            "\nLa institucion que manda es el contrato, no el pais: un 3PL open-book en\n"
            "Chile puede tener mas flexibilidad de caja que planta propia en EE.UU.\n"
            "Pedir el contrato antes que cualquier estadistica."
        )
        for k, r in REGIMES.items():
            print(f"\n[{k}] {r.driver}")
        return 0

    for key in keys:
        arch = build_archetype(
            key, a.scale, calibration=a.calibration,
            labor_regime=a.country, staffing_model=a.staffing_model,
        )
        levers = levers_from_findings(findings, arch, has_control_group=a.control)
        cost = cost_to_serve(a.fde_days, a.day_rate, travel_trips=a.trips)["costo_total_usd"]
        case = ValueCase(
            arch, levers, cost, sites=a.sites, has_control_group=a.control, horizon_months=a.horizon
        )
        r = case.simulate(a.sims)

        print(f"\n{'='*78}\n{arch.name}  |  escala {a.scale}  |  {a.sites} sitio(s)\n{'='*78}")
        print(r.to_markdown())

        ws = case.warnings(r)
        if ws:
            print("Guardrails:")
            for x in ws:
                print(f"  ! {x}")

        model = a.model or model_ladder(a.control, a.months)
        print(f"\nModelo de precio sugerido: {model}")
        band = price_band(r, model, has_control_group=a.control)
        _print(band)

        if not band["viable"]:
            # Mostrar terminos de un modelo que el propio analisis descarto es
            # como se termina negociando algo que no cierra.
            alt = band["alternativa"]
            print(f"\nCae a: {alt}")
            _print(price_band(r, alt, has_control_group=a.control))
        elif model == "gainshare":
            print("\nTerminos de gainshare:")
            _print(gainshare_terms(r, share_pct=a.share))
    return 0


def cmd_templates(a):
    from .a3 import A3
    from .baseline import BaselineSpec
    from .gemba import GembaSession
    from .standardwork import JobBreakdown, runbook_template

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    (out / "A3_plantilla.md").write_text(A3(title="", owner="").to_markdown(), encoding="utf-8")
    (out / "twi_plantilla.md").write_text(
        JobBreakdown(task="", role="").to_markdown(), encoding="utf-8"
    )
    (out / "runbook_plantilla.md").write_text(runbook_template("<sistema>"), encoding="utf-8")
    (out / "spec_linea_base_plantilla.md").write_text(
        BaselineSpec(
            metric_name="",
            metric_definition="",
            data_source="",
            unit_of_analysis="",
            direction="lower_is_better",
            target_change_pct=0.0,
            baseline_window_days=21,
        ).to_markdown(),
        encoding="utf-8",
    )
    (out / "gemba_checklist.md").write_text(
        GembaSession(out / ".tmp.jsonl", site="<sitio>").checklist(), encoding="utf-8"
    )
    (out / ".tmp.jsonl").unlink(missing_ok=True)
    print(f"plantillas en {out.resolve()}")
    return 0


# -------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fdekit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="diagnostico completo sobre el CD sintetico")
    d.add_argument("--out", default="out")
    d.add_argument("--seed", type=int, default=7)
    d.set_defaults(func=cmd_demo)

    s = sub.add_parser("synth", help="genera el CD sintetico")
    s.add_argument("--out", default="data")
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--orders", type=int, default=2500)
    s.add_argument("--skus", type=int, default=1800)
    s.set_defaults(func=cmd_synth)

    m = sub.add_parser("mine", help="process mining sobre un log")
    m.add_argument("--log", required=True)
    m.add_argument("--top", type=int, default=10)
    m.add_argument("--declared", help="flujo declarado, separado por comas")
    m.add_argument("--mermaid", help="ruta para escribir el DFG")
    m.set_defaults(func=cmd_mine)

    t = sub.add_parser("travel", help="caminata y espagueti")
    t.add_argument("--log", required=True)
    t.add_argument("--plots", help="carpeta de salida de graficos")
    t.set_defaults(func=cmd_travel)

    f = sub.add_parser("field", help="demo de mesa: detecciones -> espagueti medido")
    f.add_argument("--detections", required=True)
    f.add_argument("--refs", required=True, help="CSV con 4 esquinas: x_px,y_px,x_m,y_m")
    f.add_argument("--out", default="out")
    f.add_argument("--fps", type=float, default=30.0)
    f.add_argument(
        "--frames",
        type=int,
        default=None,
        help="total de cuadros del video; solo hace falta si el CSV no trae "
        "la linea '# frames_total=<int>' (la que escribe write_detections)",
    )
    f.add_argument(
        "--log",
        default=None,
        help="log del WMS: el modelo contra el que se mide. Sin el no hay "
        "residual, y la salida lo dice explicitamente en vez de omitirlo",
    )
    f.add_argument(
        "--max-distance",
        dest="max_distance",
        type=float,
        default=None,
        help="metros maximos entre un punto medido y la ubicacion mas cercana "
        "antes de descartarlo por caer fuera de planta. Por defecto se deriva "
        "de la geometria: 2 x el mayor de --aisle-pitch y --bay-pitch",
    )
    f.add_argument(
        "--k",
        type=umbral_anonimato,
        default=3,
        help="umbral de anonimato (regla 10), minimo 1: con menos de k pistas "
        "reconstruidas no se emiten ni la lista de ubicaciones ni el PNG del "
        "espagueti. En la maqueta de mesa, con un solo carro, hace falta --k 1",
    )
    # Geometria: los defaults son los del CD. La maqueta de escritorio pasa la
    # suya (p.ej. --aisles 4 --bays 10 --aisle-pitch 3 --bay-pitch 1).
    f.add_argument("--aisles", type=int, default=12)
    f.add_argument("--bays", type=int, default=50)
    f.add_argument("--aisle-pitch", type=float, default=3.0)
    f.add_argument("--bay-pitch", type=float, default=1.2)
    f.set_defaults(func=cmd_field)

    q = sub.add_parser("dq", help="auditoria de datos maestros")
    q.add_argument("--master", required=True)
    q.add_argument("--measured", help="medicion fisica en terreno")
    q.add_argument("--plan-only", action="store_true", help="solo el plan de muestreo")
    q.add_argument("--moe", type=float, default=0.05)
    q.add_argument("--expected", type=float, default=0.2)
    q.add_argument("--out")
    q.set_defaults(func=cmd_dq)

    v = sub.add_parser("sim", help="calibra y dimensiona")
    v.add_argument("--log", required=True)
    v.add_argument("--pickers", type=int, default=9)
    v.add_argument("--packers", type=int, default=4)
    v.add_argument("--reps", type=int, default=3)
    v.set_defaults(func=cmd_sim)

    c = sub.add_parser("spc", help="control estadistico y alarma de degradacion")
    c.add_argument("--values", required=True, help="CSV con la serie en la primera columna")
    c.add_argument("--baseline", type=int, default=30, help="puntos de linea base")
    c.add_argument("--direction", default="lower_is_better", choices=["lower_is_better", "higher_is_better"])
    c.add_argument("--plot")
    c.set_defaults(func=cmd_spc)

    b = sub.add_parser("probe", help="smoke test de EDI")
    b.add_argument("--edi", required=True, help="carpeta con .edi / .x12")
    b.set_defaults(func=cmd_probe)

    val = sub.add_parser("value", help="caso economico y modelo de precio")
    val.add_argument("--findings", default="out/hallazgos.json")
    val.add_argument("--archetype", default="todos", help="3PL | RETAIL_OMNI | MANUFACTURA | ECOMMERCE | MAYORISTA | todos")
    val.add_argument("--scale", default="grande", choices=["pyme", "media", "grande", "enterprise"])
    val.add_argument(
        "--calibration",
        default="chile",
        choices=["chile", "generico"],
        help="chile = parametros verificados contra fuente; generico = priors sin validar",
    )
    # El regimen laboral y la calibracion economica son ejes distintos: hay
    # costo verificado solo para Chile, pero labor_flex_share para cuatro paises.
    val.add_argument(
        "--country",
        default=None,
        choices=["usa", "australia", "chile", "argentina"],
        help="regimen laboral para labor_flex_share (default: chile si --calibration chile)",
    )
    val.add_argument(
        "--staffing-model",
        default="planta_propia",
        dest="staffing_model",
        choices=["planta_propia", "3pl_open_book", "3pl_closed_book",
                 "3pl_volumen_comprometido", "mix"],
        help="el ajuste mas grande del estudio: el contrato manda sobre el pais",
    )
    val.add_argument(
        "--regimes",
        action="store_true",
        help="imprime la tabla de regimenes laborales y modelos de dotacion, y sale",
    )
    val.add_argument("--sites", type=int, default=1)
    val.add_argument("--control", action="store_true", help="hay linea base con grupo de control")
    val.add_argument("--fde-days", type=float, default=70, dest="fde_days")
    val.add_argument("--day-rate", type=float, default=900, dest="day_rate")
    val.add_argument("--trips", type=int, default=5)
    val.add_argument("--horizon", type=int, default=36)
    val.add_argument("--months", type=int, default=0, help="meses de relacion con el cliente")
    val.add_argument("--model", help="forzar modelo de precio")
    val.add_argument("--share", type=float, default=0.20)
    val.add_argument("--sims", type=int, default=20_000)
    val.set_defaults(func=cmd_value)

    from .decide.cli import register as _register_decide

    _register_decide(sub)

    z = sub.add_parser("templates", help="escribe las plantillas en blanco")
    z.add_argument("--out", default="docs")
    z.set_defaults(func=cmd_templates)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
