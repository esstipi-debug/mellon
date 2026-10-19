"""Grafico XmR (individuales y rango movil) con las reglas de Nelson.

Por que XmR y no un umbral fijo: un umbral fijo genera falsas alarmas cuando el
proceso solo esta variando normalmente, y el equipo aprende a ignorarlo en tres
semanas. El grafico de control distingue ruido de senal, que es exactamente lo
que hace falta para llamar al cliente ANTES de que el llame.

Regla dura: los limites se calculan sobre la ventana de linea base estable y se
CONGELAN. Recalcularlos cada semana hace que el proceso se degrade sin que el
grafico lo note — es el error mas comun de quien implementa SPC por primera vez.

`degradation_alarm` hace cumplir la primera mitad: chequea la linea base antes de
fijar limites y se niega si una ola o un corrimiento la ensucian.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

D2_N2 = 1.128  # constante de rango movil para n=2
E2_N2 = 2.66  # 3 / d2
D4_N2 = 3.267


@dataclass
class ControlLimits:
    center: float
    ucl: float
    lcl: float
    sigma: float
    mr_bar: float
    mr_ucl: float
    n_baseline: int

    def as_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def compute_limits(values, lcl_floor: float | None = None) -> ControlLimits:
    x = np.asarray(values, float)
    x = x[~np.isnan(x)]
    if len(x) < 8:
        raise ValueError("se necesitan al menos 8 puntos de linea base para limites creibles")

    mr = np.abs(np.diff(x))
    mr_bar = float(mr.mean())
    center = float(x.mean())
    sigma = mr_bar / D2_N2
    ucl = center + E2_N2 * mr_bar
    lcl = center - E2_N2 * mr_bar
    if lcl_floor is not None:
        lcl = max(lcl, lcl_floor)

    return ControlLimits(center, ucl, lcl, sigma, mr_bar, D4_N2 * mr_bar, len(x))


def xmr_chart(values, limits: ControlLimits | None = None, lcl_floor: float | None = None) -> pd.DataFrame:
    """Serie con limites y zonas sigma. Si no se pasan limites, se calculan
    sobre la misma serie (solo valido para el analisis inicial de estabilidad)."""
    x = np.asarray(values, float)
    lim = limits or compute_limits(x, lcl_floor)

    df = pd.DataFrame({"i": np.arange(len(x)), "value": x})
    df["mr"] = np.concatenate([[np.nan], np.abs(np.diff(x))])
    df["center"] = lim.center
    df["ucl"] = lim.ucl
    df["lcl"] = lim.lcl
    df["zone"] = np.floor(np.abs(x - lim.center) / lim.sigma).clip(0, 3)
    df["side"] = np.sign(x - lim.center)
    return df


def nelson_rules(values, limits: ControlLimits) -> pd.DataFrame:
    """Aplica las ocho reglas de Nelson. Devuelve una fila por violacion.

    En operaciones las que mas sirven son la 1 (fuera de control), la 2 (corrimiento
    sostenido) y la 3 (tendencia) — las otras cinco generan mas conversacion que
    accion, pero se calculan igual porque cuestan cero.
    """
    x = np.asarray(values, float)
    c, s = limits.center, limits.sigma
    n = len(x)
    hits: list[dict] = []

    def add(rule: int, i: int, desc: str):
        hits.append({"rule": rule, "index": int(i), "value": float(x[i]), "description": desc})

    dev = x - c
    z = dev / s if s else np.zeros_like(dev)

    for i in range(n):
        if abs(z[i]) > 3:
            add(1, i, "punto fuera de los limites de control (>3 sigma)")

    def run_same_side(k: int, rule: int, desc: str):
        for i in range(k - 1, n):
            w = np.sign(dev[i - k + 1 : i + 1])
            if np.all(w > 0) or np.all(w < 0):
                add(rule, i, desc)

    run_same_side(9, 2, "9 puntos consecutivos del mismo lado: el proceso se corrio")

    for i in range(5, n):
        w = x[i - 5 : i + 1]
        d = np.diff(w)
        if np.all(d > 0):
            add(3, i, "6 puntos consecutivos en ascenso: tendencia")
        elif np.all(d < 0):
            add(3, i, "6 puntos consecutivos en descenso: tendencia")

    for i in range(13, n):
        d = np.diff(x[i - 13 : i + 1])
        if np.all(d[:-1] * d[1:] < 0):
            add(4, i, "14 puntos alternando: probable sobre-ajuste del operador")

    for i in range(2, n):
        w = z[i - 2 : i + 1]
        for sign in (1, -1):
            if np.sum(w * sign > 2) >= 2 and (z[i] * sign > 2):
                add(5, i, "2 de 3 puntos mas alla de 2 sigma del mismo lado")
                break

    for i in range(4, n):
        w = z[i - 4 : i + 1]
        for sign in (1, -1):
            if np.sum(w * sign > 1) >= 4 and (z[i] * sign > 1):
                add(6, i, "4 de 5 puntos mas alla de 1 sigma del mismo lado")
                break

    for i in range(14, n):
        if np.all(np.abs(z[i - 14 : i + 1]) < 1):
            add(7, i, "15 puntos dentro de 1 sigma: variacion sospechosamente baja")

    for i in range(7, n):
        if np.all(np.abs(z[i - 7 : i + 1]) > 1):
            add(8, i, "8 puntos consecutivos mas alla de 1 sigma a ambos lados")

    out = pd.DataFrame(hits)
    if out.empty:
        return pd.DataFrame(columns=["rule", "index", "value", "description"])
    return out.drop_duplicates(subset=["rule", "index"]).sort_values(["index", "rule"]).reset_index(drop=True)


# Reglas que descalifican una linea base: un punto fuera de limites, un corrimiento
# sostenido o una tendencia.
BASELINE_RULES = (1, 2, 3)

# Fraccion maxima de la linea base que puede marcar esas reglas. Medido sobre
# procesos estables: con 30 puntos i.i.d. alguna de ellas dispara en el 14% de las
# corridas, pero la fraccion de puntos marcados supera 0,2 en 0 de 4000 corridas;
# con autocorrelacion AR(1) de 0,5 supera 1/3 en el 0,6%. Una ola, un escalon o una
# tendencia la llevan a 0,5-1,0. La regla literal ("alguna dispara") negaria el 14%
# de los procesos i.i.d. y el 62% de los de autocorrelacion 0,5.
MAX_BASELINE_FLAGGED_FRACTION = 1 / 3


def baseline_stability(baseline) -> dict:
    """Chequea la linea base antes de fijarle limites.

    Los limites salen de la misma serie que se chequea, asi que las reglas se
    evaluan con los limites de la propia linea base. Un punto suelto no la invalida:
    lo que la invalida es que la marque una fraccion grande, porque entonces los
    limites describen esa forma (la ola, el escalon) y el monitoreo se juzgaria
    contra la forma equivocada.
    """
    x = np.asarray(baseline, float)
    x = x[~np.isnan(x)]
    viol = nelson_rules(x, compute_limits(x))
    criticas = viol[viol["rule"].isin(BASELINE_RULES)] if not viol.empty else viol
    marcados = int(criticas["index"].nunique()) if not criticas.empty else 0
    fraccion = marcados / len(x)
    return {
        "stable": fraccion <= MAX_BASELINE_FLAGGED_FRACTION,
        "n": len(x),
        "points_flagged": marcados,
        "fraction_flagged": round(fraccion, 3),
        "detail": criticas.to_dict("records"),
    }


def degradation_alarm(
    baseline, monitoring, direction: str = "lower_is_better", lcl_floor: float | None = None
) -> dict:
    """Monitor de degradacion post go-live.

    Congela limites sobre la linea base y evalua la ventana de monitoreo. El
    veredicto distingue tres casos que el cliente confunde todo el tiempo:
    mejora sostenida, ruido, y degradacion real.

    Antes de fijar limites chequea la linea base (`baseline_stability`). Si una ola
    o un corrimiento la ensucian, no fija nada: `limits` queda en None, el veredicto
    es 'SIN LIMITES' con las reglas que la marcaron en `baseline_detail`, y el
    monitoreo no se juzga.
    """
    base = baseline_stability(baseline)
    m = np.asarray(monitoring, float)
    chequeo = {
        "baseline_stable": base["stable"],
        "baseline_fraction_flagged": base["fraction_flagged"],
        "baseline_points_flagged": base["points_flagged"],
        "baseline_detail": base["detail"],
    }
    if not base["stable"]:
        return {
            **chequeo,
            "limits": None,
            "monitoring_mean": round(float(np.mean(m)), 3),
            "shift_vs_baseline": None,
            "shift_sigmas": None,
            "violations": None,
            "critical_violations": None,
            "first_critical_index": None,
            "verdict": (
                f"SIN LIMITES: {base['points_flagged']} de {base['n']} puntos de la linea "
                "base disparan las reglas 1-3 de Nelson. Los limites saldrian de la ola o "
                "del corrimiento y describirian eso, no el proceso. No hay veredicto de "
                "degradacion hasta tener una linea base estable."
            ),
            "detail": [],
        }

    lim = compute_limits(baseline, lcl_floor)
    viol = nelson_rules(monitoring, lim)

    bad_side = 1 if direction == "higher_is_better" else -1
    # Un corrimiento "malo" es hacia arriba si menor es mejor.
    worse = -bad_side

    shift = float(np.mean(m) - lim.center)
    drifted_wrong_way = np.sign(shift) == worse

    critical = viol[viol["rule"].isin([1, 2, 3])] if not viol.empty else viol

    if critical.empty:
        verdict = "en control"
    elif drifted_wrong_way:
        verdict = "DEGRADACION: llamar al cliente antes de que llame el"
    else:
        verdict = "cambio favorable sostenido: documentarlo y mover la linea base"

    return {
        **chequeo,
        "limits": lim.as_dict(),
        "monitoring_mean": round(float(np.mean(m)), 3),
        "shift_vs_baseline": round(shift, 3),
        "shift_sigmas": round(shift / lim.sigma, 2) if lim.sigma else float("nan"),
        "violations": int(len(viol)),
        "critical_violations": int(len(critical)),
        "first_critical_index": int(critical["index"].min()) if not critical.empty else None,
        "verdict": verdict,
        "detail": viol.to_dict("records"),
    }


def plot_xmr(values, limits: ControlLimits | None = None, title: str = "", path: str | None = None):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lim = limits or compute_limits(values)
    df = xmr_chart(values, lim)
    viol = nelson_rules(values, lim)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True, height_ratios=[2, 1])
    ax1.plot(df["i"], df["value"], marker="o", ms=3.5, lw=1, color="#2c3e50")
    ax1.axhline(lim.center, color="#27ae60", lw=1.2)
    ax1.axhline(lim.ucl, color="#c0392b", ls="--", lw=1)
    ax1.axhline(lim.lcl, color="#c0392b", ls="--", lw=1)
    if not viol.empty:
        v = viol[viol["rule"].isin([1, 2, 3])]
        ax1.scatter(v["index"], v["value"], s=70, facecolors="none", edgecolors="#c0392b", lw=1.6)
    ax1.set_ylabel("individuales")
    ax1.set_title(title or "Grafico XmR con reglas de Nelson")

    ax2.plot(df["i"], df["mr"], marker="o", ms=3, lw=1, color="#7f8c8d")
    ax2.axhline(lim.mr_bar, color="#27ae60", lw=1.2)
    ax2.axhline(lim.mr_ucl, color="#c0392b", ls="--", lw=1)
    ax2.set_ylabel("rango movil")
    ax2.set_xlabel("observacion")

    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
        plt.close(fig)
    return fig
