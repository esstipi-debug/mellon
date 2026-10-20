"""Guardarrailes deterministas y safe-staging criptografico con HMAC-SHA256.

El Patron Ithildin:
La proteccion permanece en silencio e invisible durante la operacion nominal.
Solo se "ilumina" (rechaza, bloquea y genera traza auditable) cuando un agente
o integracion intenta una mutacion que viola contratos, carece de idempotencia,
o pretende escribir en un sistema transaccional sin plan de rollback verificado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
from typing import Any, Mapping


class RiskLevel(str, Enum):
    """Nivel de riesgo operacional de una propuesta de accion."""

    READ = "READ"  # Solo lectura, riesgo nulo sobre base de datos
    REVERSIBLE = "REVERSIBLE"  # Escritura compensable (ej. crear borrador, reserva temporal)
    IRREVERSIBLE = "IRREVERSIBLE"  # Mutacion destructiva o financiera (ej. anular factura, mover stock real)


@dataclass(frozen=True)
class StagingAction:
    """Propuesta inmutable de accion generada por un agente o pipeline antes de tocar produccion."""

    action_id: str
    risk_level: RiskLevel
    target_system: str
    payload: Mapping[str, Any]
    idempotency_key: str
    timestamp_utc: str
    rollback_plan: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("action_id no puede ser vacio")
        if not self.target_system:
            raise ValueError("target_system no puede ser vacio")
        if not self.idempotency_key:
            raise ValueError("idempotency_key no puede ser vacia: toda accion debe ser idempotente")
        if not self.timestamp_utc:
            raise ValueError("timestamp_utc no puede ser vacio: auditoria temporal estricta requerida")

    def canonical_bytes(self) -> bytes:
        """Serializacion canonica determinista para calculo de firma."""
        normalized = {
            "action_id": self.action_id,
            "risk_level": self.risk_level.value,
            "target_system": self.target_system,
            "payload": self.payload,
            "idempotency_key": self.idempotency_key,
            "timestamp_utc": self.timestamp_utc,
            "rollback_plan": self.rollback_plan,
        }
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


@dataclass(frozen=True)
class StagingVerdict:
    """Veredicto determinista de evaluacion de staging."""

    approved: bool
    code: str
    reason: str
    audit_hash: str
    evaluated_at_utc: str


class IthildinGuard:
    """Motor determinista de validacion y firma de acciones para integraciones y agentes."""

    def __init__(self, secret_key: bytes) -> None:
        if not secret_key or len(secret_key) < 16:
            raise ValueError("secret_key debe tener al menos 16 bytes de entropia para HMAC-SHA256")
        self._secret = secret_key
        self._committed_keys: set[str] = set()
        self._audit_ledger: list[StagingVerdict] = []

    def sign_action(self, action: StagingAction) -> str:
        """Genera el token HMAC-SHA256 que firma criptograficamente la accion en staging."""
        raw = action.canonical_bytes()
        sig = hmac.new(self._secret, raw, hashlib.sha256).hexdigest()
        return f"ithildin-v1-{sig}"

    def verify_signature(self, action: StagingAction, token: str) -> bool:
        """Verifica si el token corresponde a la accion exacta usando comparacion en tiempo constante."""
        if not token.startswith("ithildin-v1-"):
            return False
        expected_token = self.sign_action(action)
        return hmac.compare_digest(token, expected_token)

    def evaluate_and_commit(self, action: StagingAction, token: str) -> StagingVerdict:
        """Evalua la accion contra guardarrailes deterministas.

        Si se aprueba, la clave de idempotencia queda consumida en el ledger in-memory.
        Si se rechaza, la accion se ilumina (falla) con procedencia clara.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        audit_hash = hashlib.sha256(action.canonical_bytes()).hexdigest()

        # 1. Verificacion de firma criptografica
        if not self.verify_signature(action, token):
            verdict = StagingVerdict(
                approved=False,
                code="FORBIDDEN_INVALID_SIGNATURE",
                reason="El token HMAC no coincide o el payload fue adulterado.",
                audit_hash=audit_hash,
                evaluated_at_utc=now_utc,
            )
            self._audit_ledger.append(verdict)
            return verdict

        # 2. Verificacion de idempotencia
        if action.idempotency_key in self._committed_keys:
            verdict = StagingVerdict(
                approved=False,
                code="REJECTED_DUPLICATE_IDEMPOTENCY",
                reason=f"La clave de idempotencia '{action.idempotency_key}' ya fue consumida previamente.",
                audit_hash=audit_hash,
                evaluated_at_utc=now_utc,
            )
            self._audit_ledger.append(verdict)
            return verdict

        # 3. Guardarrail de reversibilidad obligatoria
        if action.risk_level == RiskLevel.IRREVERSIBLE and not action.rollback_plan:
            verdict = StagingVerdict(
                approved=False,
                code="REJECTED_IRREVERSIBLE_WITHOUT_ROLLBACK",
                reason="Las acciones IRREVERSIBLE requieren obligatoriamente un rollback_plan estructurado.",
                audit_hash=audit_hash,
                evaluated_at_utc=now_utc,
            )
            self._audit_ledger.append(verdict)
            return verdict

        # Si pasa todas las compuertas, se aprueba y se compromete
        self._committed_keys.add(action.idempotency_key)
        verdict = StagingVerdict(
            approved=True,
            code="APPROVED_FOR_WRITEBACK",
            reason="Accion validada deterministamente con firma integra y plan de contingencia.",
            audit_hash=audit_hash,
            evaluated_at_utc=now_utc,
        )
        self._audit_ledger.append(verdict)
        return verdict

    @property
    def audit_ledger(self) -> list[StagingVerdict]:
        """Registro inmutable de veredictos emitidos."""
        return list(self._audit_ledger)
