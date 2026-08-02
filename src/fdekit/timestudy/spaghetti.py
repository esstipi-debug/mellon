"""Diagrama de espagueti y mapa de calor a partir del log del WMS.

No hace falta seguir a un picker con una tiza: las tareas del WMS ya traen
ubicacion y orden. Reconstruir el recorrido es aritmetica sobre el layout, y el
grafico resultante es el que abre la boca del gerente de operaciones.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..layout import DOCK, Layout
from ..processmining.log import EventLog

PICK_ACTIVITIES = ("PICK", "PICK_EXCEPTION_LOCATION", "SHORT_PICK")


def _pick_paths(log: EventLog, activities=PICK_ACTIVITIES) -> dict[str, list[str]]:
    df = log.df
    df = df[df["activity"].isin(activities)].dropna(subset=["location"])
    df = df[df["location"] != DOCK]
    return {cid: list(g["location"]) for cid, g in df.groupby("case_id", sort=False)}


def travel_report(log: EventLog, layout: Layout | None = None) -> pd.DataFrame:
    """Distancia recorrida por pedido, con lineas y metros por linea."""
    lay = layout or Layout()
    paths = _pick_paths(log)

    rows = []
    for cid, stops in paths.items():
        n_picks = sum(1 for s in stops)
        dist = lay.route_distance(stops)
        rows.append((cid, n_picks, round(dist, 1), round(dist / max(n_picks, 1), 1)))

    out = pd.DataFrame(rows, columns=["case_id", "n_stops", "distance_m", "m_per_stop"])
    return out.sort_values("distance_m", ascending=False).reset_index(drop=True)


def travel_stats(log: EventLog, layout: Layout | None = None, walk_speed: float = 1.1) -> dict:
    t = travel_report(log, layout)
    total_m = float(t["distance_m"].sum())
    hours = total_m / walk_speed / 3600
    return {
        "orders": int(len(t)),
        "total_km": round(total_m / 1000, 2),
        "median_m_per_order": round(float(t["distance_m"].median()), 1),
        "p90_m_per_order": round(float(t["distance_m"].quantile(0.9)), 1),
        "median_m_per_stop": round(float(t["m_per_stop"].median()), 1),
        # En un CD tipico el 50-60% del tiempo de picking es caminata. Si el
        # numero da menos de 35%, sospechar del log antes que del CD.
        #
        # Unidad de salida: la ventana observada, con `orders` como denominador.
        # Ojo que `orders` cuenta los pedidos CON lineas de picking, que no son
        # todos los casos del log — repartir estas horas entre los casos totales
        # subestima la caminata por pedido. La anualizacion vive en
        # `value/levers.py`, junto a los dias de operacion del arquetipo.
        #
        # 4 decimales, no 2: este campo dejo de ser decorativo y paso a ser el
        # insumo de la anualizacion. En una ventana corta 0.0081 h redondeado a
        # 0.01 h es un +24% que despues se multiplica por los pedidos del ano.
        "walking_hours_in_window": round(hours, 4),
    }


def location_frequency(log: EventLog, activities=PICK_ACTIVITIES) -> pd.DataFrame:
    """Visitas por ubicacion — insumo del mapa de calor y del reslotting.

    Cuenta las mismas actividades que `_pick_paths`, y eso es una correccion, no
    una ampliacion. Filtrar solo `PICK` dejaba fuera `PICK_EXCEPTION_LOCATION` y
    `SHORT_PICK`, que son exactamente las visitas a ubicaciones con el maestro
    vencido: las que mas veces se recorren y las unicas que el reslotting tiene
    que ver. El mapa de calor mostraba el CD que el WMS cree, no el que el
    picker camina — y el sesgo apuntaba justo contra el hallazgo.
    """
    df = log.df
    df = df[df["activity"].isin(activities)].dropna(subset=["location"])
    df = df[df["location"] != DOCK]
    return df["location"].value_counts().rename("visits").rename_axis("location").reset_index()


def slotting_opportunity(
    log: EventLog, master: pd.DataFrame, layout: Layout | None = None
) -> dict:
    """Cuanto recorrido se ahorra reslotting la clase A a la zona dorada.

    Estimacion conservadora: mantiene la secuencia de pedidos y solo reasigna
    ubicaciones, comparando la distancia media al dock antes y despues.
    """
    lay = layout or Layout()
    freq = location_frequency(log)
    loc2sku = dict(zip(master["home_location"], master["sku_id"]))
    cls = dict(zip(master["sku_id"], master["abc_class"]))

    freq = freq.copy()
    freq["sku_id"] = freq["location"].map(loc2sku)
    freq["abc_class"] = freq["sku_id"].map(cls)
    freq["dist_to_dock_m"] = [lay.distance(DOCK, c) for c in freq["location"]]

    golden = lay.golden_zone()
    freq["in_golden"] = freq["location"].isin(golden)

    a = freq[freq["abc_class"] == "A"]
    a_visits = int(a["visits"].sum())
    total_visits = int(freq["visits"].sum())

    weighted_now = float((freq["visits"] * freq["dist_to_dock_m"]).sum() / max(total_visits, 1))
    golden_mean = float(np.mean([lay.distance(DOCK, c) for c in sorted(golden)]))

    # Contrafactual: la clase A se mueve a la distancia media de la zona dorada.
    d_after = freq["dist_to_dock_m"].where(freq["abc_class"] != "A", golden_mean)
    weighted_after = float((freq["visits"] * d_after).sum() / max(total_visits, 1))

    return {
        "class_a_share_of_visits_pct": round(a_visits / max(total_visits, 1) * 100, 1),
        "class_a_already_in_golden_pct": round(
            float(a.loc[a["in_golden"], "visits"].sum()) / max(a_visits, 1) * 100, 1
        ),
        "mean_weighted_distance_now_m": round(weighted_now, 1),
        "mean_weighted_distance_after_m": round(weighted_after, 1),
        "reduction_pct": round((1 - weighted_after / max(weighted_now, 1e-9)) * 100, 1),
    }


# ------------------------------------------------------------------ graficos


def plot_spaghetti(log: EventLog, layout: Layout | None = None, n_orders: int = 25, path: str | None = None):
    """Dibuja las rutas de N pedidos sobre la planta. Este es el grafico."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lay = layout or Layout()
    paths = _pick_paths(log)
    sample = list(paths.items())[:n_orders]

    fig, ax = plt.subplots(figsize=(11, 7))
    for a in range(1, lay.aisles + 1):
        x = a * lay.aisle_pitch
        ax.plot([x, x], [0, lay.depth_m], color="0.90", lw=8, zorder=0, solid_capstyle="butt")

    for _, stops in sample:
        pts = [lay.xy(DOCK), *[lay.xy(s) for s in stops], lay.xy(DOCK)]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, lw=0.9, alpha=0.55)

    dx, dy = lay.xy(DOCK)
    ax.scatter([dx], [dy], s=180, marker="s", color="#c0392b", zorder=5, label="Dock / packing")
    ax.set_title(f"Diagrama de espagueti — {len(sample)} pedidos")
    ax.set_xlabel("metros (transversal)")
    ax.set_ylabel("metros (profundidad de pasillo)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
        plt.close(fig)
    return fig


def plot_heatmap(log: EventLog, layout: Layout | None = None, path: str | None = None):
    """Mapa de calor de visitas por (pasillo, modulo)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lay = layout or Layout()
    freq = location_frequency(log)
    grid = np.zeros((lay.bays + 1, lay.aisles + 1))
    for loc, v in zip(freq["location"], freq["visits"]):
        a, b, _ = lay.parse(loc)
        grid[b, a] += v

    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(grid, aspect="auto", origin="lower", cmap="magma")
    ax.set_xlabel("pasillo")
    ax.set_ylabel("modulo (0 = frente / dock)")
    ax.set_title("Frecuencia de visita por ubicacion")
    fig.colorbar(im, ax=ax, label="picks")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
        plt.close(fig)
    return fig
