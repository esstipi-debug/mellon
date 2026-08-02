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


def _rework_consequences(
    df: pd.DataFrame,
    direct: list[str],
    threshold: float,
    min_occurrences: int = 5,
) -> list[str]:
    """Actividades que no se llaman reproceso pero solo existen por el.

    El caso que motiva la regla: un `SHORT_PICK` cuesta 50 segundos de registro y
    dispara un `REPLENISH` de ocho minutos que retiene al picker. El nombre no
    matchea ningun patron de reproceso, asi que esas horas se caian enteras del
    caso economico mientras la tabla mostraba el SHORT_PICK como un problema
    menor. Es la clase de error que no falla: muestra un numero chico y creible.

    La regla es general y no depende de la jerga del cliente: si casi todas las
    ocurrencias de una actividad vienen inmediatamente despues de un reproceso
    dentro del mismo caso, esa actividad es parte de la cadena. El umbral
    discrimina bien porque una actividad de flujo normal aparece tambien en los
    casos sanos — PACK sigue a CARTON_REWORK 246 veces sobre 1.046, o sea 0,24,
    muy lejos del corte.

    `min_occurrences` evita que una coincidencia sobre dos eventos arrastre una
    actividad entera al caso economico. El 5 es el mismo criterio de celda minima
    que usa `stats.risk_ratio_2x2`.
    """
    if not direct:
        return []

    prev = df.shift(1)
    same = df["case_id"] == prev["case_id"]
    chain = pd.DataFrame(
        {
            "activity": df["activity"],
            "after_rework": same & prev["activity"].isin(direct),
        }
    )
    chain = chain[~chain["activity"].isin(direct)]
    if chain.empty:
        return []

    g = chain.groupby("activity")["after_rework"]
    share, n = g.mean(), g.size()
    return sorted(share.index[(share >= threshold) & (n >= min_occurrences)])


def rework_summary(
    log: EventLog,
    rework_activities: list[str] | None = None,
    consequence_threshold: float = 0.9,
) -> pd.DataFrame:
    """Cuantifica el reproceso: cuantos casos lo sufren y cuanto cuesta.

    Si no se pasa la lista, se infiere en dos pasos:

    1. **directa** — por nombre (REWORK/REPACK/REPICK/EXCEPTION/SHORT/FAIL/RETURN).
    2. **consecuencia** — actividades que solo aparecen despues de una directa,
       detectadas por `_rework_consequences`. Sin este paso el costo real de un
       reproceso queda registrado bajo el nombre de su consecuencia y no llega a
       ninguna palanca.

    La columna `rework_kind` deja ver de cual de los dos pasos vino cada fila:
    la de consecuencia es una inferencia y hay que poder discutirla en la sala.

    Pasar `rework_activities` explicito desactiva la deteccion entera. Si el FDE
    ya mapeo la taxonomia del cliente, adivinar encima seria peor.

    Cuidado con la lectura de una consecuencia: su duracion es el retraso que
    inserta en el caso. Es tiempo de operador perdido solo si el operador espera
    —que es lo normal en un quiebre de picking— y no si se va a otra tarea.
    """
    df = log.df
    if rework_activities is None:
        pat = r"REWORK|REPACK|REPICK|EXCEPTION|SHORT|FAIL|RETURN"
        direct = [a for a in log.activities if pd.Series([a]).str.contains(pat).iloc[0]]
        consequences = _rework_consequences(df, direct, consequence_threshold)
    else:
        direct, consequences = list(rework_activities), []

    rows = []
    tagged = [(a, "directa") for a in direct] + [(a, "consecuencia") for a in consequences]
    for act, kind in tagged:
        sub = df[df["activity"] == act]
        cases = sub["case_id"].nunique()
        rows.append(
            {
                "activity": act,
                "rework_kind": kind,
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
    out["hours_lost_in_window"] = (out["occurrences"] * out["direct_cost_s"] / 3600).round(4)
    # Unidad de salida: la ventana observada. `annual_hours_lost` vivia aca con
    # un 250 hardcodeado y `value/levers.py` volvia a escalar por
    # `annual_orders / (pedidos_observados * operating_days)`: los dos factores
    # se cancelaban salvo por un residuo de 250/operating_days que nadie veia.
    # La anualizacion es una sola, y va donde estan los dias del arquetipo.
    out["cases_in_window"] = log.n_cases
    return out.sort_values("hours_lost_in_window", ascending=False).reset_index(drop=True)


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
