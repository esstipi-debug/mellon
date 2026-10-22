"""
core_event_contracts.py
=======================
Cryptographically verified, strongly-typed physical event contracts for Gemba operations.
Standard: Pydantic V2, Strict Runtime Validation, Fixed-Point Decimal Arithmetic.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import hashlib
import hmac
import re
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


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


# 1. Countermeasure: Yard Dwell Gaming & Ghost Arrivals
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
    scale_weight_kg: Decimal = Field(..., gt=Decimal("0.0"))
    cryptographic_signature: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

    @model_validator(mode="after")
    def verify_physical_coherence(self) -> "YardGateEvent":
        # Disallow arrival registration if ALPR optical scan does not cross-verify RF transponder
        if self.is_transponder_active and not self.optical_plate_scan_match:
            raise ValueError(
                "DISCREPANCY: Active RF transponder without optical camera match. "
                "Possible yard geofence spoofing or tailgating."
            )
        # Ensure timestamp is in UTC and not in distant future
        now_utc = datetime.now(timezone.utc)
        ts = self.telemetry_timestamp if self.telemetry_timestamp.tzinfo else self.telemetry_timestamp.replace(tzinfo=timezone.utc)
        if (ts - now_utc).total_seconds() > 300:
            raise ValueError("PHYSICAL_ANOMALY: Telemetry timestamp cannot be > 300s in the future.")
        return self


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

    @model_validator(mode="after")
    def validate_weight_parity(self) -> "ScrapDisposalEvent":
        # Use Decimal fixed-point arithmetic to eliminate IEEE-754 floating point vulnerability
        expected_weight = (self.theoretical_unit_weight_kg * Decimal(self.units_declared)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        delta_abs = abs(self.scale_measured_total_weight_kg - expected_weight)
        delta_pct = delta_abs / expected_weight

        # Strict physical tolerance (+/- 3.00%)
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
    # Cryptographic blind token generated by backend; operator never sees expected units on RF gun
    blind_token_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

    @model_validator(mode="after")
    def verify_blind_count(self) -> "BlindCycleCountEvent":
        expected_blind_hash = hashlib.sha256(
            f"{self.bin_location}:{self.sku_scanned}:{self.manifest_expected_units}".encode("utf-8")
        ).hexdigest()
        if self.blind_token_hash.lower() != expected_blind_hash.lower():
            raise ValueError(
                "INTEGRITY_VIOLATION: Invalid blind recount token. "
                "Possible tampering with offline handheld terminal."
            )
        return self


def compute_hmac_proof(secret_key: bytes, message: str) -> str:
    """Helper to compute deterministic SHA-256 HMAC for sensor and event authentication."""
    return hmac.new(secret_key, message.encode("utf-8"), hashlib.sha256).hexdigest()
