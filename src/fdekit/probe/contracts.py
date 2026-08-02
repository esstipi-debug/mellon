"""Contratos de API y auditoria de husos horarios.

Los dos incidentes post go-live mas frecuentes, en orden:

    1. un campo que cambio de tipo sin aviso (int -> str, o null donde no habia)
    2. un timestamp sin zona horaria

El segundo es peor porque no falla: entrega numeros plausibles y equivocados
durante semanas. Un CD en Santiago con un TMS en UTC y un ERP en hora local
produce reportes que cuadran cuatro dias de cada cinco.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

TYPE_NAMES = {int: "int", float: "float", str: "str", bool: "bool", list: "list", dict: "dict"}


@dataclass
class ContractCheck:
    """Contrato esperado de un payload.

    required   campo -> tipo python esperado
    nullable   campos que pueden venir en null
    enums      campo -> valores permitidos
    """

    name: str
    required: dict[str, type]
    nullable: tuple[str, ...] = ()
    enums: dict[str, tuple[str, ...]] | None = None
    datetime_fields: tuple[str, ...] = ()


def check_payload(payload: dict, contract: ContractCheck) -> list[dict]:
    """Valida un payload contra el contrato. Devuelve la lista de hallazgos."""
    out: list[dict] = []

    def add(sev: str, field: str, detail: str):
        out.append({"contract": contract.name, "severity": sev, "field": field, "detail": detail})

    for field, typ in contract.required.items():
        if field not in payload:
            add("ERROR", field, "campo obligatorio ausente")
            continue
        val = payload[field]
        if val is None:
            if field not in contract.nullable:
                add("ERROR", field, "null en un campo no nullable")
            continue
        if typ is float and isinstance(val, int) and not isinstance(val, bool):
            continue  # int donde se espera float es aceptable
        if not isinstance(val, typ):
            add(
                "ERROR",
                field,
                f"tipo {type(val).__name__}, se esperaba {TYPE_NAMES.get(typ, typ.__name__)}",
            )

    for field, allowed in (contract.enums or {}).items():
        if field in payload and payload[field] is not None and payload[field] not in allowed:
            add("ERROR", field, f"valor '{payload[field]}' fuera del enum {allowed}")

    for field in contract.datetime_fields:
        if field not in payload or payload[field] is None:
            continue
        val = payload[field]
        parsed = _parse_dt(val)
        if parsed is None:
            add("ERROR", field, f"no parseable como fecha/hora: {val!r}")
        elif parsed.tzinfo is None:
            add("ERROR", field, "timestamp sin zona horaria: exigir ISO-8601 con offset")

    extra = set(payload) - set(contract.required)
    if extra:
        add("INFO", ",".join(sorted(extra)), "campos no declarados en el contrato (posible drift)")
    return out


def _parse_dt(val) -> datetime | None:
    if isinstance(val, datetime):
        return val
    if not isinstance(val, str):
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None


def timezone_audit(df: pd.DataFrame, columns: list[str], expected_tz: str = "America/Santiago") -> pd.DataFrame:
    """Audita columnas de fecha/hora de un export del cliente.

    Detecta: naive vs aware, zona distinta a la esperada, y el sintoma clasico
    del desfase de zona — actividad concentrada fuera del horario de turno.
    """
    rows = []
    for col in columns:
        if col not in df.columns:
            rows.append({"column": col, "issue": "ERROR", "detail": "columna ausente"})
            continue

        s = pd.to_datetime(df[col], errors="coerce")
        naive = s.dt.tz is None
        n_bad = int(s.isna().sum())

        detail = []
        if n_bad:
            detail.append(f"{n_bad} valores no parseables")
        if naive:
            detail.append("sin zona horaria (naive)")
        else:
            if str(s.dt.tz) != expected_tz:
                detail.append(f"zona {s.dt.tz}, se esperaba {expected_tz}")

        # Sintoma de desfase: picos de actividad de madrugada.
        hours = (s.dt.tz_localize(None) if not naive else s).dt.hour
        night = float(((hours >= 0) & (hours < 5)).mean())
        if night > 0.15:
            detail.append(f"{night:.0%} de los eventos entre 00:00 y 05:00: revisar offset")

        rows.append(
            {
                "column": col,
                "issue": "ERROR" if (naive or n_bad) else ("WARN" if detail else "OK"),
                "detail": "; ".join(detail) or "sin hallazgos",
            }
        )
    return pd.DataFrame(rows)


def retry_idempotency_check(events: pd.DataFrame, key_cols: list[str]) -> dict:
    """¿El reintento duplica? Busca claves de negocio repetidas.

    Un despacho duplicado por un reintento sin idempotencia es el incidente que
    termina en una llamada del gerente general un sabado."""
    dup = events.duplicated(subset=key_cols, keep=False)
    n = int(dup.sum())
    return {
        "key": key_cols,
        "duplicate_rows": n,
        "duplicate_pct": round(n / max(len(events), 1) * 100, 3),
        "sample": events[dup].head(5).to_dict("records") if n else [],
        "verdict": "OK" if n == 0 else "el endpoint no es idempotente: exigir clave de idempotencia",
    }
