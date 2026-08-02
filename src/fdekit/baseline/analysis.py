"""Analisis pre/post con y sin grupo de control.

Sin grupo de control, un pre/post mide el efecto del proyecto *mas* la
estacionalidad, la curva de aprendizaje, el clima y la contratacion de noviembre.
Con grupo de control, diferencias-en-diferencias separa lo tuyo de lo demas. Es
la diferencia entre un caso de renovacion y una discusion.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def bootstrap_ci(
    a, b, stat=np.median, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0
) -> dict:
    """IC bootstrap para la diferencia de un estadistico entre dos muestras.

    Se usa la mediana por defecto: los tiempos de ciclo tienen colas que hacen
    del promedio una metrica que el supervisor no reconoce como suya.
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(a, float)
    a = a[~np.isnan(a)]
    b = np.asarray(b, float)
    b = b[~np.isnan(b)]

    obs = float(stat(b) - stat(a))
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = stat(rng.choice(b, b.size, replace=True)) - stat(
            rng.choice(a, a.size, replace=True)
        )
    lo, hi = np.percentile(diffs, [alpha / 2 * 100, (1 - alpha / 2) * 100])

    base = float(stat(a))
    return {
        "pre": round(base, 3),
        "post": round(float(stat(b)), 3),
        "delta": round(obs, 3),
        "delta_pct": round(obs / base * 100, 2) if base else float("nan"),
        "ci_low": round(float(lo), 3),
        "ci_high": round(float(hi), 3),
        "significant": bool(lo > 0 or hi < 0),
    }


def pre_post(pre, post, alpha: float = 0.05) -> dict:
    """Comparacion pre/post sin control. Reportar SIEMPRE con la advertencia."""
    pre = np.asarray(pre, float)
    pre = pre[~np.isnan(pre)]
    post = np.asarray(post, float)
    post = post[~np.isnan(post)]

    t, p = stats.ttest_ind(post, pre, equal_var=False)
    u, pu = stats.mannwhitneyu(post, pre, alternative="two-sided")

    pooled = np.sqrt((pre.var(ddof=1) + post.var(ddof=1)) / 2)
    d = (post.mean() - pre.mean()) / pooled if pooled else float("nan")

    out = bootstrap_ci(pre, post, alpha=alpha)
    out.update(
        {
            "n_pre": int(pre.size),
            "n_post": int(post.size),
            "welch_t": round(float(t), 3),
            "welch_p": float(f"{p:.3g}"),
            "mannwhitney_p": float(f"{pu:.3g}"),
            "cohens_d": round(float(d), 3),
            "warning": (
                "Sin grupo de control este delta incluye estacionalidad, curva de "
                "aprendizaje y cualquier otro cambio simultaneo. No atribuir al "
                "proyecto sin un contrafactual."
            ),
        }
    )
    return out


