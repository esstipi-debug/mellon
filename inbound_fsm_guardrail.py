"""
inbound_fsm_guardrail.py
========================
Finite State Machine enforcing physical telemetry proofs before ERP ledger mutations.
Standard: Deterministic Poka-Yoke, Zero-Bypass State Machine.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Union, Optional
from core_event_contracts import YardGateEvent, ScrapDisposalEvent, BlindCycleCountEvent


class InvalidStateTransitionError(Exception):
    """Raised when an illegal transition is attempted across state vertices."""
    pass


class PhysicalProofMissingError(Exception):
    """Raised when a state transition lacks cryptographic or sensor proof."""
    pass


class ReplayAttackDetectedError(Exception):
    """Raised when an event timestamp is older than the current state timestamp or replayed."""
    pass


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
        "CLOSED_RETURNED": []
    }

    def __init__(self, delivery_id: str):
        if not delivery_id or len(delivery_id.strip()) < 8:
            raise ValueError("delivery_id must be at least 8 alphanumeric characters.")
        self.delivery_id = delivery_id.strip()
        self.current_state = "ANNOUNCED"
        self.history: list[dict] = []
        self.telemetry_proofs: Dict[str, Union[YardGateEvent, ScrapDisposalEvent, BlindCycleCountEvent]] = {}
        self.last_event_timestamp: Optional[datetime] = None

    def get_current_state(self) -> str:
        return self.current_state

    def transition_to(
        self,
        target_state: str,
        proof_payload: Union[YardGateEvent, ScrapDisposalEvent, BlindCycleCountEvent]
    ) -> str:
        # 1. Verify topological transition validity
        allowed_targets = self.VALID_TRANSITIONS.get(self.current_state, [])
        if target_state not in allowed_targets:
            raise InvalidStateTransitionError(
                f"ILLEGAL_TRANSITION: Cannot transition from '{self.current_state}' to '{target_state}'. "
                f"Allowed downstream vertices: {allowed_targets}."
            )

        # 2. Strict type-enforcement: Disallow raw dicts or non-Pydantic contracts
        if not isinstance(proof_payload, (YardGateEvent, ScrapDisposalEvent, BlindCycleCountEvent)):
            raise PhysicalProofMissingError(
                f"TYPE_SECURITY_VIOLATION: proof_payload must be an instance of YardGateEvent, "
                f"ScrapDisposalEvent, or BlindCycleCountEvent. Received: {type(proof_payload).__name__}."
            )

        # Verify delivery_id binding consistency
        if proof_payload.delivery_id != self.delivery_id:
            raise PhysicalProofMissingError(
                f"BINDING_VIOLATION: proof delivery_id '{proof_payload.delivery_id}' does not match "
                f"FSM delivery_id '{self.delivery_id}'."
            )

        # 3. Extract and verify timestamp causality (Anti-Replay / Monotonicity)
        event_ts: datetime
        if isinstance(proof_payload, YardGateEvent):
            event_ts = proof_payload.telemetry_timestamp
        elif isinstance(proof_payload, ScrapDisposalEvent):
            event_ts = proof_payload.disposal_timestamp
        elif isinstance(proof_payload, BlindCycleCountEvent):
            event_ts = proof_payload.scan_timestamp

        if self.last_event_timestamp is not None:
            if event_ts < self.last_event_timestamp:
                raise ReplayAttackDetectedError(
                    f"TIMESTAMP_INVERSION: New event timestamp {event_ts.isoformat()} is prior to "
                    f"preceding state timestamp {self.last_event_timestamp.isoformat()}. Replay attack blocked."
                )

        # 4. State-specific domain verification
        if target_state == "GATE_ARRIVED":
            if not isinstance(proof_payload, YardGateEvent):
                raise PhysicalProofMissingError("GATE_ARRIVED requires a validated YardGateEvent instance.")
            if not (proof_payload.is_transponder_active and proof_payload.optical_plate_scan_match):
                raise PhysicalProofMissingError(
                    "DUAL_SENSOR_FAILURE: Simultaneous ALPR and RF transponder match is mandatory for GATE_ARRIVED."
                )

        elif target_state == "WEIGHED_IN":
            if not isinstance(proof_payload, YardGateEvent):
                raise PhysicalProofMissingError("WEIGHED_IN requires a validated YardGateEvent with scale weight.")
            if proof_payload.scale_weight_kg <= Decimal("0.0"):
                raise PhysicalProofMissingError("WEIGHED_IN scale weight must be strictly positive.")

        elif target_state == "UNLOADING_ACTIVE":
            if not isinstance(proof_payload, YardGateEvent):
                raise PhysicalProofMissingError("UNLOADING_ACTIVE requires validated yard dock telemetry.")

        elif target_state == "DISCREPANCY_HOLD":
            if not isinstance(proof_payload, BlindCycleCountEvent):
                raise PhysicalProofMissingError("DISCREPANCY_HOLD requires BlindCycleCountEvent documenting count.")
            if proof_payload.counted_quantity == proof_payload.manifest_expected_units:
                raise InvalidStateTransitionError(
                    "LOGICAL_CONFLICT: Counted units match manifest. State must proceed to CLEARED_COMPLETE."
                )

        elif target_state == "CLEARED_COMPLETE":
            if not isinstance(proof_payload, (BlindCycleCountEvent, YardGateEvent)):
                raise PhysicalProofMissingError("CLEARED_COMPLETE requires validated receipt or recount verification.")
            if isinstance(proof_payload, BlindCycleCountEvent):
                if proof_payload.counted_quantity != proof_payload.manifest_expected_units:
                    raise InvalidStateTransitionError(
                        "DISCREPANCY_DETECTED: Scanned units diverge from manifest. Redirect to DISCREPANCY_HOLD."
                    )

        elif target_state == "SCRAP_RECORDED":
            if not isinstance(proof_payload, ScrapDisposalEvent):
                raise PhysicalProofMissingError("SCRAP_RECORDED requires a validated ScrapDisposalEvent instance.")

        elif target_state == "POSTED_TO_ERP":
            # Mandatory audit: verify that previous state was CLEARED_COMPLETE and has valid telemetry
            if self.current_state != "CLEARED_COMPLETE":
                raise InvalidStateTransitionError(
                    f"SECURITY_VIOLATION: Cannot post to ERP from state '{self.current_state}'. "
                    f"Prerequisite state must be 'CLEARED_COMPLETE'."
                )
            if "GATE_ARRIVED" not in self.telemetry_proofs:
                raise PhysicalProofMissingError("AUDIT_FAILURE: Missing GATE_ARRIVED proof in execution ledger.")

        # 5. Persist to immutable memory ledger
        self.telemetry_proofs[target_state] = proof_payload
        self.last_event_timestamp = event_ts
        self.history.append({
            "from_state": self.current_state,
            "to_state": target_state,
            "timestamp": event_ts.isoformat(),
            "transaction_id": proof_payload.transaction_id,
            "proof_type": type(proof_payload).__name__
        })
        self.current_state = target_state
        return self.current_state
