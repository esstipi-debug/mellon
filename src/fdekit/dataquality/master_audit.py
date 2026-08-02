"""Plan de muestreo, auditoria fisica y vinculo con el reproceso observado."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ..stats import risk_ratio_2x2

DIM_COLS = ["length_cm", "width_cm", "height_cm"]
DEFAULT_TOLERANCE = {"dim_pct": 0.10, "weight_pct": 0.15}


def sampling_plan(
    population: int,
    margin_of_error: float = 0.05,
    confidence: float = 0.95,
    expected_defect_rate: float = 0.20,
) -> dict:
    """Tamano de muestra para estimar una tasa de defecto, con correccion por
    poblacion finita.

    Usar `expected_defect_rate=0.5` cuando no se tiene idea (es el peor caso y
    da la muestra mas grande). Si el cliente dice "nuestros datos estan bien",
    ese es exactamente el momento de usar 0.5.
    """
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p = expected_defect_rate
    n0 = z**2 * p * (1 - p) / margin_of_error**2
    n = n0 / (1 + (n0 - 1) / population)
    n = int(np.ceil(n))

    return {
        "population": population,
        "confidence": confidence,
        "margin_of_error": margin_of_error,
        "expected_defect_rate": p,
        "sample_size": n,
        # A 4 minutos por SKU medido (sacarlo, medir 3 dimensiones, pesar,
        # devolverlo). Este numero decide si el cliente presta gente o no.
        "field_hours_estimate": round(n * 4 / 60, 1),
    }


def stratified_sample(
    master: pd.DataFrame, n: int, by: str = "abc_class", seed: int = 0
) -> pd.DataFrame:
    """Muestra estratificada. Sobre-representa la clase A a proposito: un error
    en un SKU clase A cuesta 50 veces mas que en uno clase C."""
    rng = np.random.default_rng(seed)
    weights = {"A": 3.0, "B": 1.5, "C": 1.0}

    strata = master[by].map(lambda c: weights.get(c, 1.0))
    strata = strata / strata.sum()
    idx = rng.choice(master.index, size=min(n, len(master)), replace=False, p=strata.to_numpy())
    return master.loc[idx].sort_values("sku_id").reset_index(drop=True)


def audit_master(
    master: pd.DataFrame,
    measured: pd.DataFrame,
    tolerance: dict | None = None,
) -> pd.DataFrame:
    """Compara maestro contra medicion fisica.

    `measured` debe traer sku_id + las mismas columnas dimensionales, tomadas en
    terreno. Devuelve una fila por SKU auditado con los errores relativos y las
    banderas de fuera de tolerancia.
    """
    tol = {**DEFAULT_TOLERANCE, **(tolerance or {})}
    m = master.set_index("sku_id")
    p = measured.set_index("sku_id")
    common = m.index.intersection(p.index)
    m, p = m.loc[common], p.loc[common]

    out = pd.DataFrame(index=common)
    out["abc_class"] = m["abc_class"]

    for col in DIM_COLS + ["weight_kg"]:
        if col in m and col in p:
            err = (m[col] - p[col]) / p[col].replace(0, np.nan)
            out[f"{col}_err_pct"] = (err * 100).round(1)

    dim_err = out[[f"{c}_err_pct" for c in DIM_COLS]].abs().max(axis=1) / 100
    out["dim_out_of_tol"] = dim_err > tol["dim_pct"]
    out["weight_out_of_tol"] = out["weight_kg_err_pct"].abs() / 100 > tol["weight_pct"]

    # Error volumetrico: es el que rompe el cubicaje y la seleccion de carton.
    vol_m = m[DIM_COLS].prod(axis=1)
    vol_p = p[DIM_COLS].prod(axis=1)
    out["cube_err_pct"] = ((vol_m - vol_p) / vol_p * 100).round(1)

    if "home_location" in m and "home_location" in p:
        out["location_mismatch"] = m["home_location"] != p["home_location"]
    else:
        out["location_mismatch"] = False

    out["any_defect"] = out["dim_out_of_tol"] | out["weight_out_of_tol"] | out["location_mismatch"]
    return out.reset_index(names="sku_id")


def audit_summary(audit: pd.DataFrame, population: int | None = None, confidence: float = 0.95) -> dict:
    """Tasas de defecto con intervalo de confianza (Wilson).

    El intervalo importa: "18% de defectos" y "18% +-3%" son la misma medicion,
    pero solo la segunda sobrevive a la pregunta del CFO.
    """
    n = len(audit)
    z = stats.norm.ppf(1 - (1 - confidence) / 2)

    def wilson(k: int) -> tuple[float, float, float]:
        if n == 0:
            return (0.0, 0.0, 0.0)
        ph = k / n
        d = 1 + z**2 / n
        c = (ph + z**2 / (2 * n)) / d
        h = z * np.sqrt(ph * (1 - ph) / n + z**2 / (4 * n**2)) / d
        return (round(ph * 100, 1), round(max(0, c - h) * 100, 1), round(min(1, c + h) * 100, 1))

    metrics = {}
    for flag in ("dim_out_of_tol", "weight_out_of_tol", "location_mismatch", "any_defect"):
        k = int(audit[flag].sum())
        pt, lo, hi = wilson(k)
        metrics[flag] = {"defects": k, "rate_pct": pt, "ci_low_pct": lo, "ci_high_pct": hi}

    cube = audit["cube_err_pct"].dropna()
    by_class = (
        audit.groupby("abc_class")["any_defect"].mean().mul(100).round(1).to_dict()
        if "abc_class" in audit
        else {}
    )

    out = {
        "sample_size": n,
        "confidence": confidence,
        "rates": metrics,
        "cube_error": {
            # La mediana sobre TODO el catalogo suele dar 0 (la mayoria de los
            # SKU estan bien) y eso subestima el problema en el reporte. El
            # numero que importa es la magnitud del error donde lo hay.
            "median_abs_pct": round(float(cube.abs().median()), 1),
            "median_abs_pct_defective": round(
                float(cube[audit["dim_out_of_tol"]].abs().median()), 1
            )
            if bool(audit["dim_out_of_tol"].any())
            else 0.0,
            "p90_abs_pct": round(float(cube.abs().quantile(0.9)), 1),
            # Sesgo: si es positivo el maestro sobreestima el volumen y el
            # cliente esta comprando cartones de mas todos los dias.
            "bias_pct": round(float(cube.mean()), 1),
        },
        "defect_rate_by_class_pct": by_class,
    }
    if population:
        r = metrics["any_defect"]
        out["projected_defective_skus"] = {
            "point": int(round(population * r["rate_pct"] / 100)),
            "low": int(round(population * r["ci_low_pct"] / 100)),
            "high": int(round(population * r["ci_high_pct"] / 100)),
        }
    return out


def link_defects_to_rework(
    audit: pd.DataFrame,
    events: pd.DataFrame,
    order_lines: pd.DataFrame,
    rework_activity: str = "CARTON_REWORK",
) -> dict:
    """Triangulacion: ¿los pedidos que tocan SKUs con maestro malo sufren mas
    reproceso?

    Este es el resultado que cierra la discusion. La auditoria de datos y el
    process mining llegan al mismo hallazgo por caminos independientes, y el
    riesgo relativo lo dice en una linea.
    """
    bad = set(audit.loc[audit["dim_out_of_tol"], "sku_id"])
    if not bad:
        return {"error": "sin SKUs fuera de tolerancia en la muestra"}

    lines = order_lines.copy()
    lines["touches_bad"] = lines["sku_id"].isin(bad)
    per_order = lines.groupby("order_id")["touches_bad"].any()

    hit = set(events.loc[events["activity"] == rework_activity, "case_id"])
    frame = per_order.to_frame("touches_bad")
    frame["reworked"] = frame.index.isin(hit)

    ct = pd.crosstab(frame["touches_bad"], frame["reworked"])
    ct = ct.reindex(index=[False, True], columns=[False, True], fill_value=0)

    a, b = int(ct.loc[True, True]), int(ct.loc[True, False])  # expuestos
    c, d = int(ct.loc[False, True]), int(ct.loc[False, False])  # no expuestos

    # El calculo vive en `fdekit.stats` porque `decide.metrics` necesita el
    # mismo 2x2 para otra pregunta. Dos copias se desincronizan.
    r = risk_ratio_2x2(a, b, c, d)
    rr = r["risk_ratio"]
    paf = r["population_attributable_fraction_pct"]

    return {
        "exposed_orders": r["expuestos"],
        "unexposed_orders": r["no_expuestos"],
        "rework_rate_exposed_pct": r["tasa_expuestos_pct"],
        "rework_rate_unexposed_pct": r["tasa_no_expuestos_pct"],
        "risk_ratio": rr,
        "chi2": r["chi2"],
        "p_value": r["p_value"],
        "population_attributable_fraction_pct": paf,
        "reading": (
            f"Los pedidos que tocan un SKU con dimensiones erradas se reprocesan "
            f"{rr:.1f}x mas. Arreglar el maestro elimina ~{paf:.0f}% del reproceso "
            f"de carton, sin tocar una linea de codigo del producto."
        ),
    }
