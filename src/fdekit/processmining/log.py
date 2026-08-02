"""Envoltorio minimo de log de eventos. Sin dependencias pesadas.

El contrato es deliberadamente pobre — (case_id, activity, timestamp) mas dos
columnas opcionales. Cualquier WMS/TMS/ERP puede exportarlo. Negociar un
contrato mas rico en el kickoff es la forma mas comun de perder tres semanas.
"""

from __future__ import annotations

import pandas as pd

REQUIRED = ["case_id", "activity", "timestamp"]


class EventLog:
    """Log de eventos validado y ordenado."""

    def __init__(self, df: pd.DataFrame):
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            raise ValueError(f"faltan columnas obligatorias en el log: {missing}")

        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for opt in ("resource", "location"):
            if opt not in df.columns:
                df[opt] = pd.NA

        self.df = df.sort_values(["case_id", "timestamp"], kind="mergesort").reset_index(drop=True)

    # -------------------------------------------------------------- lecturas

    def __len__(self) -> int:
        return len(self.df)

    @property
    def n_cases(self) -> int:
        return int(self.df["case_id"].nunique())

    @property
    def activities(self) -> list[str]:
        return sorted(self.df["activity"].unique())

    def traces(self) -> pd.Series:
        """Serie case_id -> tupla de actividades en orden."""
        return self.df.groupby("case_id", sort=False)["activity"].agg(tuple)

    def case_durations(self) -> pd.DataFrame:
        """Tiempo de ciclo total por caso (lead time punta a punta)."""
        g = self.df.groupby("case_id")["timestamp"]
        out = pd.DataFrame({"start": g.min(), "end": g.max()})
        out["cycle_time_s"] = (out["end"] - out["start"]).dt.total_seconds()
        out["n_events"] = self.df.groupby("case_id").size()
        return out.reset_index()

    def activity_counts(self) -> pd.DataFrame:
        c = self.df["activity"].value_counts().rename("events").to_frame()
        c["cases"] = self.df.groupby("activity")["case_id"].nunique()
        c["cases_pct"] = (c["cases"] / self.n_cases * 100).round(1)
        c["events_per_case"] = (c["events"] / c["cases"]).round(2)
        return c.reset_index(names="activity")

    def resource_load(self) -> pd.DataFrame:
        """Carga por recurso. La dispersion entre recursos de un mismo rol es
        la senal mas barata de que el trabajo estandar no existe."""
        d = self.df.dropna(subset=["resource"])
        out = (
            d.groupby("resource")
            .agg(events=("activity", "size"), cases=("case_id", "nunique"))
            .reset_index()
        )
        out["role"] = out["resource"].astype(str).str.split("-").str[0]
        return out.sort_values(["role", "events"], ascending=[True, False]).reset_index(drop=True)

    def filter_activities(self, keep: list[str]) -> "EventLog":
        return EventLog(self.df[self.df["activity"].isin(keep)])
