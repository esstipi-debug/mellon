"""
test_gemba_invariants.py
========================
Property-Based Verification Harness for Gemba Invariants and FSM Determinism.
Standard: Hypothesis, Deterministic Seeded 50,000-Cycle Adversarial Campaign,
Fail-Closed HMAC Verification, Total UTC Monotonicity, Single-Use Proof Nonces,
Master Catalog Weight Parity, and Governed Return Custody (124 vs 122).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import random
import sys
import unittest

from hypothesis import Phase, given, settings, strategies as st
from pydantic import ValidationError

from core_event_contracts import (
    BlindCycleCountEvent,
    ErpLedgerPostEvent,
    ReturnAuthorizationEvent,
    ScrapDisposalEvent,
    ScrapDispositionReason,
    YardGateEvent,
    compute_hmac_proof,
)
from inbound_fsm_guardrail import (
    InboundDeliveryFSM,
    InvalidStateTransitionError,
    PhysicalProofMissingError,
    ReplayAttackDetectedError,
)

TEST_HMAC_SECRET = b"mellon-ithildin-edge-gateway-secret-2026"
MASTER_CATALOG_WEIGHTS = {
    "SKU-DAMAGED-01": Decimal("2.5000"),
    "SKU-PHARMA-009": Decimal("0.8500"),
}

invalid_hex_64 = st.text(
    alphabet="ghijklmnopqrstuvwxyzGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+",
    min_size=64,
    max_size=64,
)


def make_valid_yard_event(
    delivery_id: str,
    ts: datetime,
    scale_weight: Decimal = Decimal("15420.50"),
    tx_id: str = "TX-YARD-0000000001",
    secret: bytes = TEST_HMAC_SECRET,
) -> YardGateEvent:
    ts_utc = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    ts_utc = ts_utc.astimezone(timezone.utc)
    plate = "AB123CD"
    weight_norm = scale_weight.quantize(Decimal("0.01"))
    canonical = f"{tx_id}|{delivery_id}|{plate}|{weight_norm}|{ts_utc.isoformat()}"
    sig = compute_hmac_proof(secret, canonical)
    return YardGateEvent(
        transaction_id=tx_id,
        delivery_id=delivery_id,
        truck_license_plate=plate,
        carrier_id="CARRIER-LOGIX",
        latitude=Decimal("-33.4569"),
        longitude=Decimal("-70.6483"),
        geofence_id="GATE-DC-01",
        telemetry_timestamp=ts,
        is_transponder_active=True,
        optical_plate_scan_match=True,
        scale_weight_kg=scale_weight,
        cryptographic_signature=sig,
    )


def make_valid_blind_count_event(
    delivery_id: str,
    ts: datetime,
    counted: int,
    expected: int,
    tx_id: str = "TX-COUNT-0000000001",
) -> BlindCycleCountEvent:
    bin_loc = "A-12-04"
    sku = "SKU-PHARMA-009"
    token = hashlib.sha256(f"{bin_loc}:{sku}:{expected}".encode("utf-8")).hexdigest()
    return BlindCycleCountEvent(
        transaction_id=tx_id,
        delivery_id=delivery_id,
        bin_location=bin_loc,
        sku_scanned=sku,
        counted_quantity=counted,
        manifest_expected_units=expected,
        rf_device_id="RF-GUN-88",
        scan_timestamp=ts,
        blind_token_hash=token,
    )


def make_valid_erp_post_event(
    delivery_id: str,
    ts: datetime,
    posted_units: int,
    bwart: str = "105",
    tx_id: str = "TX-ERP-0000000001",
    secret: bytes = TEST_HMAC_SECRET,
) -> ErpLedgerPostEvent:
    ts_utc = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    ts_utc = ts_utc.astimezone(timezone.utc)
    canonical = f"{tx_id}|{delivery_id}|{bwart}|{posted_units}|{ts_utc.isoformat()}"
    sig = compute_hmac_proof(secret, canonical)
    return ErpLedgerPostEvent(
        transaction_id=tx_id,
        delivery_id=delivery_id,
        reference_movement_code=bwart,  # type: ignore[arg-type]
        posted_units=posted_units,
        posting_timestamp=ts,
        approver_hmac_signature=sig,
    )


class TestGembaInvariants(unittest.TestCase):

    # PROPERTY 1: Scale weight divergence > 3% must ALWAYS raise ValidationError
    @settings(max_examples=500, phases=[Phase.generate])
    @given(
        units=st.integers(min_value=1, max_value=500),
        unit_weight=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("50.0"), places=2),
        divergence_factor=st.one_of(
            st.decimals(min_value=Decimal("1.0310"), max_value=Decimal("2.5000"), places=4),
            st.decimals(min_value=Decimal("0.1000"), max_value=Decimal("0.9690"), places=4),
        ),
    )
    def test_property_scale_weight_divergence_blocked(self, units, unit_weight, divergence_factor):
        expected_weight = (unit_weight * Decimal(units)).quantize(Decimal("0.0001"))
        tampered_weight = (expected_weight * divergence_factor).quantize(Decimal("0.0001"))
        delta_pct = abs(tampered_weight - expected_weight) / expected_weight
        if delta_pct <= Decimal("0.0300"):
            tampered_weight = (expected_weight * Decimal("1.0500")).quantize(Decimal("0.0001"))
        photo_hash = hashlib.sha256(b"dummy").hexdigest()

        with self.assertRaises(ValidationError):
            ScrapDisposalEvent(
                transaction_id="TX-SCRAP-TAMPERED-01",
                delivery_id="DELIV-99887766",
                operator_badge_id="OP-1234",
                sku_id="SKU-DAMAGED-01",
                disposal_bin_id="BIN-01",
                reason_code=ScrapDispositionReason.DROPPED_IN_WAREHOUSE,
                theoretical_unit_weight_kg=unit_weight,
                scale_measured_total_weight_kg=tampered_weight,
                units_declared=units,
                photo_verification_hash=photo_hash,
                disposal_timestamp=datetime.now(timezone.utc),
            )

    # PROPERTY 2: Corrupted or non-hexadecimal SHA-256 hashes must ALWAYS raise ValidationError
    @settings(max_examples=500, phases=[Phase.generate])
    @given(bad_hash=invalid_hex_64)
    def test_property_corrupted_hash_rejected(self, bad_hash):
        with self.assertRaises(ValidationError):
            ScrapDisposalEvent(
                transaction_id="TX-SCRAP-BADHASH-01",
                delivery_id="DELIV-99887766",
                operator_badge_id="OP-1234",
                sku_id="SKU-DAMAGED-01",
                disposal_bin_id="BIN-01",
                reason_code=ScrapDispositionReason.EXPIRED_LOT,
                theoretical_unit_weight_kg=Decimal("1.00"),
                scale_measured_total_weight_kg=Decimal("10.00"),
                units_declared=10,
                photo_verification_hash=bad_hash,
                disposal_timestamp=datetime.now(timezone.utc),
            )

    # PROPERTY 3: Unvalidated dict injection must NEVER transition state
    @settings(max_examples=500, phases=[Phase.generate])
    @given(
        target_state=st.sampled_from(["GATE_ARRIVED", "WEIGHED_IN", "CLEARED_COMPLETE", "POSTED_TO_ERP"]),
        fake_dict=st.dictionaries(keys=st.text(min_size=1, max_size=10), values=st.booleans()),
    )
    def test_property_dictionary_injection_blocked(self, target_state, fake_dict):
        fsm = InboundDeliveryFSM("DELIV-SECURE-001", hmac_secret=TEST_HMAC_SECRET)
        with self.assertRaises((PhysicalProofMissingError, InvalidStateTransitionError)):
            fsm.transition_to(target_state, fake_dict)  # type: ignore[arg-type]

    # PROPERTY 4: Timestamp inversion, equal-timestamp replay, and duplicate transaction_id blocked (P2 + P3)
    @settings(max_examples=500, phases=[Phase.generate])
    @given(time_delta_seconds=st.integers(min_value=0, max_value=86400))
    def test_property_timestamp_inversion_and_equal_replay_blocked(self, time_delta_seconds):
        delivery_id = "DELIV-TIME-MONO-01"
        fsm = InboundDeliveryFSM(delivery_id, hmac_secret=TEST_HMAC_SECRET)
        t0 = datetime(2026, 10, 22, 10, 0, 0, tzinfo=timezone.utc)

        ev1 = make_valid_yard_event(delivery_id, t0, tx_id="TX-YARD-0000000001")
        fsm.transition_to("GATE_ARRIVED", ev1)

        t_non_increasing = t0 - timedelta(seconds=time_delta_seconds)
        ev2 = make_valid_yard_event(delivery_id, t_non_increasing, tx_id="TX-YARD-0000000002")

        with self.assertRaises(ReplayAttackDetectedError):
            fsm.transition_to("WEIGHED_IN", ev2)

    # PROPERTY 5: P1 Fail-Closed HMAC, P2 Naive/Aware UTC Safety, P4 124 Return Custody, P5 Bounds, P6 Catalog Parity
    def test_forensic_probes_p1_to_p6_closed(self):
        deliv = "DELIV-PROBE-CLOSURE"
        t0_naive = datetime(2026, 10, 22, 2, 30, 0)  # naive timestamp (P2)
        t1_aware = datetime(2026, 10, 22, 2, 32, 0, tzinfo=timezone.utc)

        # P1a: Missing secret must fail closed
        fsm_no_secret = InboundDeliveryFSM(deliv, hmac_secret=None)
        ev_valid = make_valid_yard_event(deliv, t0_naive, tx_id="TX-YARD-P1A-000001")
        with self.assertRaises(PhysicalProofMissingError):
            fsm_no_secret.transition_to("GATE_ARRIVED", ev_valid)

        # P1b: Forged 64-hex signature ('a' * 64) must fail closed
        fsm = InboundDeliveryFSM(
            deliv,
            hmac_secret=TEST_HMAC_SECRET,
            catalog_unit_weights=MASTER_CATALOG_WEIGHTS,
        )
        ev_forged = YardGateEvent(
            transaction_id="TX-YARD-FORGED-0001",
            delivery_id=deliv,
            truck_license_plate="AB123CD",
            carrier_id="CARRIER-LOGIX",
            latitude=Decimal("-33.4569"),
            longitude=Decimal("-70.6483"),
            geofence_id="GATE-DC-01",
            telemetry_timestamp=t0_naive,
            is_transponder_active=True,
            optical_plate_scan_match=True,
            scale_weight_kg=Decimal("15420.50"),
            cryptographic_signature="a" * 64,
        )
        with self.assertRaises(PhysicalProofMissingError):
            fsm.transition_to("GATE_ARRIVED", ev_forged)

        # P5: Implausible weighbridge weights (0.01 kg or 999,999,999.99 kg) rejected
        for bad_w in (Decimal("0.01"), Decimal("999999999.99")):
            with self.assertRaises(ValidationError):
                make_valid_yard_event(deliv, t0_naive, scale_weight=bad_w, tx_id="TX-YARD-BADWEIGHT1")

        # P2: Naive followed by UTC-aware transitions cleanly without TypeError
        fsm.transition_to("GATE_ARRIVED", ev_valid)
        ev_weigh = make_valid_yard_event(deliv, t1_aware, tx_id="TX-YARD-WEIGH-0001")
        fsm.transition_to("WEIGHED_IN", ev_weigh)

        # P3: Reusing exact same event object (even if timestamp were bumped) blocked by consumed_transaction_ids
        with self.assertRaises((InvalidStateTransitionError, ReplayAttackDetectedError)):
            fsm.transition_to("UNLOADING_ACTIVE", ev_weigh)

        ev_unload = make_valid_yard_event(
            deliv, t1_aware + timedelta(seconds=60), tx_id="TX-YARD-UNLOAD-001"
        )
        fsm.transition_to("UNLOADING_ACTIVE", ev_unload)

        ev_hold = make_valid_blind_count_event(
            deliv, t1_aware + timedelta(seconds=120), counted=480, expected=500, tx_id="TX-CNT-HOLD-00001"
        )
        fsm.transition_to("DISCREPANCY_HOLD", ev_hold)

        # P6: Self-consistent scrap payload with spoofed unit_weight (9.99 kg != 2.50 kg catalog) blocked
        ev_spoofed_catalog = ScrapDisposalEvent(
            transaction_id="TX-SCRAP-SPOOF-001",
            delivery_id=deliv,
            operator_badge_id="OP-7721",
            sku_id="SKU-DAMAGED-01",
            disposal_bin_id="BIN-SCRAP-9",
            reason_code=ScrapDispositionReason.DAMAGED_IN_TRANSIT,
            theoretical_unit_weight_kg=Decimal("9.9900"),
            scale_measured_total_weight_kg=Decimal("199.8000"),
            units_declared=20,
            photo_verification_hash=hashlib.sha256(b"photo").hexdigest(),
            disposal_timestamp=t1_aware + timedelta(seconds=180),
        )
        with self.assertRaises(PhysicalProofMissingError):
            fsm.transition_to("SCRAP_RECORDED", ev_spoofed_catalog)

        # P4a: Recycled YardGateEvent cannot authorize RETURN_ISSUED
        ev_yard_recycle = make_valid_yard_event(
            deliv, t1_aware + timedelta(seconds=200), tx_id="TX-YARD-RECYCLE-01"
        )
        with self.assertRaises(PhysicalProofMissingError):
            fsm.transition_to("RETURN_ISSUED", ev_yard_recycle)

        # P4b: Pre-105 blocked return using movement '122' instead of '124' is rejected
        ev_bad_122 = ReturnAuthorizationEvent(
            transaction_id="TX-RET-BAD122-0001",
            delivery_id=deliv,
            reference_movement_code="122",
            rejected_units=20,
            inspector_badge_id="QA-09",
            carrier_acknowledgment_hash=hashlib.sha256(b"ack").hexdigest(),
            authorization_timestamp=t1_aware + timedelta(seconds=210),
        )
        with self.assertRaises(InvalidStateTransitionError):
            fsm.transition_to("RETURN_ISSUED", ev_bad_122)

        # Valid '124' origin return authorization succeeds and closes cleanly
        ev_ok_124 = ReturnAuthorizationEvent(
            transaction_id="TX-RET-OK124-00001",
            delivery_id=deliv,
            reference_movement_code="124",
            rejected_units=20,
            inspector_badge_id="QA-09",
            carrier_acknowledgment_hash=hashlib.sha256(b"ack").hexdigest(),
            authorization_timestamp=t1_aware + timedelta(seconds=220),
        )
        self.assertEqual(fsm.transition_to("RETURN_ISSUED", ev_ok_124), "RETURN_ISSUED")
        ev_exit = make_valid_yard_event(
            deliv, t1_aware + timedelta(seconds=300), scale_weight=Decimal("8200.00"), tx_id="TX-YARD-EXIT-00001"
        )
        self.assertEqual(fsm.transition_to("CLOSED_RETURNED", ev_exit), "CLOSED_RETURNED")

    def test_fuzzing_campaign_accounting_invariant(self):
        """Verifies deterministic fuzzing campaign accounts for 100% of branches with zero violations."""
        summary = run_50000_fuzzing_campaign(seed=20261024, total_attempts=700, quiet=True)
        self.assertEqual(summary["violations"], 0)
        self.assertEqual(sum(summary["counters"].values()), 700)


def run_50000_fuzzing_campaign(
    seed: int = 20261024,
    total_attempts: int = 50000,
    quiet: bool = False,
) -> dict:
    """
    Executes a deterministic, reproducible campaign of 50,000 randomized adversarial cycles
    against InboundDeliveryFSM with exact branch accounting (sum of outcomes == total_attempts).
    """
    rng = random.Random(seed)
    counters = {
        "blocked_illegal_transitions": 0,
        "blocked_weight_divergences": 0,
        "blocked_hash_or_hmac_forgeries": 0,
        "blocked_replay_or_nonce_reuse": 0,
        "blocked_dict_injections": 0,
        "successful_valid_full_lifecycles": 0,
        "successful_valid_single_step_arrivals": 0,
    }
    invariant_violations = 0

    states = [
        "ANNOUNCED",
        "GATE_ARRIVED",
        "WEIGHED_IN",
        "UNLOADING_ACTIVE",
        "DISCREPANCY_HOLD",
        "CLEARED_COMPLETE",
        "SCRAP_RECORDED",
        "RETURN_ISSUED",
        "POSTED_TO_ERP",
    ]
    attack_vectors = [
        "VALID_HAPPY_PATH",
        "OUT_OF_ORDER_JUMP",
        "DICT_INJECTION",
        "TAMPERED_WEIGHT",
        "TIMESTAMP_OR_NONCE_REPLAY",
        "FORGED_HMAC_OR_HASH",
        "RANDOM_WALK",
    ]

    now_campaign = datetime(2026, 10, 23, 0, 0, 0, tzinfo=timezone.utc)
    for cycle in range(1, total_attempts + 1):
        deliv_id = f"DELIV-FUZZ-{cycle:06d}"
        fsm = InboundDeliveryFSM(
            deliv_id,
            hmac_secret=TEST_HMAC_SECRET,
            catalog_unit_weights=MASTER_CATALOG_WEIGHTS,
        )
        t_base = now_campaign + timedelta(milliseconds=cycle * 10)
        attack_type = rng.choice(attack_vectors)

        if attack_type == "VALID_HAPPY_PATH":
            e1 = make_valid_yard_event(deliv_id, t_base, tx_id=f"TX-Y1-{cycle:012d}")
            fsm.transition_to("GATE_ARRIVED", e1)
            e2 = make_valid_yard_event(
                deliv_id, t_base + timedelta(seconds=120), Decimal("18500.00"), tx_id=f"TX-Y2-{cycle:012d}"
            )
            fsm.transition_to("WEIGHED_IN", e2)
            e3 = make_valid_yard_event(
                deliv_id, t_base + timedelta(seconds=240), Decimal("18500.00"), tx_id=f"TX-Y3-{cycle:012d}"
            )
            fsm.transition_to("UNLOADING_ACTIVE", e3)
            e4 = make_valid_blind_count_event(
                deliv_id, t_base + timedelta(seconds=360), 500, 500, tx_id=f"TX-C4-{cycle:012d}"
            )
            fsm.transition_to("CLEARED_COMPLETE", e4)
            e5 = make_valid_erp_post_event(
                deliv_id, t_base + timedelta(seconds=420), 500, "105", tx_id=f"TX-P5-{cycle:012d}"
            )
            fsm.transition_to("POSTED_TO_ERP", e5)
            counters["successful_valid_full_lifecycles"] += 1

        elif attack_type == "OUT_OF_ORDER_JUMP":
            e = make_valid_yard_event(deliv_id, t_base, tx_id=f"TX-OO-{cycle:012d}")
            try:
                fsm.transition_to("POSTED_TO_ERP", e)
                invariant_violations += 1
            except InvalidStateTransitionError:
                counters["blocked_illegal_transitions"] += 1

        elif attack_type == "DICT_INJECTION":
            try:
                fsm.transition_to("GATE_ARRIVED", {"lpr_verified": True, "scale_weight_kg": 15000})  # type: ignore[arg-type]
                invariant_violations += 1
            except PhysicalProofMissingError:
                counters["blocked_dict_injections"] += 1

        elif attack_type == "TAMPERED_WEIGHT":
            try:
                ScrapDisposalEvent(
                    transaction_id=f"TX-SCRAP-{cycle:012d}",
                    delivery_id=deliv_id,
                    operator_badge_id="OP-1001",
                    sku_id="SKU-DAMAGED-01",
                    disposal_bin_id="BIN-01",
                    reason_code=ScrapDispositionReason.DAMAGED_IN_TRANSIT,
                    theoretical_unit_weight_kg=Decimal("2.5000"),
                    scale_measured_total_weight_kg=Decimal("26.5000"),  # +6% error on 10 units
                    units_declared=10,
                    photo_verification_hash=hashlib.sha256(b"x").hexdigest(),
                    disposal_timestamp=t_base,
                )
                invariant_violations += 1
            except ValidationError:
                counters["blocked_weight_divergences"] += 1

        elif attack_type == "TIMESTAMP_OR_NONCE_REPLAY":
            e1 = make_valid_yard_event(deliv_id, t_base, tx_id=f"TX-RP1-{cycle:012d}")
            fsm.transition_to("GATE_ARRIVED", e1)
            if cycle % 2 == 0:
                e_bad = make_valid_yard_event(deliv_id, t_base, tx_id=f"TX-RP2-{cycle:012d}")  # equal ts
            else:
                e_bad = e1  # reused nonce
            try:
                fsm.transition_to("WEIGHED_IN", e_bad)
                invariant_violations += 1
            except ReplayAttackDetectedError:
                counters["blocked_replay_or_nonce_reuse"] += 1

        elif attack_type == "FORGED_HMAC_OR_HASH":
            if cycle % 2 == 0:
                forged = YardGateEvent(
                    transaction_id=f"TX-FORG-{cycle:012d}",
                    delivery_id=deliv_id,
                    truck_license_plate="AB123CD",
                    carrier_id="CARRIER-LOGIX",
                    latitude=Decimal("-33.4569"),
                    longitude=Decimal("-70.6483"),
                    geofence_id="GATE-DC-01",
                    telemetry_timestamp=t_base,
                    is_transponder_active=True,
                    optical_plate_scan_match=True,
                    scale_weight_kg=Decimal("15420.50"),
                    cryptographic_signature="a" * 64,
                )
                try:
                    fsm.transition_to("GATE_ARRIVED", forged)
                    invariant_violations += 1
                except PhysicalProofMissingError:
                    counters["blocked_hash_or_hmac_forgeries"] += 1
            else:
                try:
                    ScrapDisposalEvent(
                        transaction_id=f"TX-BADH-{cycle:012d}",
                        delivery_id=deliv_id,
                        operator_badge_id="OP-1001",
                        sku_id="SKU-DAMAGED-01",
                        disposal_bin_id="BIN-01",
                        reason_code=ScrapDispositionReason.DAMAGED_IN_TRANSIT,
                        theoretical_unit_weight_kg=Decimal("2.5000"),
                        scale_measured_total_weight_kg=Decimal("25.0000"),
                        units_declared=10,
                        photo_verification_hash="Z" * 64,
                        disposal_timestamp=t_base,
                    )
                    invariant_violations += 1
                except ValidationError:
                    counters["blocked_hash_or_hmac_forgeries"] += 1

        elif attack_type == "RANDOM_WALK":
            target = rng.choice(states)
            e = make_valid_yard_event(deliv_id, t_base, tx_id=f"TX-RW-{cycle:012d}")
            try:
                fsm.transition_to(target, e)
                if target == "GATE_ARRIVED":
                    counters["successful_valid_single_step_arrivals"] += 1
                else:
                    invariant_violations += 1
            except (InvalidStateTransitionError, PhysicalProofMissingError):
                counters["blocked_illegal_transitions"] += 1

    total_accounted = sum(counters.values()) + invariant_violations
    assert total_accounted == total_attempts, (
        f"Unaccounted fuzz cycles: {total_accounted} != {total_attempts}"
    )
    satisfaction_pct = 100.0 * (total_attempts - invariant_violations) / total_attempts

    if not quiet:
        print("=" * 80)
        print(f"DETERMINISTIC FUZZING CAMPAIGN SUMMARY (seed={seed}):")
        print(f"Total Cycles Evaluated & Accounted:        {total_accounted:,} / {total_attempts:,}")
        for k, v in counters.items():
            print(f"  - {k:40s}: {v:,}")
        print(f"  - {'invariant_violations':40s}: {invariant_violations:,}")
        print(f"EMPIRICAL INVARIANT SATISFACTION RATE:     {satisfaction_pct:.3f}%")
        print("=" * 80)
    if invariant_violations > 0:
        sys.exit(1)
    return {"seed": seed, "total": total_attempts, "counters": counters, "violations": invariant_violations}


if __name__ == "__main__":
    run_50000_fuzzing_campaign()
