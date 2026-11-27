"""
inbound_fsm_guardrail.py
========================
Finite State Machine enforcing physical telemetry proofs before ERP ledger mutations.
Standard: Deterministic Poka-Yoke, Fail-Closed HMAC Authentication (with SoD Approver Key),
Total UTC Monotonicity, Event Freshness TTL, Persistent Single-Use Nonce Consumption,
Master Catalog Weight Parity, and Governed Return Custody.
"""

import hmac
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from core_event_contracts import (
    MAX_WEIGHBRIDGE_KG,
    MIN_WEIGHBRIDGE_KG,
    BlindCycleCountEvent,
    ErpLedgerPostEvent,
    ReturnAuthorizationEvent,
    ScrapDisposalEvent,
    YardGateEvent,
    normalize_utc_timestamp,
)

ProofContract = (
    YardGateEvent
    | ScrapDisposalEvent
    | BlindCycleCountEvent
    | ReturnAuthorizationEvent
    | ErpLedgerPostEvent
)


class InvalidStateTransitionError(Exception):
    """Raised when an illegal transition is attempted across state vertices."""


class PhysicalProofMissingError(Exception):
    """Raised when a state transition lacks cryptographic, catalog, or sensor proof."""


class ReplayAttackDetectedError(Exception):
    """Raised when an event timestamp is non-monotonic/stale or a transaction_id is reused."""


