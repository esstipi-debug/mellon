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


def parallel_trends_check(df: pd.DataFrame, value: str, group: str, time: str, cutoff) -> dict:
    """Chequeo de tendencias paralelas en el periodo pre.

    Si los dos grupos ya venian divergiendo antes del cambio, DiD no es valido y
    hay que decirlo antes de que lo diga el analista del cliente.
    """
    pre = df[df[time] < cutoff]
    slopes = {}
    for g in ("control", "treat"):
        sub = pre[pre[group] == g]
        x = pd.to_numeric(pd.to_datetime(sub[time])).to_numpy(dtype=float) / 8.64e13
        y = sub[value].astype(float).to_numpy()
        if len(x) < 3:
            return {"valid": False, "reason": "muy pocos puntos en el periodo pre"}
        slopes[g] = float(np.polyfit(x, y, 1)[0])

    diff = slopes["treat"] - slopes["control"]
    scale = abs(pre[value].astype(float).mean()) or 1.0
    ok = abs(diff) / scale < 0.02
    return {
        "slope_treat_per_day": round(slopes["treat"], 4),
        "slope_control_per_day": round(slopes["control"], 4),
        "divergence_per_day": round(diff, 4),
        "parallel_trends_ok": bool(ok),
        "reason": "" if ok else "los grupos ya divergian antes del cambio: DiD sesgado",
    }
