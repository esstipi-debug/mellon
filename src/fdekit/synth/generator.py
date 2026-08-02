"""Genera un centro de distribucion sintetico con defectos realistas.

No es un dataset de juguete. Los defectos estan *encadenados causalmente*, que
es lo que permite que dos herramientas del kit lleguen a la misma conclusion por
caminos independientes:

    maestro con dimensiones erradas  ->  reproceso de carton en packing
    maestro con ubicacion vencida    ->  excepcion de picking + viaje extra
    slotting aleatorio               ->  clase A lejos del dock -> recorrido alto
    pickers subdimensionados         ->  cola entre liberacion y picking

Cuando en el A3 final la auditoria de datos maestros (herramienta 4) explica
exactamente el bucle de reproceso que encontro el process mining (herramienta 3),
el cliente deja de discutir. Ese es el objetivo del diseno.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..layout import DOCK, Layout

# Duraciones base en segundos.
PICK_TIME_MEDIAN_S = 11.0
PICK_TIME_SIGMA = 0.35
SEARCH_ON_EXCEPTION_S = 75.0
REPLENISH_LEAD_S = 420.0
CONSOLIDATE_S = 45.0
PACK_TIME_MEDIAN_S = 95.0
PACK_TIME_SIGMA = 0.28
CARTON_REWORK_S = 190.0
QC_S = 40.0
REPACK_S = 165.0
SHIP_S = 25.0


@dataclass
class DCConfig:
    """Parametros del CD sintetico. Los defaults producen un CD con dolor
    visible pero no caricaturesco."""

    seed: int = 7
    n_skus: int = 1800
    # Dimensionado para ~85% de utilizacion de los pickers: se forma cola en el
    # pico de media manana y se drena antes del cierre del turno. Subirlo sin
    # subir la dotacion produce un backlog que no cierra, que es un CD en crisis,
    # no un CD con oportunidades.
    n_orders: int = 800
    n_pickers: int = 7
    n_packers: int = 8
    n_replenishers: int = 2
    shift_start: str = "2026-03-02 07:00:00"
    shift_hours: float = 8.0

    # Defectos de datos maestros
    dim_error_rate: float = 0.18
    location_error_rate: float = 0.07

    # Defectos de operacion
    short_pick_rate: float = 0.025
    qc_fail_rate: float = 0.035
    carton_rework_rate_bad_dims: float = 0.55
    carton_rework_rate_good_dims: float = 0.04

    slotting: str = "random"  # "random" | "abc"
    layout: Layout = field(default_factory=Layout)


@dataclass
class DCDataset:
    """Todo lo que produce el generador."""

    events: pd.DataFrame  # log de eventos (contrato del kit)
    master: pd.DataFrame  # lo que el WMS cree
    truth: pd.DataFrame  # la realidad fisica (solo para la "medicion" en terreno)
    defects: pd.DataFrame  # clave de respuestas, para evaluar el kit
    orders: pd.DataFrame
    order_lines: pd.DataFrame
    config: DCConfig

    def summary(self) -> str:
        n_cases = self.events["case_id"].nunique()
        span = self.events["timestamp"].max() - self.events["timestamp"].min()
        return (
            f"{len(self.events):,} eventos | {n_cases:,} pedidos | "
            f"{self.master.shape[0]:,} SKUs | ventana {span}"
        )


# ------------------------------------------------------------------- maestros


def _build_skus(
    cfg: DCConfig, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = cfg.n_skus
    lay = cfg.layout

    # Popularidad Zipf -> curva ABC realista (20% de SKU, ~75% de lineas).
    rank = np.arange(1, n + 1)
    popularity = 1.0 / rank**0.85
    popularity = popularity / popularity.sum()
    order = rng.permutation(n)
    popularity = popularity[np.argsort(order)]

    cum = np.cumsum(np.sort(popularity)[::-1])
    a_cut = np.searchsorted(cum, 0.75) + 1
    b_cut = np.searchsorted(cum, 0.95) + 1
    ranking = np.argsort(np.argsort(-popularity))
    abc = np.where(ranking < a_cut, "A", np.where(ranking < b_cut, "B", "C"))

    length = np.round(rng.lognormal(3.0, 0.45, n), 1)
    width = np.round(length * rng.uniform(0.4, 0.95, n), 1)
    height = np.round(rng.lognormal(2.4, 0.5, n), 1)
    weight = np.round(np.clip(length * width * height / 4200 * rng.lognormal(0, 0.3, n), 0.05, 30), 3)

    # Slotting fisico real.
    locations = lay.all_locations()
    if cfg.slotting == "abc":
        golden = sorted(lay.golden_zone())
        rest = [c for c in locations if c not in set(golden)]
        rng.shuffle(golden)
        rng.shuffle(rest)
        pool: list[str] = []
        gi = ri = 0
        for cls in abc:
            if cls == "A" and gi < len(golden):
                pool.append(golden[gi])
                gi += 1
            else:
                pool.append(rest[ri])
                ri += 1
        home = np.array(pool)
    else:
        home = rng.choice(locations, size=n, replace=False)

    truth = pd.DataFrame(
        {
            "sku_id": [f"S{i:05d}" for i in range(1, n + 1)],
            "abc_class": abc,
            "popularity": popularity,
            "length_cm": length,
            "width_cm": width,
            "height_cm": height,
            "weight_kg": weight,
            "home_location": home,
        }
    )

    # El maestro es la verdad, degradada.
    master = truth.drop(columns=["popularity"]).copy()
    dim_bad = rng.random(n) < cfg.dim_error_rate
    loc_bad = rng.random(n) < cfg.location_error_rate

    factor = np.where(rng.random(n) < 0.5, rng.uniform(1.35, 2.3, n), rng.uniform(0.35, 0.7, n))
    for col in ("length_cm", "width_cm", "height_cm"):
        master.loc[dim_bad, col] = np.round(master.loc[dim_bad, col] * factor[dim_bad], 1)
    master.loc[dim_bad, "weight_kg"] = np.round(
        master.loc[dim_bad, "weight_kg"] * rng.uniform(0.6, 1.8, dim_bad.sum()), 3
    )
    stale = rng.choice(locations, size=int(loc_bad.sum()), replace=False)
    master.loc[loc_bad, "home_location"] = stale

    defects = pd.DataFrame(
        {"sku_id": truth["sku_id"], "dim_error": dim_bad, "location_error": loc_bad}
    )
    return master, truth, defects


def _build_orders(
    cfg: DCConfig, truth: pd.DataFrame, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = cfg.n_orders
    t0 = pd.Timestamp(cfg.shift_start)
    horizon_s = cfg.shift_hours * 3600

    # Liberacion con pico de media manana: mezcla de uniforme y normal.
    base = rng.uniform(0, horizon_s, n)
    peak = rng.normal(horizon_s * 0.35, horizon_s * 0.10, n)
    mix = rng.random(n) < 0.45
    rel = np.clip(np.where(mix, peak, base), 0, horizon_s)
    rel.sort()

    orders = pd.DataFrame(
        {
            "order_id": [f"O{i:06d}" for i in range(1, n + 1)],
            "released_at": [t0 + pd.Timedelta(seconds=float(s)) for s in rel],
            "priority": rng.choice(["STD", "EXP"], size=n, p=[0.85, 0.15]),
        }
    )

    n_lines = np.clip(rng.geometric(0.38, n), 1, 12)
    p = truth["popularity"].to_numpy()
    p = p / p.sum()
    skus = truth["sku_id"].to_numpy()

    rows = []
    for oid, k in zip(orders["order_id"], n_lines):
        chosen = rng.choice(skus, size=int(k), replace=False, p=p)
        for sku in chosen:
            rows.append((oid, sku, int(rng.integers(1, 4))))
    order_lines = pd.DataFrame(rows, columns=["order_id", "sku_id", "qty"])
    return orders, order_lines


# ------------------------------------------------------------------ event log


def _simulate(
    cfg: DCConfig,
    orders: pd.DataFrame,
    lines: pd.DataFrame,
    master: pd.DataFrame,
    truth: pd.DataFrame,
    defects: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    lay = cfg.layout
    t0 = pd.Timestamp(cfg.shift_start)

    m_loc = dict(zip(master["sku_id"], master["home_location"]))
    t_loc = dict(zip(truth["sku_id"], truth["home_location"]))
    bad_dims = set(defects.loc[defects["dim_error"], "sku_id"])
    bad_loc = set(defects.loc[defects["location_error"], "sku_id"])

    lines_by_order: dict[str, list[str]] = {}
    for oid, grp in lines.groupby("order_id", sort=False):
        lines_by_order[oid] = list(grp["sku_id"])

    pickers = [(0.0, f"PICK-{i:02d}") for i in range(1, cfg.n_pickers + 1)]
    packers = [(0.0, f"PACK-{i:02d}") for i in range(1, cfg.n_packers + 1)]
    replen = [(0.0, f"REPL-{i:02d}") for i in range(1, cfg.n_replenishers + 1)]
    heapq.heapify(pickers)
    heapq.heapify(packers)
    heapq.heapify(replen)

    ev: list[tuple] = []

    def emit(case, act, t, res, loc):
        ev.append((case, act, t, res, loc))

    for oid, rel_ts in zip(orders["order_id"], orders["released_at"]):
        rel = (rel_ts - t0).total_seconds()
        emit(oid, "ORDER_RELEASED", rel, "WMS", DOCK)

        skus = lines_by_order.get(oid, [])
        # Secuenciacion serpentina por (pasillo, modulo) — como rutea el WMS.
        stops = sorted(skus, key=lambda s: lay.parse(m_loc[s])[:2])

        free, picker = heapq.heappop(pickers)
        t = max(rel, free)
        here = DOCK
        touched_bad_dim = False

        for sku in stops:
            declared = m_loc[sku]
            actual = t_loc[sku]
            t += lay.travel_time_s(here, declared)
            here = declared

            if sku in bad_loc:
                # El picker llega, no encuentra, busca, y camina a la real.
                t += SEARCH_ON_EXCEPTION_S
                emit(oid, "PICK_EXCEPTION_LOCATION", t, picker, declared)
                t += lay.travel_time_s(declared, actual)
                here = actual

            if rng.random() < cfg.short_pick_rate:
                emit(oid, "SHORT_PICK", t, picker, here)
                rfree, rres = heapq.heappop(replen)
                rstart = max(t, rfree)
                rdone = rstart + REPLENISH_LEAD_S * rng.uniform(0.6, 1.6)
                emit(oid, "REPLENISH", rdone, rres, here)
                heapq.heappush(replen, (rdone, rres))
                t = max(t, rdone)

            t += rng.lognormal(np.log(PICK_TIME_MEDIAN_S), PICK_TIME_SIGMA)
            t += lay.reach_penalty_s(here)
            emit(oid, "PICK", t, picker, here)
            if sku in bad_dims:
                touched_bad_dim = True

        t += lay.travel_time_s(here, DOCK)
        heapq.heappush(pickers, (t, picker))
        pick_done = t

        pfree, packer = heapq.heappop(packers)
        t = max(pick_done, pfree)
        t += CONSOLIDATE_S * rng.uniform(0.7, 1.5)
        emit(oid, "CONSOLIDATE", t, packer, DOCK)

        t += rng.lognormal(np.log(PACK_TIME_MEDIAN_S), PACK_TIME_SIGMA)
        emit(oid, "PACK", t, packer, DOCK)

        rework_p = (
            cfg.carton_rework_rate_bad_dims if touched_bad_dim else cfg.carton_rework_rate_good_dims
        )
        if rng.random() < rework_p:
            t += CARTON_REWORK_S * rng.uniform(0.7, 1.4)
            emit(oid, "CARTON_REWORK", t, packer, DOCK)
            t += rng.lognormal(np.log(PACK_TIME_MEDIAN_S * 0.7), PACK_TIME_SIGMA)
            emit(oid, "PACK", t, packer, DOCK)

        t += QC_S * rng.uniform(0.6, 1.6)
        emit(oid, "QC", t, packer, DOCK)
        if rng.random() < cfg.qc_fail_rate:
            t += REPACK_S * rng.uniform(0.7, 1.4)
            emit(oid, "REPACK", t, packer, DOCK)
            t += QC_S * rng.uniform(0.6, 1.6)
            emit(oid, "QC", t, packer, DOCK)

        t += SHIP_S * rng.uniform(0.6, 1.6)
        emit(oid, "SHIP", t, packer, DOCK)
        heapq.heappush(packers, (t, packer))

    df = pd.DataFrame(ev, columns=["case_id", "activity", "t_s", "resource", "location"])
    df["timestamp"] = t0 + pd.to_timedelta(df["t_s"], unit="s")
    df = df.drop(columns=["t_s"]).sort_values(["timestamp", "case_id"]).reset_index(drop=True)
    return df[["case_id", "activity", "timestamp", "resource", "location"]]


def generate_dc(cfg: DCConfig | None = None) -> DCDataset:
    """Genera el dataset completo. Determinista dado `cfg.seed`."""
    cfg = cfg or DCConfig()
    rng = np.random.default_rng(cfg.seed)

    master, truth, defects = _build_skus(cfg, rng)
    orders, lines = _build_orders(cfg, truth, rng)
    events = _simulate(cfg, orders, lines, master, truth, defects, rng)

    return DCDataset(
        events=events,
        master=master,
        truth=truth,
        defects=defects,
        orders=orders,
        order_lines=lines,
        config=cfg,
    )
