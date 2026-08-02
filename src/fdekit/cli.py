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
        levers_from_findings,
        model_ladder,
        price_band,
    )

    findings = json.loads(Path(a.findings).read_text(encoding="utf-8"))
    keys = [a.archetype] if a.archetype != "todos" else sorted(ARCHETYPES)

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
