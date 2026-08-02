"""Herramienta 7 — sonda de integracion.

Smoke tests contra el sandbox del cliente: EDI X12, contratos de API, husos
horarios y comportamiento en reintento. Corre en CI y en cada ventana de cambio.
El 70% de los incidentes post go-live no son del modelo: son un campo que cambio
de tipo, un timestamp sin zona, o un reintento que duplico un despacho.
"""

from .edi import X12Message, parse_x12, validate_transaction, smoke_report
from .contracts import ContractCheck, check_payload, retry_idempotency_check, timezone_audit

__all__ = [
    "X12Message",
    "parse_x12",
    "validate_transaction",
    "smoke_report",
    "ContractCheck",
    "check_payload",
    "timezone_audit",
    "retry_idempotency_check",
]
