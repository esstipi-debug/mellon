"""Regresiones de seguridad del kit de guardias (antiguos ``xfail`` de limites conocidos, hoy cerrados).

Cada prueba verifica una propiedad criptografica, temporal, de idempotencia persistente o de
segregacion de funciones en ``core_event_contracts``, ``inbound_fsm_guardrail`` e ``IthildinGuard``.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from core_event_contracts import (
    BlindCycleCountEvent,
    ErpLedgerPostEvent,
    ReturnAuthorizationEvent,
    ScrapDisposalEvent,
    ScrapDispositionReason,
    YardGateEvent,
    compute_hmac_proof,
    normalize_utc_timestamp,
)
from fdekit.ithildin.guards import IthildinGuard, RiskLevel, StagingAction
from inbound_fsm_guardrail import (
    InboundDeliveryFSM,
    PhysicalProofMissingError,
    ReplayAttackDetectedError,
)

SECRET = b"known-limits-secret-0123456789ab"
OTRO_SECRETO = b"another-secret-0123456789abcdef!"
CATALOGO = {"SKU-1": Decimal("2.0000")}


def _patio(delivery_id: str, ts: datetime, tx_id: str = "TX-LIMITES-0000001") -> YardGateEvent:
    """Un evento del patio con los dos sensores en verdad y firmado con SECRET."""
    campos = dict(
        transaction_id=tx_id,
        delivery_id=delivery_id,
        truck_license_plate="AB123CD",
        carrier_id="CARRIER-LOGIX",
        latitude=Decimal("-33.4569"),
        longitude=Decimal("-70.6483"),
        geofence_id="GATE-DC-01",
        telemetry_timestamp=ts,
        is_transponder_active=True,
        optical_plate_scan_match=True,
        scale_weight_kg=Decimal("15420.50"),
        cryptographic_signature="0" * 64,
    )
    sin_firma = YardGateEvent(**campos)
    firma = compute_hmac_proof(SECRET, sin_firma.canonical_signing_payload())
    return YardGateEvent(**{**campos, "cryptographic_signature": firma})


def _conteo_ciego(
    delivery_id: str,
    ts: datetime,
    counted: int,
    expected: int,
    tx_id: str = "TX-LIMITES-BLIND-01",
    secret: bytes = SECRET,
) -> BlindCycleCountEvent:
    bin_loc = "A-01"
    sku = "SKU-1"
    token = compute_hmac_proof(secret, f"{bin_loc}|{sku}|{expected}")
    return BlindCycleCountEvent(
        transaction_id=tx_id,
        delivery_id=delivery_id,
        bin_location=bin_loc,
        sku_scanned=sku,
        counted_quantity=counted,
        manifest_expected_units=expected,
        rf_device_id="RF-01",
        scan_timestamp=ts,
        blind_token_hash=token,
    )


def _accion() -> StagingAction:
    return StagingAction(
        action_id="A-LIMITES-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="erp",
        payload={"sku": "SKU-1", "reorder_point": 120},
        idempotency_key="K-LIMITES-1",
        timestamp_utc="2024-01-05T02:30:00+00:00",
    )


# ---- automata de recepcion (inbound_fsm_guardrail / core_event_contracts) --------------


def test_the_yard_signature_covers_the_sensor_flags():
    bueno = _patio("DELIV-LIMITES-01", datetime.now(timezone.utc))
    assert bueno.verify_hmac_signature(SECRET) is True
    alterado = bueno.model_copy(update={"is_transponder_active": False, "optical_plate_scan_match": False})
    assert alterado.verify_hmac_signature(SECRET) is False


def test_the_approver_key_is_not_the_gateway_key():
    with pytest.raises(ValueError, match="approver_secret"):
        InboundDeliveryFSM("DELIV-LIMITES-02", hmac_secret=SECRET, approver_secret=SECRET)

    base = datetime.now(timezone.utc) - timedelta(seconds=120)
    fsm = InboundDeliveryFSM("DELIV-LIMITES-02", hmac_secret=SECRET, approver_secret=OTRO_SECRETO)
    fsm.transition_to("GATE_ARRIVED", _patio("DELIV-LIMITES-02", base, tx_id="TX-LIM-02-GATE-01"))
    fsm.transition_to("WEIGHED_IN", _patio("DELIV-LIMITES-02", base + timedelta(seconds=10), tx_id="TX-LIM-02-WGH-001"))
    fsm.transition_to(
        "UNLOADING_ACTIVE", _patio("DELIV-LIMITES-02", base + timedelta(seconds=20), tx_id="TX-LIM-02-UNL-001")
    )
    fsm.transition_to(
        "CLEARED_COMPLETE", _conteo_ciego("DELIV-LIMITES-02", base + timedelta(seconds=30), 50, 50, tx_id="TX-LIM-02-CNT-001")
    )

    ts_post = base + timedelta(seconds=40)
    payload_post = f"TX-LIM-02-ERP-BAD|DELIV-LIMITES-02|105|50|{ts_post.isoformat()}"
    forged_by_gateway = ErpLedgerPostEvent(
        transaction_id="TX-LIM-02-ERP-BAD",
        delivery_id="DELIV-LIMITES-02",
        reference_movement_code="105",
        posted_units=50,
        posting_timestamp=ts_post,
        approver_hmac_signature=compute_hmac_proof(SECRET, payload_post),
    )
    with pytest.raises(PhysicalProofMissingError):
        fsm.transition_to("POSTED_TO_ERP", forged_by_gateway)

    payload_ok = f"TX-LIM-02-ERP-OK1|DELIV-LIMITES-02|105|50|{ts_post.isoformat()}"
    signed_by_approver = ErpLedgerPostEvent(
        transaction_id="TX-LIM-02-ERP-OK1",
        delivery_id="DELIV-LIMITES-02",
        reference_movement_code="105",
        posted_units=50,
        posting_timestamp=ts_post,
        approver_hmac_signature=compute_hmac_proof(OTRO_SECRETO, payload_ok),
    )
    assert fsm.transition_to("POSTED_TO_ERP", signed_by_approver) == "POSTED_TO_ERP"


def test_a_fresh_fsm_refuses_a_stale_signed_event():
    delivery = "DELIV-LIMITES-03"
    viejo = _patio(delivery, datetime.now(timezone.utc) - timedelta(seconds=901))
    fsm = InboundDeliveryFSM(delivery, hmac_secret=SECRET)
    with pytest.raises(ReplayAttackDetectedError):
        fsm.transition_to("GATE_ARRIVED", viejo)


def test_a_second_fsm_refuses_an_already_consumed_event(tmp_path):
    db = tmp_path / "nonces.db"
    delivery = "DELIV-LIMITES-04"
    evento = _patio(delivery, datetime.now(timezone.utc))
    InboundDeliveryFSM(delivery, hmac_secret=SECRET, nonce_store_path=db).transition_to("GATE_ARRIVED", evento)
    with pytest.raises(ReplayAttackDetectedError):
        InboundDeliveryFSM(delivery, hmac_secret=SECRET, nonce_store_path=db).transition_to("GATE_ARRIVED", evento)


# ---- guardia Ithildin (fdekit.ithildin.guards) ------------------------------------------


def test_ithildin_refuses_an_expired_signed_action():
    guardia = IthildinGuard(secret_key=SECRET)
    accion = _accion()
    veredicto = guardia.evaluate_and_commit(accion, guardia.sign_action(accion))
    assert veredicto.approved is False
    assert veredicto.code == "REJECTED_EXPIRED_ACTION"

    vigente = StagingAction(
        action_id="A-LIMITES-1-OK",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="erp",
        payload={"sku": "SKU-1", "reorder_point": 120},
        idempotency_key="K-LIMITES-1-OK",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )
    assert guardia.evaluate_and_commit(vigente, guardia.sign_action(vigente)).approved is True


def test_ithildin_action_names_its_approver():
    assert "approved_by" in {campo.name for campo in dataclasses.fields(StagingAction)}
    with pytest.raises(ValueError, match="approved_by"):
        StagingAction(
            action_id="A-LIMITES-APR-BAD",
            risk_level=RiskLevel.REVERSIBLE,
            target_system="erp",
            payload={"sku": "SKU-1"},
            idempotency_key="K-LIMITES-APR-BAD",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            approved_by="   ",
        )

    guardia = IthildinGuard(secret_key=SECRET)
    accion = StagingAction(
        action_id="A-LIMITES-APR-OK",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="erp",
        payload={"sku": "SKU-1"},
        idempotency_key="K-LIMITES-APR-OK",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        approved_by="supervisor-01",
    )
    token = guardia.sign_action(accion)
    assert guardia.verify_signature(accion, token) is True
    suplantada = dataclasses.replace(accion, approved_by="otro-usuario")
    assert guardia.verify_signature(suplantada, token) is False


def test_ithildin_idempotency_survives_a_new_instance(tmp_path):
    db = tmp_path / "ithildin.db"
    accion = StagingAction(
        action_id="A-LIMITES-IDEMP-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="erp",
        payload={"sku": "SKU-1", "reorder_point": 120},
        idempotency_key="K-LIMITES-IDEMP-1",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        approved_by="supervisor-01",
    )
    primera = IthildinGuard(secret_key=SECRET, store_path=db)
    token = primera.sign_action(accion)
    assert primera.evaluate_and_commit(accion, token).approved is True
    segunda = IthildinGuard(secret_key=SECRET, store_path=db)
    veredicto = segunda.evaluate_and_commit(accion, token)
    assert veredicto.approved is False
    assert veredicto.code == "REJECTED_DUPLICATE_IDEMPOTENCY"


# ---- limites adicionales detectados en auditoria forense ---------------------------------


def test_blind_count_token_is_keyed_not_plaintext_sha256():
    expected = 50
    token_sin_clave = hashlib.sha256(f"A-01:SKU-1:{expected}".encode()).hexdigest()
    with pytest.raises(ValidationError):
        BlindCycleCountEvent(
            transaction_id="TX-LIMITES-BLIND-01",
            delivery_id="DELIV-LIMITES-05",
            bin_location="A-01",
            sku_scanned="SKU-1",
            counted_quantity=48,
            manifest_expected_units=expected,
            rf_device_id="RF-01",
            scan_timestamp=datetime.now(timezone.utc),
            blind_token_hash=token_sin_clave,
        )

    ev_keyed = _conteo_ciego("DELIV-LIMITES-05", datetime.now(timezone.utc), 48, expected)
    assert ev_keyed.verify_blind_token(SECRET) is True
    assert ev_keyed.verify_blind_token(OTRO_SECRETO) is False


def test_scrap_disposal_requires_hmac_signature():
    base = datetime.now(timezone.utc) - timedelta(seconds=60)
    campos = dict(
        transaction_id="TX-LIMITES-SCRAP-01",
        delivery_id="DELIV-LIMITES-06",
        operator_badge_id="BADGE-01",
        sku_id="SKU-1",
        disposal_bin_id="BIN-01",
        reason_code=ScrapDispositionReason.DAMAGED_IN_TRANSIT,
        theoretical_unit_weight_kg=Decimal("2.0000"),
        scale_measured_total_weight_kg=Decimal("4.0000"),
        units_declared=2,
        photo_verification_hash="0" * 64,
        disposal_timestamp=base + timedelta(seconds=40),
        cryptographic_signature="0" * 64,
    )
    forged = ScrapDisposalEvent(**campos)
    assert forged.verify_hmac_signature(SECRET) is False

    signed = ScrapDisposalEvent(
        **{**campos, "cryptographic_signature": compute_hmac_proof(SECRET, forged.canonical_signing_payload())}
    )
    assert signed.verify_hmac_signature(SECRET) is True

    fsm = InboundDeliveryFSM("DELIV-LIMITES-06", hmac_secret=SECRET, catalog_unit_weights=CATALOGO)
    fsm.transition_to("GATE_ARRIVED", _patio("DELIV-LIMITES-06", base, tx_id="TX-LIM-06-GATE-01"))
    fsm.transition_to("WEIGHED_IN", _patio("DELIV-LIMITES-06", base + timedelta(seconds=10), tx_id="TX-LIM-06-WGH-001"))
    fsm.transition_to(
        "UNLOADING_ACTIVE", _patio("DELIV-LIMITES-06", base + timedelta(seconds=20), tx_id="TX-LIM-06-UNL-001")
    )
    fsm.transition_to(
        "DISCREPANCY_HOLD", _conteo_ciego("DELIV-LIMITES-06", base + timedelta(seconds=30), 48, 50, tx_id="TX-LIM-06-CNT-001")
    )
    with pytest.raises(PhysicalProofMissingError):
        fsm.transition_to("SCRAP_RECORDED", forged)
    assert fsm.transition_to("SCRAP_RECORDED", signed) == "SCRAP_RECORDED"


def test_return_authorization_requires_hmac_signature():
    base = datetime.now(timezone.utc) - timedelta(seconds=60)
    campos = dict(
        transaction_id="TX-LIMITES-RET-01",
        delivery_id="DELIV-LIMITES-07",
        reference_movement_code="124",
        rejected_units=5,
        inspector_badge_id="INSP-01",
        carrier_acknowledgment_hash="0" * 64,
        authorization_timestamp=base + timedelta(seconds=40),
        cryptographic_signature="0" * 64,
    )
    forged = ReturnAuthorizationEvent(**campos)
    assert forged.verify_hmac_signature(SECRET) is False

    signed = ReturnAuthorizationEvent(
        **{**campos, "cryptographic_signature": compute_hmac_proof(SECRET, forged.canonical_signing_payload())}
    )
    assert signed.verify_hmac_signature(SECRET) is True

    fsm = InboundDeliveryFSM("DELIV-LIMITES-07", hmac_secret=SECRET)
    fsm.transition_to("GATE_ARRIVED", _patio("DELIV-LIMITES-07", base, tx_id="TX-LIM-07-GATE-01"))
    fsm.transition_to("WEIGHED_IN", _patio("DELIV-LIMITES-07", base + timedelta(seconds=10), tx_id="TX-LIM-07-WGH-001"))
    fsm.transition_to(
        "UNLOADING_ACTIVE", _patio("DELIV-LIMITES-07", base + timedelta(seconds=20), tx_id="TX-LIM-07-UNL-001")
    )
    fsm.transition_to(
        "DISCREPANCY_HOLD", _conteo_ciego("DELIV-LIMITES-07", base + timedelta(seconds=30), 45, 50, tx_id="TX-LIM-07-CNT-001")
    )
    with pytest.raises(PhysicalProofMissingError):
        fsm.transition_to("RETURN_ISSUED", forged)
    assert fsm.transition_to("RETURN_ISSUED", signed) == "RETURN_ISSUED"


def test_naive_timestamp_is_rejected_fail_closed():
    with pytest.raises(ValueError, match="FAIL_CLOSED"):
        normalize_utc_timestamp(datetime(2026, 1, 5, 2, 30))
    aware_clt = datetime(2026, 1, 5, 2, 30, tzinfo=timezone(timedelta(hours=-3)))
    assert normalize_utc_timestamp(aware_clt) == datetime(2026, 1, 5, 5, 30, tzinfo=timezone.utc)


def test_ithildin_rejects_placeholder_rollback_plan():
    guardia = IthildinGuard(secret_key=SECRET)
    accion = StagingAction(
        action_id="A-LIMITES-RB-1",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="erp",
        payload={"sku": "SKU-1", "writeoff": 10},
        idempotency_key="K-LIMITES-RB-1",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        rollback_plan={"todo": "later"},
    )
    veredicto = guardia.evaluate_and_commit(accion, guardia.sign_action(accion))
    assert veredicto.approved is False
    assert veredicto.code == "REJECTED_INVALID_ROLLBACK_PLAN"

    ejecutable = StagingAction(
        action_id="A-LIMITES-RB-2",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="erp",
        payload={"sku": "SKU-1", "writeoff": 10},
        idempotency_key="K-LIMITES-RB-2",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        rollback_plan={"strategy": "reverse_movement", "reversal_movement": "102"},
    )
    assert guardia.evaluate_and_commit(ejecutable, guardia.sign_action(ejecutable)).approved is True
