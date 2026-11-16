"""Los limites conocidos del kit de guardias, fijados como pruebas que fallan a proposito (``xfail`` estricto).

Cada prueba afirma la propiedad que el kit **deberia** tener y que hoy no tiene. Mientras el kit no la
cumpla, la prueba falla y queda como ``xfailed``: la brecha esta escrita y medida. Si alguien la arregla, la
prueba pasa por sorpresa (``XPASS``) y, por ser estricta, rompe la suite: obliga a reemplazarla por la prueba
de verdad y a corregir lo que el libro y el README dicen del limite.

Lo que NO se afirma: que el kit sea inseguro para lo que dice ser. Es un kit de guardias con sondas (ver
README); estos son los limites que hay que leer antes de llevarlo a una instalacion.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core_event_contracts import YardGateEvent, compute_hmac_proof
from fdekit.ithildin.guards import IthildinGuard, RiskLevel, StagingAction
from inbound_fsm_guardrail import (
    InboundDeliveryFSM,
    PhysicalProofMissingError,
    ReplayAttackDetectedError,
)

SECRET = b"known-limits-secret-0123456789ab"
OTRO_SECRETO = b"another-secret-0123456789abcdef!"


def _patio(delivery_id: str, ts: datetime) -> YardGateEvent:
    """Un evento del patio con los dos sensores en verdad y firmado con SECRET."""
    campos = dict(
        transaction_id="TX-LIMITES-0000001",
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


@pytest.mark.xfail(
    strict=True,
    reason="la firma del patio cubre transaccion, entrega, patente, peso y hora, pero no los dos sensores "
    "(is_transponder_active, optical_plate_scan_match): quien reenvia el evento puede cambiarlos sin romperla",
)
def test_the_yard_signature_covers_the_sensor_flags():
    bueno = _patio("DELIV-LIMITES-01", datetime(2026, 1, 5, 2, 30, tzinfo=timezone.utc))
    alterado = bueno.model_copy(update={"is_transponder_active": False, "optical_plate_scan_match": False})
    assert alterado.verify_hmac_signature(SECRET) is False


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="no hay clave del aprobador distinta de la del gateway: el mismo secreto verifica los eventos del "
    "patio y la firma del aprobador de POSTED_TO_ERP, asi que un gateway comprometido firma como aprobador",
)
def test_the_approver_key_is_not_the_gateway_key():
    InboundDeliveryFSM("DELIV-LIMITES-02", hmac_secret=SECRET, approver_secret=OTRO_SECRETO)


@pytest.mark.xfail(
    strict=True,
    reason="no hay edad maxima del evento ni historial de transaction_id persistido: el conjunto de "
    "transacciones consumidas vive en la instancia, y una instancia nueva acepta un evento firmado viejo",
)
def test_a_fresh_fsm_refuses_a_stale_signed_event():
    delivery = "DELIV-LIMITES-03"
    viejo = _patio(delivery, datetime(2024, 1, 5, 2, 30, tzinfo=timezone.utc))
    fsm = InboundDeliveryFSM(delivery, hmac_secret=SECRET)
    with pytest.raises((PhysicalProofMissingError, ReplayAttackDetectedError)):
        fsm.transition_to("GATE_ARRIVED", viejo)


@pytest.mark.xfail(
    strict=True,
    reason="el historial de transaction_id consumidos vive en cada instancia del automata: el mismo evento "
    "firmado, ya aceptado por una instancia, lo acepta otra instancia nueva de la misma entrega",
)
def test_a_second_fsm_refuses_an_already_consumed_event():
    delivery = "DELIV-LIMITES-04"
    evento = _patio(delivery, datetime(2026, 1, 5, 2, 30, tzinfo=timezone.utc))
    InboundDeliveryFSM(delivery, hmac_secret=SECRET).transition_to("GATE_ARRIVED", evento)
    with pytest.raises(ReplayAttackDetectedError):
        InboundDeliveryFSM(delivery, hmac_secret=SECRET).transition_to("GATE_ARRIVED", evento)


# ---- guardia Ithildin (fdekit.ithildin.guards) ------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="IthildinGuard no vence una accion firmada: la especificacion habla de 900 s de vigencia y el codigo "
    "no compara timestamp_utc contra el reloj",
)
def test_ithildin_refuses_an_expired_signed_action():
    guardia = IthildinGuard(secret_key=SECRET)
    accion = _accion()
    veredicto = guardia.evaluate_and_commit(accion, guardia.sign_action(accion))
    assert veredicto.approved is False


@pytest.mark.xfail(
    strict=True,
    reason="StagingAction no lleva quien aprueba: el token prueba integridad de la accion, no autoria de la aprobacion",
)
def test_ithildin_action_names_its_approver():
    assert "approved_by" in {campo.name for campo in dataclasses.fields(StagingAction)}


@pytest.mark.xfail(
    strict=True,
    reason="las claves de idempotencia de IthildinGuard viven en memoria: otra instancia vuelve a aprobar la "
    "misma accion con el mismo token",
)
def test_ithildin_idempotency_survives_a_new_instance():
    accion = _accion()
    primera = IthildinGuard(secret_key=SECRET)
    token = primera.sign_action(accion)
    assert primera.evaluate_and_commit(accion, token).approved is True
    segunda = IthildinGuard(secret_key=SECRET)
    assert segunda.evaluate_and_commit(accion, token).approved is False
