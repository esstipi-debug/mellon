"""Operational trust boundaries, column-semantics probes, and numeric conservation.

Stdlib only (offline-safe). Closes the four operational gaps around Ithildin:
  1. UntrustedPayloadFence + DataTaint + ExecutionMode (Dual-LLM / mode scoping).
  2. ScopedIthildinGuard (blocks writes in forensic modes; enforces SoD on UNTRUSTED_AI).
  3. verify_numeric_conservation (blocks numeric drift/hallucination in rewritten text).
  4. ColumnSemanticsProbe & IterativeSplitProbe (BPI-style repeated snapshots & Kurakin splits).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from .guards import IthildinGuard, RiskLevel, StagingAction, StagingVerdict

FORBIDDEN_CONTROL_KEYS: frozenset[str] = frozenset(
    {
        "risk_level",
        "risk_tier",
        "approved_by",
        "approver_id",
        "auto_approve",
        "auto_apply",
        "skip_review",
        "taint",
        "rollback_plan",
        "signature",
        "signature_ref",
        "bank_account",
        "partner_id",
        "exposure",
        "computed_exposure_minor",
        "charter_hash",
    }
)

_INVISIBLE_CONTROL_CHARS = frozenset(
    {
        "\x00",
        "\ufeff",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)

# Matches numbers including optional sign, thousand-grouped or plain integers/decimals.
_NUM_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![A-Za-z0-9_])"
)
_QUANT4 = Decimal("0.0001")


class DataTaint(str, Enum):
    """Provenance taint of an action or payload entering staging."""

    VERIFIED_STRUCTURED = "VERIFIED_STRUCTURED"
    UNTRUSTED_AI = "UNTRUSTED_AI"


class ExecutionMode(str, Enum):
    """Mode scoping inspired by operational least-privilege boundaries."""

    FORENSIC_READONLY = "FORENSIC_READONLY"
    SCHEMA_PROBE = "SCHEMA_PROBE"
    STAGING_REVIEW = "STAGING_REVIEW"


class BoundaryViolation(Exception):
    """Fail-closed violation raised when an untrusted payload breaches the fence."""

    def __init__(self, code: str, detail: str, *, paths: Sequence[str] = ()) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.paths = tuple(paths)


def _find_forbidden_keys(
    obj: Any, forbidden: frozenset[str], path: str = "$"
) -> list[str]:
    hits: list[str] = []
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            key_norm = str(key).strip().lower()
            cur_path = f"{path}.{key}"
            if key_norm in forbidden:
                hits.append(cur_path)
            hits.extend(_find_forbidden_keys(value, forbidden, cur_path))
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            hits.extend(_find_forbidden_keys(item, forbidden, f"{path}[{idx}]"))
    return hits


def _scan_and_copy(value: Any, path: str = "$") -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise BoundaryViolation(
                "NON_FINITE_NUMBER",
                f"Non-finite float {value!r} rejected at {path}",
                paths=(path,),
            )
        return value
    if isinstance(value, str):
        bad = [ch for ch in value if ch in _INVISIBLE_CONTROL_CHARS]
        if bad:
            raise BoundaryViolation(
                "INVISIBLE_CONTROL_CHAR",
                f"Invisible bidi/control character rejected at {path}",
                paths=(path,),
            )
        return value
    if isinstance(value, Mapping):
        return {
            str(k): _scan_and_copy(v, f"{path}.{k}") for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scan_and_copy(item, f"{path}[{idx}]") for idx, item in enumerate(value)]
    if isinstance(value, tuple):
        return [_scan_and_copy(item, f"{path}[{idx}]") for idx, item in enumerate(value)]
    return value


class UntrustedPayloadFence:
    """Strict structural fence isolating untrusted payloads from control channels."""

    def __init__(self, forbidden_keys: frozenset[str] = FORBIDDEN_CONTROL_KEYS) -> None:
        self.forbidden_keys = forbidden_keys

    def validate_payload(
        self,
        payload: Mapping[str, Any],
        *,
        required_keys: Sequence[str] = (),
        forbidden_keys: frozenset[str] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise BoundaryViolation(
                "INVALID_PAYLOAD_TYPE", "Payload must be a mapping.", paths=("$",)
            )
        active_forbidden = (
            forbidden_keys if forbidden_keys is not None else self.forbidden_keys
        )
        smuggled = _find_forbidden_keys(payload, active_forbidden)
        if smuggled:
            raise BoundaryViolation(
                "PROMPT_INJECTION_CONTROL_FIELD",
                f"Forbidden control key(s) smuggled in payload: {', '.join(smuggled)}",
                paths=smuggled,
            )
        cleaned = _scan_and_copy(payload)
        missing = [
            key
            for key in required_keys
            if key not in cleaned
            or cleaned[key] is None
            or (isinstance(cleaned[key], str) and not cleaned[key].strip())
        ]
        if missing:
            raise BoundaryViolation(
                "MISSING_REQUIRED_FIELD",
                f"Missing required payload field(s): {', '.join(missing)}",
                paths=tuple(f"$.{k}" for k in missing),
            )
        return cleaned


class ScopedIthildinGuard:
    """Mode-aware, SoD-enforcing wrapper around IthildinGuard."""

    def __init__(
        self,
        guard: IthildinGuard,
        *,
        mode: ExecutionMode = ExecutionMode.STAGING_REVIEW,
        fence: UntrustedPayloadFence | None = None,
    ) -> None:
        self._guard = guard
        self.mode = mode
        self.fence = fence if fence is not None else UntrustedPayloadFence()

    def evaluate_scoped(
        self,
        action: StagingAction,
        token: str,
        *,
        taint: DataTaint = DataTaint.UNTRUSTED_AI,
        initiator_id: str = "",
        human_verifier: str = "",
        evaluated_at_utc: str | None = None,
    ) -> StagingVerdict:
        now_utc = (
            evaluated_at_utc
            if evaluated_at_utc is not None
            else datetime.now(timezone.utc).isoformat()
        )
        audit_hash = hashlib.sha256(action.canonical_bytes()).hexdigest()

        if self.mode in (
            ExecutionMode.FORENSIC_READONLY,
            ExecutionMode.SCHEMA_PROBE,
        ) and action.risk_level != RiskLevel.READ:
            return StagingVerdict(
                approved=False,
                code="REJECTED_MODE_FORBIDS_MUTATION",
                reason=(
                    f"Mode {self.mode.value} only permits READ actions; "
                    f"refused {action.risk_level.value}."
                ),
                audit_hash=audit_hash,
                evaluated_at_utc=now_utc,
            )

        try:
            self.fence.validate_payload(action.payload)
        except BoundaryViolation as exc:
            return StagingVerdict(
                approved=False,
                code=exc.code,
                reason=exc.detail,
                audit_hash=audit_hash,
                evaluated_at_utc=now_utc,
            )

        if taint == DataTaint.UNTRUSTED_AI and action.risk_level != RiskLevel.READ:
            init_clean = initiator_id.strip()
            ver_clean = human_verifier.strip()
            if not init_clean or not ver_clean or init_clean == ver_clean:
                return StagingVerdict(
                    approved=False,
                    code="REJECTED_UNTRUSTED_AI_SOD",
                    reason=(
                        "UNTRUSTED_AI mutations require non-empty initiator_id and "
                        "a distinct human_verifier (fail-closed SoD)."
                    ),
                    audit_hash=audit_hash,
                    evaluated_at_utc=now_utc,
                )
            if action.approved_by is not None and action.approved_by.strip() != ver_clean:
                return StagingVerdict(
                    approved=False,
                    code="REJECTED_UNTRUSTED_AI_SOD",
                    reason=(
                        "Action approved_by does not match human_verifier "
                        "(fail-closed SoD)."
                    ),
                    audit_hash=audit_hash,
                    evaluated_at_utc=now_utc,
                )

        return self._guard.evaluate_and_commit(action, token, now_utc=now_utc)


@dataclass(frozen=True)
class NumericDriftReport:
    """Result of deterministic numeric conservation verification."""

    ok: bool
    expected_numbers: tuple[str, ...]
    missing_numbers: tuple[str, ...]
    invented_numbers: tuple[str, ...]
    detail: str


def _canonical_number_token(raw: str) -> str:
    cleaned = raw.replace(",", "")
    d = Decimal(cleaned)
    if d == 0:
        return "0"
    normalized = d.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _extract_numbers(text: str) -> list[str]:
    out: list[str] = []
    for match in _NUM_TOKEN_RE.finditer(text):
        token = match.group(0)
        try:
            out.append(_canonical_number_token(token))
        except InvalidOperation:
            continue
    return out


def verify_numeric_conservation(
    source_summary: str, rewritten_text: str
) -> NumericDriftReport:
    """Verify rewritten text preserves every source number and invents none."""
    expected = _extract_numbers(source_summary)
    found = _extract_numbers(rewritten_text)

    expected_counts: dict[str, int] = defaultdict(int)
    for num in expected:
        expected_counts[num] += 1

    found_counts: dict[str, int] = defaultdict(int)
    for num in found:
        found_counts[num] += 1

    missing: list[str] = []
    for num, count in expected_counts.items():
        diff = count - found_counts.get(num, 0)
        if diff > 0:
            missing.extend([num] * diff)

    invented: list[str] = []
    for num, count in found_counts.items():
        diff = count - expected_counts.get(num, 0)
        if diff > 0:
            invented.extend([num] * diff)

    ok = not missing and not invented
    if ok:
        detail = f"Numeric conservation verified ({len(expected)} number(s) preserved)."
    else:
        detail = (
            f"Numeric drift detected: missing={missing or '[]'}, "
            f"invented={invented or '[]'}."
        )
    return NumericDriftReport(
        ok=ok,
        expected_numbers=tuple(expected),
        missing_numbers=tuple(missing),
        invented_numbers=tuple(invented),
        detail=detail,
    )


def _parse_finite_decimal(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        return raw if raw.is_finite() else None
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        if not math.isfinite(raw):
            return None
        return Decimal(str(raw))
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            d = Decimal(text)
        except InvalidOperation:
            return None
        return d if d.is_finite() else None
    return None


class SemanticsClass(str, Enum):
    """Classification of multi-event numeric column behavior."""

    REPEATED_SNAPSHOT = "REPEATED_SNAPSHOT"
    MONOTONIC_CUMULATIVE = "MONOTONIC_CUMULATIVE"
    INCREMENTAL_ADDITIVE = "INCREMENTAL_ADDITIVE"
    AMBIGUOUS_DO_NOT_SUM = "AMBIGUOUS_DO_NOT_SUM"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True)
class SemanticsReport:
    """Float-free report classifying whether a column is safe to sum per case."""

    status: SemanticsClass
    column: str
    multi_event_cases: int
    unreadable_rows: int
    all_equal_ratio: Decimal
    sum_matches_ref_ratio: Decimal | None
    last_matches_ref_ratio: Decimal | None
    monotonic_ratio: Decimal
    safe_to_sum: bool
    summary: str


class ColumnSemanticsProbe:
    """Detects BPI-style repeated/cumulative numeric columns before aggregation."""

    def inspect(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        case_col: str,
        value_col: str,
        ref_value_col: str | None = None,
        min_multi_cases: int = 1,
    ) -> SemanticsReport:
        grouped: dict[str, list[Decimal]] = defaultdict(list)
        refs: dict[str, Decimal] = {}
        unreadable = 0

        for row in rows:
            case_raw = row.get(case_col)
            case_id = "" if case_raw is None else str(case_raw).strip()
            val = _parse_finite_decimal(row.get(value_col))
            if not case_id or val is None:
                unreadable += 1
                continue
            if ref_value_col is not None:
                ref_val = _parse_finite_decimal(row.get(ref_value_col))
                if ref_val is None:
                    unreadable += 1
                    continue
                refs[case_id] = ref_val
            grouped[case_id].append(val)

        multi = {cid: vals for cid, vals in grouped.items() if len(vals) >= 2}
        n_multi = len(multi)
        zero = Decimal("0.0000")
        if n_multi < min_multi_cases:
            return SemanticsReport(
                status=SemanticsClass.NOT_EVALUABLE,
                column=value_col,
                multi_event_cases=n_multi,
                unreadable_rows=unreadable,
                all_equal_ratio=zero,
                sum_matches_ref_ratio=None,
                last_matches_ref_ratio=None,
                monotonic_ratio=zero,
                safe_to_sum=False,
                summary=(
                    f"NOT_EVALUABLE: {n_multi} multi-event case(s) (< {min_multi_cases}), "
                    f"unreadable_rows={unreadable}."
                ),
            )

        tol = Decimal("0.0001")
        all_eq = 0
        monotonic = 0
        sum_match = 0
        last_match = 0
        denom = Decimal(n_multi)

        for cid, vals in multi.items():
            if all(v == vals[0] for v in vals):
                all_eq += 1
            if all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)) and any(
                vals[i] < vals[i + 1] for i in range(len(vals) - 1)
            ):
                monotonic += 1
            if ref_value_col is not None:
                ref = refs[cid]
                if abs(sum(vals, Decimal("0")) - ref) <= tol:
                    sum_match += 1
                if abs(vals[-1] - ref) <= tol:
                    last_match += 1

        all_eq_r = (Decimal(all_eq) / denom).quantize(_QUANT4)
        mono_r = (Decimal(monotonic) / denom).quantize(_QUANT4)
        sum_r = (
            (Decimal(sum_match) / denom).quantize(_QUANT4)
            if ref_value_col is not None
            else None
        )
        last_r = (
            (Decimal(last_match) / denom).quantize(_QUANT4)
            if ref_value_col is not None
            else None
        )

        if all_eq_r >= Decimal("0.70") or (
            last_r is not None
            and sum_r is not None
            and last_r >= Decimal("0.70")
            and sum_r <= Decimal("0.10")
            and mono_r < Decimal("0.80")
        ):
            status = SemanticsClass.REPEATED_SNAPSHOT
            safe = False
        elif sum_r is not None and sum_r >= Decimal("0.90") and unreadable == 0:
            status = SemanticsClass.INCREMENTAL_ADDITIVE
            safe = True
        elif mono_r >= Decimal("0.80") and (
            last_r is None or last_r >= Decimal("0.70")
        ):
            status = SemanticsClass.MONOTONIC_CUMULATIVE
            safe = False
        elif (
            ref_value_col is None
            and all_eq_r < Decimal("0.10")
            and mono_r < Decimal("0.20")
            and unreadable == 0
        ):
            status = SemanticsClass.INCREMENTAL_ADDITIVE
            safe = True
        else:
            status = SemanticsClass.AMBIGUOUS_DO_NOT_SUM
            safe = False

        return SemanticsReport(
            status=status,
            column=value_col,
            multi_event_cases=n_multi,
            unreadable_rows=unreadable,
            all_equal_ratio=all_eq_r,
            sum_matches_ref_ratio=sum_r,
            last_matches_ref_ratio=last_r,
            monotonic_ratio=mono_r,
            safe_to_sum=safe,
            summary=(
                f"{status.value} on '{value_col}': multi_cases={n_multi}, "
                f"all_equal={all_eq_r}, monotonic={mono_r}, "
                f"unreadable={unreadable}, safe_to_sum={safe}."
            ),
        )


@dataclass(frozen=True)
class SplitAlert:
    """Detected multi-step iterative split circumventing a per-transaction threshold."""

    entity_id: str
    window_start: str
    window_end: str
    step_count: int
    rolling_sum: Decimal
    threshold: Decimal
    max_single_step: Decimal


class IterativeSplitProbe:
    """Rolling-window detector catching multi-step sub-threshold splitting."""

    def detect(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        entity_col: str,
        amount_col: str,
        date_col: str,
        threshold: Decimal | str,
        window_days: int = 7,
        min_steps: int = 2,
        max_ceiling_multiplier: Decimal | str = Decimal("3"),
    ) -> tuple[list[SplitAlert], int]:
        thresh = _parse_finite_decimal(threshold)
        mult = _parse_finite_decimal(max_ceiling_multiplier)
        if thresh is None or thresh <= 0:
            raise ValueError("threshold must be a finite positive Decimal")
        if mult is None or mult < 1:
            raise ValueError("max_ceiling_multiplier must be >= 1")
        ceiling = thresh * mult

        by_entity: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
        unreadable = 0

        for row in rows:
            ent_raw = row.get(entity_col)
            ent = "" if ent_raw is None else str(ent_raw).strip()
            amt = _parse_finite_decimal(row.get(amount_col))
            day_raw = row.get(date_col)
            day_obj: date | None = None
            if isinstance(day_raw, datetime):
                day_obj = day_raw.date()
            elif isinstance(day_raw, date):
                day_obj = day_raw
            elif isinstance(day_raw, str) and len(day_raw.strip()) >= 10:
                try:
                    day_obj = date.fromisoformat(day_raw.strip()[:10])
                except ValueError:
                    day_obj = None
            if not ent or amt is None or amt <= 0 or day_obj is None:
                unreadable += 1
                continue
            if amt <= thresh:
                by_entity[ent].append((day_obj, amt))

        alerts: list[SplitAlert] = []
        for ent, entries in sorted(by_entity.items()):
            entries.sort(key=lambda item: item[0])
            # Partition into contiguous chains where consecutive steps are <= window_days apart
            # so high-volume recurring orders exceeding `ceiling` are not misread mid-prefix.
            chains: list[list[tuple[date, Decimal]]] = []
            for entry in entries:
                if not chains or (entry[0] - chains[-1][-1][0]).days > window_days:
                    chains.append([entry])
                else:
                    chains[-1].append(entry)
            for chain in chains:
                if len(chain) < min_steps:
                    continue
                total = sum((amt for _, amt in chain), Decimal("0"))
                if thresh < total <= ceiling:
                    alerts.append(
                        SplitAlert(
                            entity_id=ent,
                            window_start=chain[0][0].isoformat(),
                            window_end=chain[-1][0].isoformat(),
                            step_count=len(chain),
                            rolling_sum=total,
                            threshold=thresh,
                            max_single_step=max(amt for _, amt in chain),
                        )
                    )
        return alerts, unreadable
