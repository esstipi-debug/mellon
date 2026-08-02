"""Tiempos de ciclo, takt time y variacion entre operadores.

La variacion entre operadores es la metrica mas subestimada del terreno. Si el
percentil 90 de un picker es el doble del percentil 10 de otro haciendo la misma
tarea, no tenes un problema de sistema: tenes un problema de trabajo estandar, y
ningun software lo va a arreglar. Eso hay que decirlo antes del go-live, no
despues.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..processmining.log import EventLog


def cycle_times(log: EventLog) -> pd.DataFrame:
    """Distribucion del tiempo de ciclo punta a punta por caso."""
    return log.case_durations()


def cycle_time_stats(log: EventLog) -> dict:
    c = log.case_durations()["cycle_time_s"]
    return {
        "n_cases": int(len(c)),
        "median_min": round(float(c.median()) / 60, 2),
        "mean_min": round(float(c.mean()) / 60, 2),
        "p90_min": round(float(c.quantile(0.9)) / 60, 2),
        "p99_min": round(float(c.quantile(0.99)) / 60, 2),
        # Indice de variabilidad: p90/p50. Sobre 2.5 el proceso no es estable y
        # cualquier promesa de SLA es humo.
        "variability_index": round(float(c.quantile(0.9) / c.median()), 2),
    }


def takt_analysis(log: EventLog, demand_units: int | None = None, available_hours: float | None = None) -> dict:
    """Takt time vs tiempo de ciclo real.

    takt = tiempo disponible / demanda. Si el ciclo real supera al takt, el
    sistema no da, y no hay software que lo salve sin agregar recursos.
    """
    cases = log.case_durations()
    span_h = (cases["end"].max() - cases["start"].min()).total_seconds() / 3600
    available_hours = available_hours or span_h
    demand_units = demand_units or log.n_cases
    median_cycle_s = float(cases["cycle_time_s"].median())

    out = {
        "window_hours": round(span_h, 2),
        "demand_units": int(demand_units),
        "median_cycle_s": round(median_cycle_s, 1),
    }

    # Una ventana de duracion cero es un log mal exportado —tipicamente el
    # timestamp truncado al dia— y no un CD infinitamente rapido. Devolver el
    # hueco marcado es la regla 1: lo que no se puede cuantificar se declara,
    # no se rellena. Reventar aca deja al FDE sin herramienta en la sala.
    if available_hours <= 0:
        return {
            **out,
            "takt_s": None,
            "throughput_per_hour": None,
            "cycle_over_takt": None,
            "warning": (
                "ventana de duracion cero: el log no tiene rango temporal utilizable. "
                "Revisar la precision del timestamp exportado por el WMS."
            ),
        }

    takt_s = available_hours * 3600 / demand_units

    return {
        **out,
        "takt_s": round(takt_s, 1),
        "throughput_per_hour": round(demand_units / available_hours, 1),
        # Es normal que ciclo >> takt cuando hay paralelismo. Lo relevante es la
        # comparacion contra la capacidad instalada, no contra 1 operador.
        "cycle_over_takt": round(median_cycle_s / takt_s, 2),
    }


def operator_variation(log: EventLog, activity: str, role_prefix: str | None = None) -> pd.DataFrame:
    """Duracion de una actividad, desagregada por operador.

    La duracion se atribuye como el delta contra el evento anterior del mismo
    caso, que es lo unico calculable cuando el WMS solo registra el termino.
    """
    df = log.df
    prev = df.shift(1)
    same = df["case_id"] == prev["case_id"]
    d = pd.DataFrame(
        {
            "activity": df["activity"],
            "resource": df["resource"],
            "dur_s": (df["timestamp"] - prev["timestamp"]).dt.total_seconds(),
        }
    )[same]
    d = d[d["activity"] == activity].dropna(subset=["resource"])
    if role_prefix:
        d = d[d["resource"].astype(str).str.startswith(role_prefix)]
    if d.empty:
        return pd.DataFrame()

    g = d.groupby("resource")["dur_s"]
    out = pd.DataFrame(
        {
            "n": g.size(),
            "p10_s": g.quantile(0.10).round(1),
            "median_s": g.median().round(1),
            "p90_s": g.quantile(0.90).round(1),
        }
    ).reset_index()

    best = out["median_s"].min()
    out["vs_best_pct"] = ((out["median_s"] / best - 1) * 100).round(1)
    return out.sort_values("median_s").reset_index(drop=True)


def standard_work_gap(log: EventLog, activity: str, role_prefix: str | None = None) -> dict:
    """Cuanto se recupera si todos trabajaran como el percentil 25 del equipo.

    No como el mejor — eso es fantasia y el supervisor lo sabe. El p25 es una
    meta que se defiende en una reunion.
    """
    ov = operator_variation(log, activity, role_prefix)
    if ov.empty:
        return {}

    target = float(np.percentile(ov["median_s"], 25))
    ov = ov.copy()
    ov["excess_s"] = (ov["median_s"] - target).clip(lower=0) * ov["n"]
    hours = float(ov["excess_s"].sum()) / 3600

    return {
        "activity": activity,
        "operators": int(len(ov)),
        "target_median_s": round(target, 1),
        "worst_median_s": round(float(ov["median_s"].max()), 1),
        "spread_pct": round(float(ov["median_s"].max() / ov["median_s"].min() - 1) * 100, 1),
        # Unidad de salida: la ventana observada, con su denominador al lado.
        # Anualizar aca obligaria a hardcodear los dias de operacion, que son un
        # dato del arquetipo del cliente y no del log. La conversion a base anual
        # vive en `value/levers.py`, que es donde esta `operating_days`. Cuando
        # estaba en los dos lados quedaba un residuo silencioso de 250/dias.
        # 4 decimales: es el insumo de la anualizacion, no un campo de tabla.
        "recoverable_hours_in_window": round(hours, 4),
        "cases_in_window": int(log.n_cases),
    }
