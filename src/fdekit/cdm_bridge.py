"""Puente entre lo que mide el kit y el modelo canonico de datos (``fdekit.cdm``).

``fdekit.cdm`` es una copia byte a byte de ``kern/src/cdm.py`` y no se edita aca
(ver su encabezado). Este modulo hace el mapeo de cada lado del kit hacia el CDM,
para que lo que se mide en el piso llegue a Kern sin que nadie reescriba campos.
Por ejemplo, un conteo ciclico ciego termina como el estante con el que Kern
dimensiona.

Dos mapeos:

* **Eventos fisicos** (``core_event_contracts.py``): porteria, conteo ciclico ciego
  y baja de mercaderia. Se leen por atributo, sin importar pydantic, porque pydantic
  no es dependencia del kit y el contrato vive fuera del paquete.
* **Nivel de riesgo** de Ithildin al vocabulario de ``nosilo_core.writeback``. Los
  tres niveles son los mismos, escritos en mayuscula de este lado.

Una diferencia que el CDM NO resuelve, y hay que saberla antes de mezclar los dos
planos de escritura: si una clave de idempotencia se repite, Ithildin RECHAZA
(``REJECTED_DUPLICATE_IDEMPOTENCY``) y Kern lo trata como un reintento y lo SALTEA
(``idempotent_skip=True``). Las dos cosas evitan una doble escritura, pero quien
llama tiene que actuar distinto en cada caso.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fdekit.cdm import (
    RISK_TIERS,
    CdmError,
    CycleCount,
    GateArrival,
    Provenance,
    ScrapDisposal,
    to_record,
)
from fdekit.ithildin import RiskLevel

#: Sistema de origen de todo lo que el kit emite.
SOURCE_SYSTEM = "fdekit"


def _instant(name: str, value: datetime, *, naive_is_utc: bool = False) -> str:
    if value.tzinfo is None:
        if not naive_is_utc:
            raise CdmError(
                f"{name}: el evento trae un instante sin zona horaria y su contrato no dice "
                "cual es; no se adivina"
            )
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _provenance(event: Any) -> Provenance:
    return Provenance(source_system=SOURCE_SYSTEM, source_id=event.transaction_id)


def yard_gate_to_cdm(event: Any) -> dict[str, Any]:
    """``YardGateEvent`` -> ``gate_arrival``. La ubicacion es la geocerca.

    Un instante sin zona se toma como UTC porque es lo que hace el propio
    ``YardGateEvent.verify_physical_coherence``. Los otros dos eventos no declaran
    nada parecido, asi que con ellos un instante sin zona se rechaza.
    """
    item = GateArrival(
        delivery_id=event.delivery_id,
        carrier_id=event.carrier_id,
        location=event.geofence_id,
        arrived_at=_instant("telemetry_timestamp", event.telemetry_timestamp, naive_is_utc=True),
    )
    return to_record(item, _provenance(event))


def cycle_count_to_cdm(event: Any) -> dict[str, Any]:
    """``BlindCycleCountEvent`` -> ``cycle_count``, con lo que esperaba el manifiesto."""
    item = CycleCount(
        sku=event.sku_scanned,
        location=event.bin_location,
        counted_qty=event.counted_quantity,
        counted_at=_instant("scan_timestamp", event.scan_timestamp),
        expected_qty=event.manifest_expected_units,
    )
    return to_record(item, _provenance(event))


def scrap_to_cdm(event: Any) -> dict[str, Any]:
    """``ScrapDisposalEvent`` -> ``scrap_disposal``. La ubicacion es el contenedor de baja."""
    reason = getattr(event.reason_code, "value", event.reason_code)
    item = ScrapDisposal(
        sku=event.sku_id,
        location=event.disposal_bin_id,
        units=event.units_declared,
        reason=str(reason).lower(),
        disposed_at=_instant("disposal_timestamp", event.disposal_timestamp),
        measured_weight_kg=float(event.scale_measured_total_weight_kg),
    )
    return to_record(item, _provenance(event))


def risk_tier(level: RiskLevel) -> str:
    """``RiskLevel`` de Ithildin -> nivel canonico (``"read"``, ``"reversible"``, ``"irreversible"``)."""
    tier = RiskLevel(level).value.lower()
    if tier not in RISK_TIERS:
        raise CdmError(f"risk_level: {level!r} no tiene equivalente canonico")
    return tier


def risk_level(tier: str) -> RiskLevel:
    """Nivel canonico -> ``RiskLevel`` de Ithildin."""
    if tier not in RISK_TIERS:
        raise CdmError(f"risk_tier: tiene que ser uno de {RISK_TIERS}, vino {tier!r}")
    return RiskLevel(tier.upper())
