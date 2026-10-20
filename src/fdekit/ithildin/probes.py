"""Inspeccion pasiva y telemetria silenciosa de logs de eventos.

El Patron Ithildin:
El probe opera en modo solo-lectura y bajo overhead.
Evalua la salud de un flujo de eventos contra el contrato de 5 columnas estandar
(case_id, activity, timestamp, resource, location) sin emitir queries agresivas
ni interrumpir los servicios transaccionales en operacion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence


STANDARD_5_COLUMNS = ("case_id", "activity", "timestamp", "resource", "location")


@dataclass(frozen=True)
class ProbeReport:
    """Resultado de la inspeccion pasiva de un flujo de eventos."""

    total_records: int
    missing_columns: tuple[str, ...]
    null_counts: Mapping[str, int]
    unparseable_timestamps: int
    tz_naive_timestamps: int
    out_of_order_cases: int
    quality_score: float  # De 0.0 (inutilizable) a 1.0 (apto para inferencia determinista)
    is_safe_for_inference: bool
    summary: str


class PassiveEventProbe:
    """Sonda pasiva de eventos operacionales."""

    def __init__(self, required_columns: Sequence[str] = STANDARD_5_COLUMNS) -> None:
        self.required_columns = tuple(required_columns)

    def inspect(self, records: Iterable[Mapping[str, Any]]) -> ProbeReport:
        """Inspecciona una coleccion o iterador de registros de eventos en streaming."""
        total = 0
        null_counts = {col: 0 for col in self.required_columns}
        unparseable_ts = 0
        tz_naive_ts = 0
        seen_columns: set[str] = set()

        last_timestamp_by_case: dict[str, datetime] = {}
        out_of_order_count = 0

        for r in records:
            total += 1
            if total == 1:
                seen_columns.update(r.keys())

            # Chequeo de columnas minimas y nulos
            for col in self.required_columns:
                val = r.get(col)
                if val is None or val == "":
                    null_counts[col] += 1

            # Chequeo de timestamp
            raw_ts = r.get("timestamp")
            if raw_ts is not None and raw_ts != "":
                parsed_dt: datetime | None = None
                if isinstance(raw_ts, datetime):
                    parsed_dt = raw_ts
                elif isinstance(raw_ts, str):
                    try:
                        parsed_dt = datetime.fromisoformat(raw_ts)
                    except Exception:
                        unparseable_ts += 1

                if parsed_dt is not None:
                    if parsed_dt.tzinfo is None:
                        tz_naive_ts += 1

                    # Verificacion de orden cronologico por caso
                    case_id = str(r.get("case_id", ""))
                    if case_id:
                        prev_dt = last_timestamp_by_case.get(case_id)
                        if prev_dt and parsed_dt < prev_dt:
                            out_of_order_count += 1
                        last_timestamp_by_case[case_id] = parsed_dt

        missing_cols = tuple(col for col in self.required_columns if col not in seen_columns)

        if total == 0:
            return ProbeReport(
                total_records=0,
                missing_columns=missing_cols,
                null_counts=null_counts,
                unparseable_timestamps=0,
                tz_naive_timestamps=0,
                out_of_order_cases=0,
                quality_score=0.0,
                is_safe_for_inference=False,
                summary="Flujo vacio. Ningun registro disponible para inspeccion.",
            )

        # Calculo ponderado de penalidades
        penalties = 0.0

        # Falta de columnas estructurales
        if missing_cols:
            penalties += len(missing_cols) * 0.25

        # Proporcion de nulos en columnas criticas (case_id, activity, timestamp)
        crit_nulls = sum(null_counts.get(c, 0) for c in ("case_id", "activity", "timestamp"))
        if crit_nulls > 0:
            penalties += min(0.40, (crit_nulls / (total * 3)))

        # Timestamps corruptos o huerfanos de huso horario
        if unparseable_ts > 0:
            penalties += min(0.30, unparseable_ts / total)
        if tz_naive_ts > 0:
            penalties += min(0.15, (tz_naive_ts / total) * 0.5)

        # Inversiones cronologicas
        if out_of_order_count > 0:
            penalties += min(0.20, out_of_order_count / total)

        score = max(0.0, min(1.0, 1.0 - penalties))
        is_safe = score >= 0.75 and not missing_cols and unparseable_ts == 0

        summary = (
            f"Inspeccionados {total} registros. Calidad: {score:.2%}. "
            f"Columnas ausentes: {len(missing_cols)}, Nulos criticos: {crit_nulls}, "
            f"Timestamps sin TZ: {tz_naive_ts}, Casos desordenados: {out_of_order_count}."
        )

        return ProbeReport(
            total_records=total,
            missing_columns=missing_cols,
            null_counts=null_counts,
            unparseable_timestamps=unparseable_ts,
            tz_naive_timestamps=tz_naive_ts,
            out_of_order_cases=out_of_order_count,
            quality_score=score,
            is_safe_for_inference=is_safe,
            summary=summary,
        )
