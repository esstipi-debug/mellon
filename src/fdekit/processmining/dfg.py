"""Grafo de sucesion directa (directly-follows graph) y deteccion de cuellos.

El DFG es el VSM automatico. Cada arista lleva dos numeros: cuantas veces ocurre
y cuanto tiempo se pierde ahi. El segundo es el que importa: el cuello de botella
casi nunca es la actividad mas lenta, es la espera *antes* de ella.
"""

from __future__ import annotations

import pandas as pd

from .log import EventLog


def directly_follows(log: EventLog) -> pd.DataFrame:
    """Aristas del DFG con frecuencia y estadistica de espera.

    Columnas: source, target, freq, cases, mean_wait_s, median_wait_s, p90_wait_s,
    total_wait_h.
    """
    df = log.df
    nxt = df.shift(-1)
    same_case = df["case_id"] == nxt["case_id"]

    pairs = pd.DataFrame(
        {
            "case_id": df["case_id"],
            "source": df["activity"],
            "target": nxt["activity"],
            "wait_s": (nxt["timestamp"] - df["timestamp"]).dt.total_seconds(),
        }
    )[same_case]

    g = pairs.groupby(["source", "target"])
    out = pd.DataFrame(
        {
            "freq": g.size(),
            "cases": g["case_id"].nunique(),
            "mean_wait_s": g["wait_s"].mean().round(1),
            "median_wait_s": g["wait_s"].median().round(1),
            "p90_wait_s": g["wait_s"].quantile(0.90).round(1),
            "total_wait_h": (g["wait_s"].sum() / 3600).round(2),
        }
    ).reset_index()

    return out.sort_values("freq", ascending=False).reset_index(drop=True)


def bottlenecks(log: EventLog, top: int = 8) -> pd.DataFrame:
    """Ranking de aristas por tiempo total perdido, no por duracion unitaria.

    Teoria de Restricciones aplicada al log: mejorar una transicion que solo
    ocurre en el 2% de los casos es gasto puro, por lenta que sea.
    """
    dfg = directly_follows(log)
    total = dfg["total_wait_h"].sum()
    dfg = dfg.copy()
    dfg["pct_of_total_wait"] = (dfg["total_wait_h"] / total * 100).round(1)
    dfg["transition"] = dfg["source"] + " -> " + dfg["target"]
    cols = [
        "transition",
        "freq",
        "median_wait_s",
        "p90_wait_s",
        "total_wait_h",
        "pct_of_total_wait",
    ]
    return dfg.sort_values("total_wait_h", ascending=False).head(top)[cols].reset_index(drop=True)


def activity_durations(log: EventLog, starts_with: dict[str, str] | None = None) -> pd.DataFrame:
    """Duracion atribuida a cada actividad = tiempo desde el evento anterior
    del mismo caso. Es una aproximacion valida cuando el log solo trae el
    timestamp de termino, que es el caso del 90% de los WMS."""
    df = log.df
    prev = df.shift(1)
    same = df["case_id"] == prev["case_id"]
    d = pd.DataFrame(
        {
            "activity": df["activity"],
            "dur_s": (df["timestamp"] - prev["timestamp"]).dt.total_seconds(),
        }
    )[same]

    g = d.groupby("activity")["dur_s"]
    out = pd.DataFrame(
        {
            "n": g.size(),
            "median_s": g.median().round(1),
            "mean_s": g.mean().round(1),
            "p90_s": g.quantile(0.9).round(1),
            "total_h": (g.sum() / 3600).round(2),
        }
    ).reset_index()
    return out.sort_values("total_h", ascending=False).reset_index(drop=True)


def to_mermaid(log: EventLog, min_freq_pct: float = 1.0) -> str:
    """DFG en Mermaid, para pegar en el A3 o en el reporte al cliente.

    Filtra aristas raras: un DFG completo de un CD real es ilegible y ese es el
    error clasico de la primera presentacion."""
    dfg = directly_follows(log)
    cutoff = dfg["freq"].sum() * min_freq_pct / 100
    dfg = dfg[dfg["freq"] >= cutoff]

    ids: dict[str, str] = {}

    def nid(name: str) -> str:
        if name not in ids:
            ids[name] = f"N{len(ids)}"
        return ids[name]

    lines = ["flowchart TD"]
    for _, r in dfg.iterrows():
        lines.append(
            f'    {nid(r["source"])}["{r["source"]}"] '
            f'-->|{int(r["freq"])} / {r["median_wait_s"]:.0f}s| '
            f'{nid(r["target"])}["{r["target"]}"]'
        )
    return "\n".join(lines)
