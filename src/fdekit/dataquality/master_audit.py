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


DEFECT_FLAGS = ("dim_out_of_tol", "weight_out_of_tol", "location_mismatch", "any_defect")


def _wilson(k: float, n: float, z: float) -> tuple[float, float, float]:
    """Intervalo de Wilson. Acepta k y n no enteros para poder recibir el tamano
    de muestra efectivo del estimador estratificado."""
    if n <= 0:
        return (0.0, 0.0, 0.0)
    ph = min(max(k / n, 0.0), 1.0)
    d = 1 + z**2 / n
    c = (ph + z**2 / (2 * n)) / d
    h = z * np.sqrt(ph * (1 - ph) / n + z**2 / (4 * n**2)) / d
    return (
        round(float(ph) * 100, 1),
        round(float(max(0, c - h)) * 100, 1),
        round(float(min(1, c + h)) * 100, 1),
    )


def _post_stratified(
    audit: pd.DataFrame, flag: str, weights: dict, z: float
) -> tuple[float, float, float, int, float]:
    """Estimador post-estratificado por clase ABC.

        p = suma_c (N_c / N) * p_c

    Devuelve (punto, ci_low, ci_high, n_efectivo, cobertura_pct).

    Por que hace falta: `stratified_sample` sobre-representa la clase A 3:1 a
    proposito, y el promedio crudo `k/n` sobre esa muestra NO es la tasa
    poblacional — es la tasa de una muestra sesgada hacia donde el error duele
    mas. En el CD sintetico la clase C tiene mas defectos que la A, asi que el
    sesgo va hacia abajo y `projected_defective_skus` subestima el trabajo de
    correccion. Muestrear con un diseno y agregar con otro es un error de una
    linea que produce un numero perfectamente creible.

    El intervalo sale de la varianza estratificada, con correccion por poblacion
    finita, convertida a un tamano efectivo que se pasa por Wilson. Se hace asi
    y no con un Wald directo porque Wilson se comporta cuando la tasa se acerca
    a 0 o a 1, que es justo donde queda una clase chica y limpia. La correccion
    finita tambien da la propiedad correcta en el limite: auditar el catalogo
    entero (censo) colapsa el intervalo a cero, que es la razon economica de
    poner un cubicador en recepcion.
    """
    n_total_pop = float(sum(weights.values()))
    p_st = var = var_srs = 0.0
    covered = 0.0

    for cls, n_c_pop in weights.items():
        sub = audit[audit["abc_class"] == cls]
        n_c = len(sub)
        if n_c == 0 or n_c_pop <= 0:
            continue  # clase de la poblacion sin representacion en la muestra
        covered += float(n_c_pop)

    if covered <= 0:
        return (0.0, 0.0, 0.0, 0, 0.0)

    for cls, n_c_pop in weights.items():
        sub = audit[audit["abc_class"] == cls]
        n_c = len(sub)
        if n_c == 0 or n_c_pop <= 0:
            continue
        # El peso se renormaliza sobre la poblacion efectivamente cubierta, y la
        # cobertura se reporta: una clase entera sin auditar es un hueco que hay
        # que ver, no un cero que se promedia.
        w = float(n_c_pop) / covered
        p_c = float(sub[flag].mean())
        fpc = max(0.0, 1.0 - n_c / float(n_c_pop))
        p_st += w * p_c
        var += w**2 * p_c * (1 - p_c) / n_c * fpc
        var_srs += w**2 * p_c * (1 - p_c) / n_c

    if var > 0 and 0 < p_st < 1:
        n_eff = p_st * (1 - p_st) / var
    elif var_srs > 0:
        # La varianza se anulo por la correccion finita y no por falta de
        # dispersion: se audito el estrato completo. Es censo, y un censo no
        # tiene error de muestreo. Colapsar el intervalo aca es lo correcto, y
        # es exactamente el retorno de convertir la auditoria manual en medicion
        # automatica: el intervalo deja de existir en vez de solo achicarse.
        return (
            round(p_st * 100, 1),
            round(p_st * 100, 1),
            round(p_st * 100, 1),
            int(covered),
            round(covered / n_total_pop * 100, 1),
        )
    else:
        # Ni dispersion ni censo: todos los estratos dieron 0% o 100%. El
        # estimador puntual existe, el intervalo se apoya en la muestra.
        n_eff = float(len(audit))
    n_eff = min(n_eff, covered)

    pt, lo, hi = _wilson(p_st * n_eff, n_eff, z)
    return (pt, lo, hi, int(round(n_eff)), round(covered / n_total_pop * 100, 1))


def audit_summary(
    audit: pd.DataFrame,
    population: int | None = None,
    confidence: float = 0.95,
    population_by_class: dict | pd.Series | None = None,
) -> dict:
    """Tasas de defecto con intervalo de confianza (Wilson).

    El intervalo importa: "18% de defectos" y "18% +-3%" son la misma medicion,
    pero solo la segunda sobrevive a la pregunta del CFO.

    `population_by_class` son los SKU de la poblacion por clase ABC. Cuando se
    pasa, la tasa se post-estratifica y deja de estar sesgada por el diseno de
    muestreo (ver `_post_stratified`). Cuando no se pasa, el resultado sigue
    siendo la tasa **de la muestra** y el campo `weighting` lo dice en voz alta
    en vez de dejar que se lea como poblacional.
    """
    n = len(audit)
    z = stats.norm.ppf(1 - (1 - confidence) / 2)

    weights = dict(population_by_class) if population_by_class is not None else None
    if weights and population is None:
        population = int(sum(weights.values()))
    stratified = bool(weights) and "abc_class" in audit

    metrics = {}
    for flag in DEFECT_FLAGS:
        k = int(audit[flag].sum())
        if stratified:
            pt, lo, hi, n_eff, coverage = _post_stratified(audit, flag, weights, z)
            metrics[flag] = {
                "defects": k,
                "rate_pct": pt,
                "ci_low_pct": lo,
                "ci_high_pct": hi,
                "sample_rate_pct": _wilson(k, n, z)[0],
                "effective_n": n_eff,
            }
        else:
            pt, lo, hi = _wilson(k, n, z)
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
        # Procedencia del agregado. Sin este campo, una tasa de muestra sesgada y
        # una tasa poblacional se ven identicas en la tabla y en el A3.
        "weighting": (
            "post-estratificado por abc_class contra la poblacion"
            if stratified
            else "SIN PONDERAR: es la tasa de la muestra. Si la muestra fue "
            "estratificada (stratified_sample sobre-representa la clase A 3:1) "
            "esta tasa NO es la poblacional. Pasar population_by_class."
        ),
        "population_coverage_pct": (
            _post_stratified(audit, "any_defect", weights, z)[4] if stratified else None
        ),
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
