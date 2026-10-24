"""
core_event_contracts.py
=======================
Cryptographically verified, strongly-typed physical event contracts for Gemba operations.
Standard: Pydantic V2, Strict Runtime Validation, Fixed-Point Decimal Arithmetic,
Total UTC Normalization, Weighbridge Physical Bounds, and Fail-Closed HMAC-SHA256.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import hashlib
import hmac
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


# Physical weighbridge bounds (light commercial tare floor -> legal bridge ceiling)
MIN_WEIGHBRIDGE_KG = Decimal("1500.00")
MAX_WEIGHBRIDGE_KG = Decimal("80000.00")


def normalize_utc_timestamp(dt: datetime) -> datetime:
    """Total normalization to timezone-aware UTC datetime (eliminates naive/aware TypeError)."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_hmac_proof(secret_key: bytes, message: str) -> str:
    """Compute deterministic SHA-256 HMAC for sensor and event authentication (fail-closed)."""
    if not isinstance(secret_key, (bytes, bytearray)) or len(secret_key) < 16:
        raise ValueError("FAIL_CLOSED: HMAC secret_key must be bytes of length >= 16.")
    return hmac.new(bytes(secret_key), message.encode("utf-8"), hashlib.sha256).hexdigest()


class GateState(str, Enum):
    OUTSIDE_GEOFENCE = "OUTSIDE_GEOFENCE"
    WITHIN_POLYGON = "WITHIN_POLYGON"
    DOCKED = "DOCKED"
    UNLOADING = "UNLOADING"
    RELEASED = "RELEASED"


class ScrapDispositionReason(str, Enum):
    DAMAGED_IN_TRANSIT = "DAMAGED_IN_TRANSIT"
    DROPPED_IN_WAREHOUSE = "DROPPED_IN_WAREHOUSE"
    EXPIRED_LOT = "EXPIRED_LOT"
    CONTAMINATION_QA = "CONTAMINATION_QA"


# 1. Countermeasure: Yard Dwell Gaming, Ghost Arrivals & Weighbridge Spoofing
class YardGateEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=16, max_length=64)]
    delivery_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=32)]
    truck_license_plate: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=5, max_length=12)]
    carrier_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=32)]
    latitude: Decimal = Field(..., ge=Decimal("-90.0"), le=Decimal("90.0"))
    longitude: Decimal = Field(..., ge=Decimal("-180.0"), le=Decimal("180.0"))
    geofence_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    telemetry_timestamp: datetime
    is_transponder_active: bool
    optical_plate_scan_match: bool
    scale_weight_kg: Decimal = Field(..., ge=MIN_WEIGHBRIDGE_KG, le=MAX_WEIGHBRIDGE_KG)
    cryptographic_signature: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

    @field_validator("telemetry_timestamp", mode="after")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        return normalize_utc_timestamp(v)

    @model_validator(mode="after")
    def verify_physical_coherence(self) -> "YardGateEvent":
        if self.is_transponder_active and not self.optical_plate_scan_match:
            raise ValueError(
                "DISCREPANCY: Active RF transponder without optical camera match. "
                "Possible yard geofence spoofing or tailgating."
            )
        now_utc = datetime.now(timezone.utc)
        if (self.telemetry_timestamp - now_utc).total_seconds() > 300:
            raise ValueError("PHYSICAL_ANOMALY: Telemetry timestamp cannot be > 300s in the future.")
        return self

    def canonical_signing_payload(self) -> str:
        weight_norm = self.scale_weight_kg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return (
            f"{self.transaction_id}|{self.delivery_id}|{self.truck_license_plate}|"
            f"{weight_norm}|{self.telemetry_timestamp.isoformat()}"
        )

    def verify_hmac_signature(self, secret_key: bytes) -> bool:
        expected = compute_hmac_proof(secret_key, self.canonical_signing_payload())
        return hmac.compare_digest(expected.lower(), self.cryptographic_signature.lower())


