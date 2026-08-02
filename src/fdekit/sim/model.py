"""Simulacion de eventos discretos del flujo picking -> packing (SimPy).

Sirve para responder, antes de instalar nada: ¿cuantos pickers? ¿cuantas
estaciones de packing? ¿donde se forma la cola en el pico de las 10:30?

La regla de oro: calibrar contra el log real (`calibrate_from_log`) y validar
que el modelo reproduce el throughput observado antes de usarlo para proyectar.
Un simulador no validado es una opinion con grafico.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import simpy

from ..processmining.log import EventLog


@dataclass
class SimConfig:
    n_pickers: int = 9
    n_packers: int = 4
    arrival_rate_per_h: float = 312.0
    pick_time_median_s: float = 300.0
    pick_time_sigma: float = 0.45
    pack_time_median_s: float = 150.0
    pack_time_sigma: float = 0.30
    horizon_h: float = 8.0
    warmup_h: float = 0.5
    seed: int = 0


@dataclass
class SimResult:
    completed: int
    throughput_per_h: float
    mean_cycle_min: float
    p90_cycle_min: float
    mean_wait_pick_min: float
    mean_wait_pack_min: float
    picker_utilization: float
    packer_utilization: float
    mean_wip: float

    def as_dict(self) -> dict:
        return {k: round(v, 3) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def run_sim(cfg: SimConfig) -> SimResult:
    rng = np.random.default_rng(cfg.seed)
    env = simpy.Environment()
    pickers = simpy.Resource(env, capacity=cfg.n_pickers)
    packers = simpy.Resource(env, capacity=cfg.n_packers)

    warmup_s = cfg.warmup_h * 3600
    horizon_s = cfg.horizon_h * 3600
    records: list[dict] = []
    busy = {"pick": 0.0, "pack": 0.0}
    wip_samples: list[int] = []
    in_system = {"n": 0}

    def lognorm(median: float, sigma: float) -> float:
        return float(rng.lognormal(np.log(median), sigma))

    def order(env, oid: float):
        t_in = env.now
        in_system["n"] += 1
        rec = {"id": oid, "arrive": t_in}

        with pickers.request() as req:
            yield req
            rec["pick_start"] = env.now
            d = lognorm(cfg.pick_time_median_s, cfg.pick_time_sigma)
            yield env.timeout(d)
            if env.now > warmup_s:
                busy["pick"] += d

        with packers.request() as req:
            yield req
            rec["pack_start"] = env.now
            d = lognorm(cfg.pack_time_median_s, cfg.pack_time_sigma)
            yield env.timeout(d)
            if env.now > warmup_s:
                busy["pack"] += d

        rec["done"] = env.now
        in_system["n"] -= 1
        if rec["arrive"] > warmup_s:
            records.append(rec)

    def source(env):
        i = 0
        rate = cfg.arrival_rate_per_h / 3600
        while True:
            yield env.timeout(rng.exponential(1 / rate))
            i += 1
            env.process(order(env, i))

    def sampler(env):
        while True:
            yield env.timeout(60)
            if env.now > warmup_s:
                wip_samples.append(in_system["n"])

    env.process(source(env))
    env.process(sampler(env))
    env.run(until=horizon_s)

    if not records:
        return SimResult(0, 0, 0, 0, 0, 0, 0, 0, 0)

    df = pd.DataFrame(records).dropna(subset=["done"])
    measured_s = horizon_s - warmup_s
    cycle = (df["done"] - df["arrive"]) / 60
    wait_pick = (df["pick_start"] - df["arrive"]) / 60
    wait_pack = (df["pack_start"] - df["arrive"]) / 60 - wait_pick

    return SimResult(
        completed=len(df),
        throughput_per_h=len(df) / (measured_s / 3600),
        mean_cycle_min=float(cycle.mean()),
        p90_cycle_min=float(cycle.quantile(0.9)),
        mean_wait_pick_min=float(wait_pick.mean()),
        mean_wait_pack_min=float(wait_pack.mean()),
        picker_utilization=busy["pick"] / (cfg.n_pickers * measured_s),
        packer_utilization=busy["pack"] / (cfg.n_packers * measured_s),
        mean_wip=float(np.mean(wip_samples)) if wip_samples else 0.0,
    )


def sizing_sweep(cfg: SimConfig, pickers: range, replications: int = 3) -> pd.DataFrame:
    """Barrido de dimensionamiento con replicas.

    Reportar siempre la media *y* la dispersion entre replicas. Un punto solo es
    una anecdota, y en la reunion de capex eso se nota.
    """
    rows = []
    for n in pickers:
        reps = []
        for r in range(replications):
            c = SimConfig(**{**cfg.__dict__, "n_pickers": n, "seed": cfg.seed + r})
            reps.append(run_sim(c))
        rows.append(
            {
                "n_pickers": n,
                "throughput_per_h": round(float(np.mean([x.throughput_per_h for x in reps])), 1),
                "mean_cycle_min": round(float(np.mean([x.mean_cycle_min for x in reps])), 1),
                "p90_cycle_min": round(float(np.mean([x.p90_cycle_min for x in reps])), 1),
                "cycle_sd_min": round(float(np.std([x.mean_cycle_min for x in reps])), 2),
                "picker_util": round(float(np.mean([x.picker_utilization for x in reps])), 3),
                "mean_wip": round(float(np.mean([x.mean_wip for x in reps])), 1),
            }
        )
    return pd.DataFrame(rows)


def _resource_service_times(df: pd.DataFrame, prefix: str) -> pd.Series:
    """Tiempo de servicio por caso, reconstruido desde el recurso.

    Truco de terreno: cuando el WMS solo registra el termino de cada tarea, el
    tiempo de servicio de un caso es el delta contra el termino del caso
    anterior *del mismo operador*. Es exacto mientras el operador trabaje
    encadenado (que es la condicion normal en hora pico) y sobreestima cuando
    esta ocioso — por eso se calibra con la ventana de mayor carga.
    """
    d = df[df["resource"].astype(str).str.startswith(prefix)]
    if d.empty:
        return pd.Series(dtype=float)

    ends = d.groupby(["resource", "case_id"], sort=False)["timestamp"].max().reset_index()
    ends = ends.sort_values(["resource", "timestamp"])
    delta = ends.groupby("resource")["timestamp"].diff().dt.total_seconds()
    return delta.dropna()


def calibrate_from_log(log: EventLog, n_pickers: int, n_packers: int) -> SimConfig:
    """Extrae los parametros del simulador del log real del cliente.

    Sin este paso el simulador es ciencia ficcion. Con este paso es el unico
    argumento que sobrevive a la pregunta "¿y de donde sacaste ese numero?".
    """
    df = log.df
    cases = log.case_durations()
    span_h = (cases["end"].max() - cases["start"].min()).total_seconds() / 3600
    arrival = log.n_cases / span_h

    pick = _resource_service_times(df, "PICK-")
    pack = _resource_service_times(df, "PACK-")

    def median_sigma(s: pd.Series, fallback: float) -> tuple[float, float]:
        s = s[s > 0]
        if len(s) < 10:
            return fallback, 0.4
        lg = np.log(s)
        return float(np.exp(lg.median())), float(min(max(lg.std(), 0.1), 1.2))

    pm, ps = median_sigma(pick, 300.0)
    km, ks = median_sigma(pack, 150.0)

    return SimConfig(
        n_pickers=n_pickers,
        n_packers=n_packers,
        arrival_rate_per_h=round(arrival, 1),
        pick_time_median_s=round(pm, 1),
        pick_time_sigma=round(ps, 2),
        pack_time_median_s=round(km, 1),
        pack_time_sigma=round(ks, 2),
        horizon_h=round(span_h, 2),
    )