class InboundDeliveryFSM:
    VALID_TRANSITIONS = {
        "ANNOUNCED": ["GATE_ARRIVED"],
        "GATE_ARRIVED": ["WEIGHED_IN"],
        "WEIGHED_IN": ["UNLOADING_ACTIVE"],
        "UNLOADING_ACTIVE": ["DISCREPANCY_HOLD", "CLEARED_COMPLETE"],
        "DISCREPANCY_HOLD": ["SCRAP_RECORDED", "RETURN_ISSUED"],
        "SCRAP_RECORDED": ["CLEARED_COMPLETE"],
        "RETURN_ISSUED": ["CLOSED_RETURNED"],
        "CLEARED_COMPLETE": ["POSTED_TO_ERP"],
        "POSTED_TO_ERP": [],
        "CLOSED_RETURNED": [],
    }

    def __init__(
        self,
        delivery_id: str,
        hmac_secret: bytes | None = None,
        catalog_unit_weights: dict[str, Decimal] | None = None,
        *,
        approver_secret: bytes | None = None,
        max_event_age_seconds: float = 900.0,
        nonce_store_path: str | Path | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        if not delivery_id or len(delivery_id.strip()) < 8:
            raise ValueError("delivery_id must be at least 8 alphanumeric characters.")
        if (
            approver_secret is not None
            and hmac_secret is not None
            and hmac.compare_digest(bytes(approver_secret), bytes(hmac_secret))
        ):
            raise ValueError("FAIL_CLOSED: approver_secret must be distinct from gateway hmac_secret.")
        if max_event_age_seconds < 0:
            raise ValueError("FAIL_CLOSED: max_event_age_seconds cannot be negative.")

        self.delivery_id = delivery_id.strip()
        self.hmac_secret = hmac_secret
        self.approver_secret = approver_secret
        self.max_event_age_seconds = float(max_event_age_seconds)
        self.nonce_store_path = Path(nonce_store_path) if nonce_store_path is not None else None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.catalog_unit_weights = dict(catalog_unit_weights) if catalog_unit_weights is not None else None
        self.current_state = "ANNOUNCED"
        self.history: list[dict] = []
        self.telemetry_proofs: dict[str, ProofContract] = {}
        self.consumed_transaction_ids: set[str] = set()
        self.last_event_timestamp: datetime | None = None

        if self.nonce_store_path is not None:
            self._init_nonce_store()

    def _init_nonce_store(self) -> None:
        assert self.nonce_store_path is not None
        self.nonce_store_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.nonce_store_path)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS consumed_nonces ("
                "transaction_id TEXT PRIMARY KEY, "
                "delivery_id TEXT NOT NULL, "
                "consumed_at_utc TEXT NOT NULL)"
            )
            conn.commit()

    def _is_nonce_consumed_in_store(self, transaction_id: str) -> bool:
        if self.nonce_store_path is None:
            return False
        with closing(sqlite3.connect(self.nonce_store_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM consumed_nonces WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
            return row is not None

    def _record_nonce_in_store(self, transaction_id: str, consumed_at_utc: datetime) -> None:
        if self.nonce_store_path is None:
            return
        with closing(sqlite3.connect(self.nonce_store_path)) as conn:
            try:
                conn.execute(
                    "INSERT INTO consumed_nonces (transaction_id, delivery_id, consumed_at_utc) VALUES (?, ?, ?)",
                    (transaction_id, self.delivery_id, consumed_at_utc.isoformat()),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ReplayAttackDetectedError(
                    f"REPLAY_BLOCKED: transaction_id '{transaction_id}' was already consumed."
                ) from exc

    def get_current_state(self) -> str:
        return self.current_state

    def _require_hmac_secret(self) -> bytes:
        if not isinstance(self.hmac_secret, (bytes, bytearray)) or len(self.hmac_secret) < 16:
            raise PhysicalProofMissingError(
                "FAIL_CLOSED: Gateway HMAC secret missing or shorter than 16 bytes."
            )
        return bytes(self.hmac_secret)

    def _require_approver_secret(self) -> bytes:
        if not isinstance(self.approver_secret, (bytes, bytearray)) or len(self.approver_secret) < 16:
            raise PhysicalProofMissingError(
                "FAIL_CLOSED: Approver HMAC secret missing or shorter than 16 bytes."
            )
        if self.hmac_secret is not None and hmac.compare_digest(
            bytes(self.approver_secret), bytes(self.hmac_secret)
        ):
            raise PhysicalProofMissingError(
                "FAIL_CLOSED: approver_secret must be distinct from gateway hmac_secret."
            )
        return bytes(self.approver_secret)

    @staticmethod
    def _extract_utc_timestamp(proof_payload: ProofContract) -> datetime:
        if isinstance(proof_payload, YardGateEvent):
            return normalize_utc_timestamp(proof_payload.telemetry_timestamp)
        if isinstance(proof_payload, ScrapDisposalEvent):
            return normalize_utc_timestamp(proof_payload.disposal_timestamp)
        if isinstance(proof_payload, BlindCycleCountEvent):
            return normalize_utc_timestamp(proof_payload.scan_timestamp)
        if isinstance(proof_payload, ReturnAuthorizationEvent):
            return normalize_utc_timestamp(proof_payload.authorization_timestamp)
        if isinstance(proof_payload, ErpLedgerPostEvent):
            return normalize_utc_timestamp(proof_payload.posting_timestamp)
        raise PhysicalProofMissingError("Unsupported proof contract timestamp.")

    def transition_to(
        self,
        target_state: str,
        proof_payload: ProofContract,
    ) -> str:
        # 1. Verify topological transition validity
        allowed_targets = self.VALID_TRANSITIONS.get(self.current_state, [])
        if target_state not in allowed_targets:
            raise InvalidStateTransitionError(
                f"ILLEGAL_TRANSITION: Cannot transition from '{self.current_state}' to '{target_state}'. "
                f"Allowed downstream vertices: {allowed_targets}."
            )

        # 2. Strict type enforcement: disallow raw dicts or unverified objects
        if not isinstance(
            proof_payload,
            (
                YardGateEvent,
                ScrapDisposalEvent,
                BlindCycleCountEvent,
                ReturnAuthorizationEvent,
                ErpLedgerPostEvent,
            ),
        ):
            raise PhysicalProofMissingError(
                f"TYPE_SECURITY_VIOLATION: proof_payload must be a verified Pydantic event contract. "
                f"Received: {type(proof_payload).__name__}."
            )

        # 3. Verify delivery_id binding consistency
        if proof_payload.delivery_id != self.delivery_id:
            raise PhysicalProofMissingError(
                f"BINDING_VIOLATION: proof delivery_id '{proof_payload.delivery_id}' does not match "
                f"FSM delivery_id '{self.delivery_id}'."
            )

        # 4. Single-consumption anti-replay check (blocks recycling the same physical event)
        if (
            proof_payload.transaction_id in self.consumed_transaction_ids
            or self._is_nonce_consumed_in_store(proof_payload.transaction_id)
        ):
            raise ReplayAttackDetectedError(
                f"REPLAY_BLOCKED: transaction_id '{proof_payload.transaction_id}' was already consumed."
            )

        # 5. Event freshness TTL and strict UTC timestamp monotonicity
        event_ts = self._extract_utc_timestamp(proof_payload)
        now_utc = normalize_utc_timestamp(self._clock())
        if (now_utc - event_ts).total_seconds() > self.max_event_age_seconds:
            raise ReplayAttackDetectedError(
                f"STALE_EVENT_REJECTED: Event timestamp {event_ts.isoformat()} exceeds "
                f"max_event_age_seconds={self.max_event_age_seconds} relative to {now_utc.isoformat()}."
            )
        if self.last_event_timestamp is not None and event_ts <= self.last_event_timestamp:
            raise ReplayAttackDetectedError(
                f"TIMESTAMP_MONOTONICITY_VIOLATION: Event timestamp {event_ts.isoformat()} is not "
                f"strictly newer than preceding timestamp {self.last_event_timestamp.isoformat()}."
            )

        # 6. State-specific domain, provenance, and catalog verification
        if target_state == "GATE_ARRIVED":
            if not isinstance(proof_payload, YardGateEvent):
                raise PhysicalProofMissingError("GATE_ARRIVED requires a validated YardGateEvent.")
            if not (proof_payload.is_transponder_active and proof_payload.optical_plate_scan_match):
                raise PhysicalProofMissingError(
                    "DUAL_SENSOR_FAILURE: Simultaneous ALPR and RF transponder match is mandatory."
                )
            secret = self._require_hmac_secret()
            if not proof_payload.verify_hmac_signature(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Forged or unauthenticated yard gateway signature."
                )

        elif target_state == "WEIGHED_IN":
            if not isinstance(proof_payload, YardGateEvent):
                raise PhysicalProofMissingError("WEIGHED_IN requires a validated YardGateEvent.")
            if not (MIN_WEIGHBRIDGE_KG <= proof_payload.scale_weight_kg <= MAX_WEIGHBRIDGE_KG):
                raise PhysicalProofMissingError("WEIGHED_IN weight outside physical bridge bounds.")
            secret = self._require_hmac_secret()
            if not proof_payload.verify_hmac_signature(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Forged or unauthenticated weighbridge signature."
                )

        elif target_state == "UNLOADING_ACTIVE":
            if not isinstance(proof_payload, YardGateEvent):
                raise PhysicalProofMissingError("UNLOADING_ACTIVE requires validated dock telemetry.")
            secret = self._require_hmac_secret()
            if not proof_payload.verify_hmac_signature(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Forged or unauthenticated dock signature."
                )

        elif target_state == "DISCREPANCY_HOLD":
            if not isinstance(proof_payload, BlindCycleCountEvent):
                raise PhysicalProofMissingError("DISCREPANCY_HOLD requires a BlindCycleCountEvent.")
            secret = self._require_hmac_secret()
            if not proof_payload.verify_blind_token(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Invalid keyed blind cycle count token on DISCREPANCY_HOLD."
                )
            if proof_payload.counted_quantity == proof_payload.manifest_expected_units:
                raise InvalidStateTransitionError(
                    "LOGICAL_CONFLICT: Counted units match manifest; proceed to CLEARED_COMPLETE."
                )

        elif target_state == "CLEARED_COMPLETE":
            if not isinstance(proof_payload, BlindCycleCountEvent):
                raise PhysicalProofMissingError(
                    "CLEARED_COMPLETE requires a verified BlindCycleCountEvent."
                )
            secret = self._require_hmac_secret()
            if not proof_payload.verify_blind_token(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Invalid keyed blind cycle count token on CLEARED_COMPLETE."
                )
            if self.current_state == "UNLOADING_ACTIVE":
                if proof_payload.counted_quantity != proof_payload.manifest_expected_units:
                    raise InvalidStateTransitionError(
                        "DISCREPANCY_DETECTED: Scanned units diverge from manifest; route to DISCREPANCY_HOLD."
                    )
            elif self.current_state == "SCRAP_RECORDED":
                scrap_ev = self.telemetry_proofs.get("SCRAP_RECORDED")
                if not isinstance(scrap_ev, ScrapDisposalEvent):
                    raise PhysicalProofMissingError("Missing SCRAP_RECORDED proof prior to clearance.")
                if proof_payload.counted_quantity + scrap_ev.units_declared != proof_payload.manifest_expected_units:
                    raise InvalidStateTransitionError(
                        "MASS_BALANCE_MISMATCH: Good units plus recorded scrap do not reconcile to manifest."
                    )

        elif target_state == "SCRAP_RECORDED":
            if not isinstance(proof_payload, ScrapDisposalEvent):
                raise PhysicalProofMissingError("SCRAP_RECORDED requires a ScrapDisposalEvent.")
            secret = self._require_hmac_secret()
            if not proof_payload.verify_hmac_signature(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Forged or unauthenticated scrap disposal signature."
                )
            if self.catalog_unit_weights is None:
                raise PhysicalProofMissingError(
                    "FAIL_CLOSED: Master catalog unit weights required to verify scrap parity."
                )
            if proof_payload.sku_id not in self.catalog_unit_weights:
                raise PhysicalProofMissingError(
                    f"UNKNOWN_CATALOG_SKU: '{proof_payload.sku_id}' absent from master catalog."
                )
            master_unit_kg = self.catalog_unit_weights[proof_payload.sku_id]
            if abs(proof_payload.theoretical_unit_weight_kg - master_unit_kg) > Decimal("0.0001"):
                raise PhysicalProofMissingError(
                    f"CATALOG_PARITY_VIOLATION: Payload unit weight ({proof_payload.theoretical_unit_weight_kg} kg) "
                    f"diverges from master catalog ({master_unit_kg} kg)."
                )

        elif target_state == "RETURN_ISSUED":
            if not isinstance(proof_payload, ReturnAuthorizationEvent):
                raise PhysicalProofMissingError(
                    "RETURN_ISSUED requires a dedicated ReturnAuthorizationEvent (reference 124/122)."
                )
            secret = self._require_hmac_secret()
            if not proof_payload.verify_hmac_signature(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Forged or unauthenticated return authorization signature."
                )
            # Prior to unrestricted release (105), origin rejection must use reference movement 124 (not 122)
            if proof_payload.reference_movement_code != "124":
                raise InvalidStateTransitionError(
                    "ACCOUNTING_VIOLATION: Pre-release blocked stock return must use movement '124', not '122'."
                )
            hold_ev = self.telemetry_proofs.get("DISCREPANCY_HOLD")
            if not isinstance(hold_ev, BlindCycleCountEvent):
                raise PhysicalProofMissingError("Missing DISCREPANCY_HOLD proof prior to RETURN_ISSUED.")

        elif target_state == "CLOSED_RETURNED":
            if not isinstance(proof_payload, YardGateEvent):
                raise PhysicalProofMissingError("CLOSED_RETURNED requires exit YardGateEvent proof.")
            secret = self._require_hmac_secret()
            if not proof_payload.verify_hmac_signature(secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Exit gate signature invalid on CLOSED_RETURNED."
                )

        elif target_state == "POSTED_TO_ERP":
            if not isinstance(proof_payload, ErpLedgerPostEvent):
                raise PhysicalProofMissingError(
                    "POSTED_TO_ERP requires a cryptographically signed ErpLedgerPostEvent (103/105)."
                )
            approver_secret = self._require_approver_secret()
            if not proof_payload.verify_hmac_signature(approver_secret):
                raise PhysicalProofMissingError(
                    "HMAC_VERIFICATION_FAILED: Invalid approver HMAC on ErpLedgerPostEvent."
                )
            cleared_ev = self.telemetry_proofs.get("CLEARED_COMPLETE")
            if not isinstance(cleared_ev, BlindCycleCountEvent) or "GATE_ARRIVED" not in self.telemetry_proofs:
                raise PhysicalProofMissingError(
                    "AUDIT_FAILURE: Complete physical provenance chain required before ERP posting."
                )
            if proof_payload.posted_units != cleared_ev.counted_quantity:
                raise InvalidStateTransitionError(
                    "QUANTITY_MISMATCH: Posted ERP units must equal verified cleared count."
                )

        # 7. Persist to immutable execution ledger (SQLite first so IntegrityError aborts atomically)
        self._record_nonce_in_store(proof_payload.transaction_id, now_utc)
        self.consumed_transaction_ids.add(proof_payload.transaction_id)
        self.telemetry_proofs[target_state] = proof_payload
        self.last_event_timestamp = event_ts
        self.history.append(
            {
                "from_state": self.current_state,
                "to_state": target_state,
                "timestamp": event_ts.isoformat(),
                "transaction_id": proof_payload.transaction_id,
                "proof_type": type(proof_payload).__name__,
            }
        )
        self.current_state = target_state
        return self.current_state