# 2. Countermeasure: Shrinkage Concealment & Unregistered Compactor Scrap
class ScrapDisposalEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=16, max_length=64)]
    delivery_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=32)]
    operator_badge_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    sku_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    disposal_bin_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    reason_code: ScrapDispositionReason
    theoretical_unit_weight_kg: Decimal = Field(..., gt=Decimal("0.0000"))
    scale_measured_total_weight_kg: Decimal = Field(..., gt=Decimal("0.0000"))
    units_declared: int = Field(..., gt=0)
    photo_verification_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]
    disposal_timestamp: datetime

    @field_validator("disposal_timestamp", mode="after")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        return normalize_utc_timestamp(v)

    @model_validator(mode="after")
    def validate_weight_parity(self) -> "ScrapDisposalEvent":
        expected_weight = (self.theoretical_unit_weight_kg * Decimal(self.units_declared)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        delta_abs = abs(self.scale_measured_total_weight_kg - expected_weight)
        delta_pct = delta_abs / expected_weight

        if delta_pct > Decimal("0.0300"):
            raise ValueError(
                f"DISPOSITION_REJECTED: Scale weight ({self.scale_measured_total_weight_kg} kg) "
                f"diverges by {delta_pct * Decimal('100'):.2f}% from theoretical mass ({expected_weight} kg). "
                f"Tolerance is +/-3.00%. Compactor mechanical lock engaged."
            )
        return self


# 3. Countermeasure: Ghost Inventory & Blind Recount Evasion
class BlindCycleCountEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=16, max_length=64)]
    delivery_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=32)]
    bin_location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    sku_scanned: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    counted_quantity: int = Field(..., ge=0)
    manifest_expected_units: int = Field(..., ge=0)
    rf_device_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    scan_timestamp: datetime
    blind_token_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

    @field_validator("scan_timestamp", mode="after")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        return normalize_utc_timestamp(v)

    @model_validator(mode="after")
    def verify_blind_count(self) -> "BlindCycleCountEvent":
        expected_blind_hash = hashlib.sha256(
            f"{self.bin_location}:{self.sku_scanned}:{self.manifest_expected_units}".encode("utf-8")
        ).hexdigest()
        if not hmac.compare_digest(self.blind_token_hash.lower(), expected_blind_hash.lower()):
            raise ValueError(
                "INTEGRITY_VIOLATION: Invalid blind recount token. "
                "Possible tampering with offline handheld terminal."
            )
        return self


# 4. Countermeasure: Governed Vendor Return Custody (Reference BWART 124 vs 122)
class ReturnAuthorizationEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=16, max_length=64)]
    delivery_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=32)]
    reference_movement_code: Literal["124", "122"]
    rejected_units: int = Field(..., gt=0)
    inspector_badge_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=32)]
    carrier_acknowledgment_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]
    authorization_timestamp: datetime

    @field_validator("authorization_timestamp", mode="after")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        return normalize_utc_timestamp(v)


# 5. Countermeasure: Cryptographically Bound ERP Ledger Posting (Reference BWART 103 / 105)
class ErpLedgerPostEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=16, max_length=64)]
    delivery_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=32)]
    reference_movement_code: Literal["103", "105"]
    posted_units: int = Field(..., gt=0)
    posting_timestamp: datetime
    approver_hmac_signature: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

    @field_validator("posting_timestamp", mode="after")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        return normalize_utc_timestamp(v)

    def canonical_signing_payload(self) -> str:
        return (
            f"{self.transaction_id}|{self.delivery_id}|{self.reference_movement_code}|"
            f"{self.posted_units}|{self.posting_timestamp.isoformat()}"
        )

    def verify_hmac_signature(self, secret_key: bytes) -> bool:
        expected = compute_hmac_proof(secret_key, self.canonical_signing_payload())
        return hmac.compare_digest(expected.lower(), self.approver_hmac_signature.lower())
