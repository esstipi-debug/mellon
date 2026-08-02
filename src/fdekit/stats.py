"""Estadistica compartida del kit.

Existe por una razon concreta: el 2x2 de riesgo relativo vivia enterrado dentro
de `dataquality.link_defects_to_rework`, y `decide.metrics` necesita exactamente
el mismo calculo para otra pregunta (si un compromiso cuyo dueno no estaba
cuando se decidio se cumple menos). Copiarlo habria producido dos versiones que
se desincronizan; extraerlo cuesta cuarenta lineas.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as _st


def risk_ratio_2x2(a: int, b: int, c: int, d: int) -> dict:
    """Tabla 2x2 de exposicion contra resultado.

        a  expuestos CON el resultado        b  expuestos SIN el resultado
        c  no expuestos CON el resultado     d  no expuestos SIN el resultado

    Devuelve riesgo relativo, chi-cuadrado, p, y la fraccion atribuible en la
    poblacion — cuanto del resultado total desaparece si se elimina la
    exposicion. El PAF es el numero que se lleva a la reunion: dice cuanto se
    gana arreglando la causa, no solo que la causa existe.
    """
    n_exp, n_unexp = a + b, c + d
    r_exp = a / n_exp if n_exp else 0.0
    r_unexp = c / n_unexp if n_unexp else 0.0
    total = a + c
    n = n_exp + n_unexp
    rate = total / n if n else 0.0

    rr = (r_exp / r_unexp) if r_unexp > 0 else (float("inf") if r_exp > 0 else float("nan"))
    paf = ((rate - r_unexp) / rate) if rate > 0 else 0.0

    table = np.array([[c, d], [a, b]])
    if table.min() < 0 or table.sum() == 0 or (table.sum(axis=0) == 0).any() or (table.sum(axis=1) == 0).any():
        chi2, pval = float("nan"), float("nan")
    else:
        chi2, pval, _, _ = _st.chi2_contingency(table)

    return {
        "expuestos": n_exp,
        "no_expuestos": n_unexp,
        "tasa_expuestos_pct": round(r_exp * 100, 1),
        "tasa_no_expuestos_pct": round(r_unexp * 100, 1),
        "risk_ratio": round(rr, 2) if np.isfinite(rr) else rr,
        "chi2": round(float(chi2), 1) if np.isfinite(chi2) else None,
        "p_value": float(f"{pval:.3g}") if np.isfinite(pval) else None,
        "population_attributable_fraction_pct": round(paf * 100, 1),
        # Con celdas chicas el chi-cuadrado no es confiable y decirlo importa
        # mas que el numero: un p-valor sobre 12 observaciones es decoracion.
        "muestra_suficiente": bool(min(a, b, c, d) >= 5),
    }