def diff_in_diff(df: pd.DataFrame, value: str, group: str, period: str) -> dict:
    """Diferencias-en-diferencias.

    `group` debe tener valores "treat"/"control"; `period` valores "pre"/"post".
    Devuelve el estimador DiD, su error estandar y el IC. Es la estimacion que
    hay que llevar a la reunion de renovacion.
    """
    cells = {}
    for g in ("control", "treat"):
        for p in ("pre", "post"):
            v = df.loc[(df[group] == g) & (df[period] == p), value].astype(float).dropna()
            if v.empty:
                raise ValueError(f"celda vacia: {g}/{p}")
            cells[(g, p)] = v

    means = {k: float(v.mean()) for k, v in cells.items()}
    did = (means[("treat", "post")] - means[("treat", "pre")]) - (
        means[("control", "post")] - means[("control", "pre")]
    )
    var = sum(float(v.var(ddof=1)) / v.size for v in cells.values())
    se = float(np.sqrt(var))

    # Varianza cero significa que las celdas no tienen dispersion: datos
    # sinteticos, o agregados tan grueso que quedo una observacion por celda.
    # Sin dispersion no hay inferencia posible, y devolver p=0 seria afirmar
    # certeza absoluta a partir de la ausencia de datos.
    testable = se > 0 and all(v.size > 1 for v in cells.values())
    z = did / se if testable else float("nan")
    p = 2 * (1 - stats.norm.cdf(abs(z))) if testable else float("nan")

    pre_treat = means[("treat", "pre")]
    return {
        "means": {f"{g}_{p}": round(v, 3) for (g, p), v in means.items()},
        "naive_pre_post_delta": round(means[("treat", "post")] - pre_treat, 3),
        "did_estimate": round(did, 3),
        "did_pct_of_baseline": round(did / pre_treat * 100, 2) if pre_treat else float("nan"),
        "se": round(se, 3),
        "ci_low": round(did - 1.96 * se, 3) if testable else None,
        "ci_high": round(did + 1.96 * se, 3) if testable else None,
        "p_value": float(f"{p:.3g}") if testable else None,
        "significant": bool(testable and abs(z) > 1.96),
        "testable": bool(testable),
        "warning_varianza": (
            ""
            if testable
            else "varianza cero o una sola observacion por celda: el estimador puntual "
            "existe pero NO es contrastable. Reportarlo como significativo seria afirmar "
            "certeza a partir de la ausencia de dispersion."
        ),
        "reading": (
            "El delta naive pre/post sobreestima o subestima el efecto segun lo que "
            "hizo el control en la misma ventana. El estimador DiD es el que se reporta."
        ),
    }


