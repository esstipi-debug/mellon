"""Variantes, reproceso y conformidad contra el flujo declarado.

Regla de terreno: el flujo que te describen en el kickoff cubre entre el 40% y
el 60% de los casos. El resto son las "excepciones que casi no pasan". Este
modulo te da el numero exacto antes de que prometas nada.
"""

from __future__ import annotations

import pandas as pd

from .log import EventLog


def variants(log: EventLog, top: int | None = 15, collapse_repeats: bool = False) -> pd.DataFrame:
    """Variantes de proceso ordenadas por frecuencia.

    collapse_repeats colapsa repeticiones consecutivas de la misma actividad
    (PICK, PICK, PICK -> PICK), util cuando el log es a nivel de linea y la
    cantidad de lineas por pedido infla artificialmente las variantes.
    """
    tr = log.traces()
    if collapse_repeats:
        tr = tr.apply(_collapse)

    counts = tr.value_counts()
    out = pd.DataFrame(
        {
            "variant": [" -> ".join(t) for t in counts.index],
            "n_events": [len(t) for t in counts.index],
            "cases": counts.to_numpy(),
        }
    )
    out["pct"] = (out["cases"] / log.n_cases * 100).round(2)
    out["cum_pct"] = out["pct"].cumsum().round(2)
    return out.head(top).reset_index(drop=True) if top else out.reset_index(drop=True)


def _collapse(trace: tuple) -> tuple:
    out: list[str] = []
    for a in trace:
        if not out or out[-1] != a:
            out.append(a)
    return tuple(out)


def rework_summary(log: EventLog, rework_activities: list[str] | None = None) -> pd.DataFrame:
    """Cuantifica el reproceso: cuantos casos lo sufren y cuanto cuesta.

    Si no se pasa la lista, se infiere por nombre (REWORK/REPACK/REPICK/EXCEPTION/
    SHORT/FAIL) mas cualquier actividad que se repita dentro del mismo caso mas
    de lo esperado.
    """
    df = log.df
    if rework_activities is None:
        pat = r"REWORK|REPACK|REPICK|EXCEPTION|SHORT|FAIL|RETURN"
        rework_activities = [a for a in log.activities if pd.Series([a]).str.contains(pat).iloc[0]]

    rows = []
    for act in rework_activities:
        sub = df[df["activity"] == act]
        cases = sub["case_id"].nunique()
        rows.append(
            {
                "activity": act,
                "occurrences": len(sub),
                "cases_affected": cases,
                "pct_cases": round(cases / log.n_cases * 100, 2),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    # Costo directo: el tiempo que la propia actividad agrega, medido como el
    # delta contra el evento anterior del mismo caso.
    #
    # Tentacion a evitar: comparar el tiempo de ciclo de los casos CON la
    # actividad contra los casos SIN ella. Esa comparacion esta confundida por
    # la hora de liberacion y la cantidad de lineas, y en un CD saturado llega a
    # dar penalizaciones negativas — o sea, "el reproceso acelera el pedido".
    # Cuando un numero contradice la fisica, el numero esta mal, no la fisica.
    prev = df.shift(1)
    same = df["case_id"] == prev["case_id"]
    dur = pd.DataFrame(
        {
            "activity": df["activity"],
            "dur_s": (df["timestamp"] - prev["timestamp"]).dt.total_seconds(),
        }
    )[same]
    med = dur.groupby("activity")["dur_s"].median()

    out["direct_cost_s"] = out["activity"].map(med).round(1)
    out["hours_lost_in_window"] = (out["occurrences"] * out["direct_cost_s"] / 3600).round(2)
    out["annual_hours_lost"] = (out["hours_lost_in_window"] * 250).round(0)
    return out.sort_values("annual_hours_lost", ascending=False).reset_index(drop=True)


def conformance(log: EventLog, declared: list[str], collapse_repeats: bool = True) -> dict:
    """Conformidad contra el flujo declarado en el kickoff.

    Devuelve el % de casos que siguen exactamente el flujo declarado, y las
    actividades que aparecen en la realidad pero no en el discurso.
    """
    tr = log.traces()
    if collapse_repeats:
        tr = tr.apply(_collapse)
        declared_t = _collapse(tuple(declared))
    else:
        declared_t = tuple(declared)

    exact = int((tr == declared_t).sum())
    observed = set(log.activities)
    undeclared = sorted(observed - set(declared))
    unused = sorted(set(declared) - observed)

    return {
        "declared_flow": " -> ".join(declared_t),
        "cases": log.n_cases,
        "conforming_cases": exact,
        "conformance_pct": round(exact / log.n_cases * 100, 2),
        "undeclared_activities": undeclared,
        "declared_but_never_seen": unused,
        "n_distinct_variants": int(tr.nunique()),
    }


def pareto_coverage(log: EventLog, target_pct: float = 80.0) -> dict:
    """Cuantas variantes hacen falta para cubrir el target_pct de los casos.

    Es el numero que decide el alcance del piloto: automatizar la variante 1
    cubre el 45%; llegar al 80% puede costar 14 variantes mas."""
    v = variants(log, top=None, collapse_repeats=True)
    n = int((v["cum_pct"] < target_pct).sum()) + 1
    return {
        "target_pct": target_pct,
        "variants_needed": min(n, len(v)),
        "total_variants": len(v),
        "top_variant_pct": float(v.loc[0, "pct"]),
    }
