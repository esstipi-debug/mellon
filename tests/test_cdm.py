"""El modelo canonico de datos vendorizado (``fdekit.cdm``) y su puente con el kit.

``src/fdekit/cdm.py`` es una copia byte a byte de ``kern/src/cdm.py``. El primer
test fija su sha256 al MISMO valor que fija Kern: si falla, alguien edito la copia
de este lado. El cambio se hace en Kern y se copia entero (ver el encabezado del
modulo).
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from fdekit import cdm
from fdekit.cdm import CdmError, from_record
from fdekit.cdm_bridge import cycle_count_to_cdm, risk_level, risk_tier, scrap_to_cdm, yard_gate_to_cdm
from fdekit.ithildin import RiskLevel

ROOT = Path(__file__).resolve().parent.parent
CDM_PATH = ROOT / "src" / "fdekit" / "cdm.py"

#: sha256 de src/fdekit/cdm.py. El MISMO valor esta fijado en kern/tests/test_cdm.py.
CDM_SHA256 = "dc290a58057f68df4e516fa1482bc4b97e3375e4646cbf629aa2e3e7b2eb7f5f"

T0 = datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)


def test_la_copia_vendorizada_no_diverge():
    digest = hashlib.sha256(CDM_PATH.read_bytes()).hexdigest()
    assert digest == CDM_SHA256, (
        "src/fdekit/cdm.py no es la copia de kern/src/cdm.py. No se edita aca: el cambio se "
        "hace en Kern, se sube CDM_VERSION y se copia el archivo entero. "
        f"Hash actual: {digest}"
    )


def test_solo_usa_la_biblioteca_estandar():
    tree = ast.parse(CDM_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module.split(".")[0])
    ajenos = {n for n in imported if n not in sys.stdlib_module_names and n != "__future__"}
    assert not ajenos, f"el kit corre sin instalar nada: cdm.py importa {sorted(ajenos)}"


# ---- eventos fisicos, leidos por atributo ------------------------------------------

def _count(**over):
    base = dict(
        transaction_id="TX-0000000000000001",
        sku_scanned="SKU-1",
        bin_location="A-01-02",
        counted_quantity=11,
        manifest_expected_units=12,
        scan_timestamp=T0,
    )
    return SimpleNamespace(**{**base, **over})


def test_un_conteo_ciego_llega_con_su_diferencia_y_su_procedencia():
    record = json.loads(json.dumps(cycle_count_to_cdm(_count())))
    item, prov = from_record(record)
    assert item.variance == -1
    assert item.counted_at == "2026-10-01T09:30:00+00:00"
    assert (prov.source_system, prov.source_id) == ("fdekit", "TX-0000000000000001")


def test_un_conteo_sin_zona_horaria_no_se_adivina():
    with pytest.raises(CdmError, match="zona horaria"):
        cycle_count_to_cdm(_count(scan_timestamp=datetime(2026, 10, 1, 9, 30)))


def test_la_porteria_toma_como_utc_lo_que_su_contrato_toma_como_utc():
    event = SimpleNamespace(
        transaction_id="TX-0000000000000002",
        delivery_id="DLV-0001",
        carrier_id="CARR1",
        geofence_id="GATE-1",
        telemetry_timestamp=datetime(2026, 10, 1, 8, 0),
    )
    item, _ = from_record(yard_gate_to_cdm(event))
    assert (item.location, item.arrived_at) == ("GATE-1", "2026-10-01T08:00:00+00:00")


# ---- nivel de riesgo -------------------------------------------------------------

@pytest.mark.parametrize("level", list(RiskLevel))
def test_cada_nivel_de_ithildin_tiene_su_par_canonico(level):
    assert risk_tier(level) in cdm.RISK_TIERS
    assert risk_level(risk_tier(level)) is level


def test_los_dos_vocabularios_tienen_los_mismos_niveles():
    assert {risk_tier(level) for level in RiskLevel} == set(cdm.RISK_TIERS)


def test_un_nivel_desconocido_se_rechaza():
    with pytest.raises(CdmError, match="risk_tier"):
        risk_level("READ")


# ---- contra los contratos pydantic reales -------------------------------------------

@pytest.fixture
def contratos():
    pytest.importorskip("pydantic")
    sys.path.insert(0, str(ROOT))
    try:
        import core_event_contracts
    finally:
        sys.path.remove(str(ROOT))
    return core_event_contracts


def test_los_motivos_de_baja_son_los_del_contrato(contratos):
    assert {r.value.lower() for r in contratos.ScrapDispositionReason} == set(cdm.SCRAP_REASONS)


def test_los_tres_eventos_reales_pasan_al_cdm(contratos):
    blind = hashlib.sha256(b"A-01-02:SKU-0001:12").hexdigest()
    count = contratos.BlindCycleCountEvent(
        transaction_id="TX-0000000000000003",
        delivery_id="DLV-0002",
        bin_location="A-01-02",
        sku_scanned="SKU-0001",
        counted_quantity=12,
        manifest_expected_units=12,
        rf_device_id="RF-01",
        scan_timestamp=T0,
        blind_token_hash=blind,
    )
    scrap = contratos.ScrapDisposalEvent(
        transaction_id="TX-0000000000000004",
        delivery_id="DLV-0003",
        operator_badge_id="OP-01",
        sku_id="SKU-0001",
        disposal_bin_id="BIN-9",
        reason_code=contratos.ScrapDispositionReason.EXPIRED_LOT,
        theoretical_unit_weight_kg=Decimal("1.5"),
        scale_measured_total_weight_kg=Decimal("3.0"),
        units_declared=2,
        photo_verification_hash="a" * 64,
        disposal_timestamp=T0,
    )
    gate = contratos.YardGateEvent(
        transaction_id="TX-0000000000000005",
        delivery_id="DLV-0004",
        truck_license_plate="ABCD12",
        carrier_id="CARR1",
        latitude=Decimal("-33.45"),
        longitude=Decimal("-70.66"),
        geofence_id="GATE-1",
        telemetry_timestamp=T0,
        is_transponder_active=True,
        optical_plate_scan_match=True,
        scale_weight_kg=Decimal("12000"),
        cryptographic_signature="b" * 64,
    )
    kinds = [from_record(r)[0].KIND for r in (cycle_count_to_cdm(count), scrap_to_cdm(scrap), yard_gate_to_cdm(gate))]
    assert kinds == ["cycle_count", "scrap_disposal", "gate_arrival"]
    assert from_record(scrap_to_cdm(scrap))[0].reason == "expired_lot"
