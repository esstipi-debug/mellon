"""Sesion de gemba: captura offline, agregacion y Pareto.

Offline a proposito. En los pasillos de un CD no hay wifi, y una herramienta que
necesita conexion para registrar una observacion no se usa — se vuelve a la
libreta. La sesion escribe a JSONL local y sincroniza cuando se puede.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .schema import GEMBA_QUESTIONS, WASTE_TYPES, Observation


class GembaSession:
    """Un turno de observacion. Append-only a un JSONL local."""

    def __init__(self, path: str | Path, site: str = "", observer: str = ""):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.site = site
        self.observer = observer
        self._obs: list[Observation] = []
        if self.path.exists():
            self._load()

    def _load(self):
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            for k in ("impact_h_per_shift", "impact_h_per_year", "quantified", "site"):
                d.pop(k, None)
            self._obs.append(Observation(**d))

    def add(self, obs: Observation) -> Observation:
        if not obs.observer:
            obs.observer = self.observer
        self._obs.append(obs)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({**obs.to_dict(), "site": self.site}, ensure_ascii=False) + "\n")
        return obs

    def __len__(self) -> int:
        return len(self._obs)

    # ------------------------------------------------------------- analisis

    def to_frame(self) -> pd.DataFrame:
        if not self._obs:
            return pd.DataFrame()
        return pd.DataFrame([o.to_dict() for o in self._obs])

    def pareto(self) -> pd.DataFrame:
        """Pareto por tipo de desperdicio, ordenado por horas anuales perdidas.

        Las observaciones sin cuantificar quedan fuera y se reportan aparte. Esa
        separacion es deliberada: obliga a volver al terreno a medir en vez de
        discutir con anecdotas.
        """
        df = self.to_frame()
        if df.empty:
            return df

        q = df[df["quantified"]]
        if q.empty:
            return pd.DataFrame()

        g = (
            q.groupby("waste_type")
            .agg(
                observations=("description", "size"),
                hours_per_shift=("impact_h_per_shift", "sum"),
                hours_per_year=("impact_h_per_year", "sum"),
            )
            .reset_index()
            .sort_values("hours_per_year", ascending=False)
        )
        total = g["hours_per_year"].sum()
        g["pct"] = (g["hours_per_year"] / total * 100).round(1)
        g["cum_pct"] = g["pct"].cumsum().round(1)
        g["definition"] = g["waste_type"].map(WASTE_TYPES)
        return g.reset_index(drop=True)

    def unquantified(self) -> pd.DataFrame:
        """Lo que falta medir. Es la lista de tareas del proximo turno."""
        df = self.to_frame()
        if df.empty:
            return df
        cols = ["area", "activity", "waste_type", "description", "duration_s", "frequency_per_shift"]
        return df.loc[~df["quantified"], cols].reset_index(drop=True)

    def top_opportunities(self, n: int = 5) -> pd.DataFrame:
        df = self.to_frame()
        if df.empty:
            return df
        cols = [
            "area",
            "activity",
            "waste_type",
            "description",
            "impact_h_per_year",
            "root_cause",
            "countermeasure_idea",
        ]
        return (
            df[df["quantified"]]
            .sort_values("impact_h_per_year", ascending=False)
            .head(n)[cols]
            .reset_index(drop=True)
        )

    def checklist(self) -> str:
        """Las preguntas que se hacen en el pasillo. Imprimir y llevar."""
        lines = [f"# Gemba — {self.site}", "", "## Preguntas al operador (en su turno, no en la oficina)"]
        lines += [f"{i}. {q}" for i, q in enumerate(GEMBA_QUESTIONS, 1)]
        lines += ["", "## Tipos de desperdicio"]
        lines += [f"- **{k}** — {v}" for k, v in WASTE_TYPES.items()]
        lines += [
            "",
            "## Regla",
            "Toda observacion necesita duracion y frecuencia. Sin los dos numeros no",
            "entra al Pareto, y lo que no entra al Pareto no se arregla.",
        ]
        return "\n".join(lines)