def _slope_with_se(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Pendiente de una regresion simple y su error estandar."""
    n = len(x)
    slope, intercept = np.polyfit(x, y, 1)
    sxx = float(((x - x.mean()) ** 2).sum())
    if n <= 2 or sxx <= 0:
        return float(slope), float("inf")
    resid = y - (slope * x + intercept)
    s2 = float((resid**2).sum()) / (n - 2)
    return float(slope), float(np.sqrt(s2 / sxx))


def parallel_trends_check(
    df: pd.DataFrame,
    value: str,
    group: str,
    time: str,
    cutoff,
    alpha: float = 0.05,
    materiality: float = 0.02,
    min_periods: int = 3,
) -> dict:
    """Chequeo de tendencias paralelas en el periodo pre.

    Si los dos grupos ya venian divergiendo antes del cambio, DiD no es valido y
    hay que decirlo antes de que lo diga el analista del cliente.

    DOS CORRECCIONES SOBRE LA VERSION QUE NUNCA SE CORRIA:

    1. **Se agrega a nivel de periodo antes de ajustar.** La version anterior
       ajustaba la recta sobre las filas crudas y contaba filas para decidir si
       tenia puntos suficientes: con un panel de pedidos veia 2.100 "puntos"
       donde habia 3 dias. Tendencias paralelas es una propiedad de la media del
       grupo a lo largo del tiempo, no de cada pedido.

    2. **La divergencia se contrasta contra su error estandar.** Sin eso, la
       funcion emitia un veredicto categorico desde tres dias de un proceso cuya
       mediana diaria se mueve 30%, y el ruido salia como "DiD sesgado" — un
       falso positivo que descarta el unico estimador que se puede defender.

    Por eso el resultado tiene DOS banderas y no una:

        parallel_trends_ok   no se detecto divergencia material y significativa
        conclusive           el diseno tenia con que detectarla

    `ok=True` con `conclusive=False` significa "no encontre divergencia y
    tampoco podria haberla encontrado". Es ausencia de evidencia, no evidencia
    de ausencia, y colapsar las dos cosas en un solo booleano es exactamente
    como se firma un DiD que el analista del cliente despues rompe.
    """
    d = df.copy()
    d[time] = pd.to_datetime(d[time])
    pre = d[d[time] < pd.Timestamp(cutoff)]
    scale = abs(pre[value].astype(float).mean()) if len(pre) else 0.0
    scale = scale or 1.0

    slopes: dict[str, float] = {}
    ses: dict[str, float] = {}
    periods: dict[str, int] = {}
    dfs: dict[str, int] = {}
    for g in ("control", "treat"):
        sub = pre[pre[group] == g]
        # Una fila por periodo: la media del grupo en ese dia.
        daily = sub.groupby(time)[value].mean().sort_index()
        periods[g] = int(len(daily))
        if len(daily) < min_periods:
            return {
                "slope_treat_per_day": None,
                "slope_control_per_day": None,
                "divergence_per_day": None,
                "se_divergence_per_day": None,
                "n_periods_pre": periods,
                "parallel_trends_ok": None,
                "conclusive": False,
                "reason": (
                    f"solo {len(daily)} periodo(s) pre en el grupo '{g}': hacen falta "
                    f"al menos {min_periods} para estimar una tendencia. El supuesto "
                    "queda SIN VERIFICAR, que no es lo mismo que verificado."
                ),
            }
        x = pd.to_numeric(daily.index).to_numpy(dtype=float) / 8.64e13
        slopes[g], ses[g] = _slope_with_se(x, daily.to_numpy(dtype=float))
        dfs[g] = len(daily) - 2

    diff = slopes["treat"] - slopes["control"]
    se = float(np.sqrt(ses["control"] ** 2 + ses["treat"] ** 2))

    # Critico t, no normal. Con tres dias por grupo la pendiente tiene UN grado
    # de libertad, y un z=1,96 sobre una varianza estimada con 1 g.l. rechaza
    # ruido como si fuera senal: es la misma clase de error que `diff_in_diff`
    # ya corrigio cuando devolvia p=0 con varianza cero. Grados de libertad de
    # la diferencia por Welch-Satterthwaite, que es lo correcto cuando los dos
    # grupos tienen ventanas pre distintas.
    num = (ses["control"] ** 2 + ses["treat"] ** 2) ** 2
    den = sum(ses[g] ** 4 / dfs[g] for g in ("control", "treat") if dfs[g] > 0)
    dof = num / den if den > 0 and np.isfinite(num) else 0.0
    crit = float(stats.t.ppf(1 - alpha / 2, dof)) if dof > 0 else float("inf")
    z = crit

    significant = bool(np.isfinite(se) and se > 0 and np.isfinite(crit) and abs(diff) > crit * se)
    material = bool(abs(diff) / scale >= materiality)
    ok = not (significant and material)

    # Divergencia mas chica que este diseno podria haber detectado, en % de la
    # metrica por dia. Es el MDE del chequeo, con la misma logica que
    # `design.required_days`: si supera el umbral de materialidad, el chequeo no
    # tenia con que fallar y su "ok" no significa nada.
    detectable = z * se / scale if np.isfinite(se) else float("inf")
    conclusive = bool(detectable <= materiality)

    if significant and material:
        reason = "los grupos ya divergian antes del cambio: DiD sesgado"
    elif not conclusive:
        reason = (
            f"sin divergencia detectada, pero el diseno solo podia detectar una de "
            f"{detectable:.1%} por dia contra un umbral de {materiality:.1%}: el "
            f"supuesto NO quedo verificado. Alargar la ventana pre "
            f"(hoy {periods['treat']} y {periods['control']} periodos) antes de "
            "presentar el DiD como limpio."
        )
    else:
        reason = ""

    return {
        "slope_treat_per_day": round(slopes["treat"], 4),
        "slope_control_per_day": round(slopes["control"], 4),
        "divergence_per_day": round(diff, 4),
        "se_divergence_per_day": round(se, 4) if np.isfinite(se) else None,
        "dof": round(dof, 2),
        "detectable_divergence_pct_per_day": (
            round(detectable * 100, 2) if np.isfinite(detectable) else None
        ),
        "n_periods_pre": periods,
        "parallel_trends_ok": bool(ok),
        "conclusive": conclusive,
        "reason": reason,
    }
