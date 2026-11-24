"""Native event-envelope/1 producer for fdekit.ithildin and fdekit.decide.

Standard library only (offline-safe). Produces float-free, canonical JSONL
streams chained with SHA-256 hashes that validate directly against
`contracts/event-envelope/envelope.py` and `envelope.schema.json`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .guards import StagingAction, StagingVerdict

CONTRACT = "event-envelope/1"
GENESIS = "GENESIS"
PRODUCER = "mellon"

_SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _slug(value: str, fallback: str = "default") -> str:
    cleaned = _SLUG_CLEAN.sub("-", value.lower()).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)[:40].strip("-")
    if len(cleaned) < 2 or not cleaned[0].isalpha():
        cleaned = f"s-{cleaned}" if cleaned else fallback
    return cleaned[:40].rstrip("-")


def _normalize_utc_z(moment: str | datetime | date) -> str:
    if isinstance(moment, datetime):
        if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
            raise ValueError("naive datetime rejected: UTC offset required")
        dt = moment.astimezone(timezone.utc)
    elif isinstance(moment, date):
        return f"{moment.isoformat()}T00:00:00Z"
    elif isinstance(moment, str):
        raw = moment.strip()
        if not raw:
            raise ValueError("timestamp string cannot be empty")
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError(f"naive timestamp {moment!r} rejected: timezone required")
        dt = dt.astimezone(timezone.utc)
    else:
        raise TypeError(f"unsupported timestamp type: {type(moment).__name__}")
    frac = f".{dt.microsecond:06d}" if dt.microsecond else ""
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}{frac}Z"


def _sanitize_no_floats(value: Any, path: str = "$") -> Any:
    if isinstance(value, float):
        raise ValueError(
            f"{path}: floating-point number {value!r} rejected; use int or Decimal/str"
        )
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{path}: non-finite Decimal {value!r} rejected")
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(k): _sanitize_no_floats(v, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_no_floats(item, f"{path}[{idx}]") for idx, item in enumerate(value)]
    return value


def _canonical_bytes(value: Any) -> bytes:
    clean = _sanitize_no_floats(value, "$")
    return json.dumps(
        clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _envelope_hash(envelope: Mapping[str, Any]) -> str:
    without_hash = {k: v for k, v in envelope.items() if k != "hash"}
    return hashlib.sha256(_canonical_bytes(without_hash)).hexdigest()


def seal_credential(credential: str | None, key: bytes | None) -> str | None:
    """Opaque HMAC-SHA256 seal of a person's credential, or None when absent."""
    if key is not None and (not isinstance(key, (bytes, bytearray)) or len(key) < 16):
        raise ValueError("seal_key must have at least 16 bytes of entropy")
    if not credential or not key:
        return None
    return hmac.new(bytes(key), credential.encode("utf-8"), hashlib.sha256).hexdigest()


def verdict_to_event(
    action: StagingAction,
    verdict: StagingVerdict,
    *,
    stream: str = "ithildin-guard",
    actor_role: str = "staging-guard",
    actor_type: str = "system",
    actor_credential: str | None = None,
    seal_key: bytes | None = None,
    signature_ref: str | None = None,
) -> dict[str, Any]:
    """Convert an IthildinGuard staging verdict into an unchained event-envelope/1 dict."""
    if not verdict.approved:
        kind = "alert"
        event_type = "ithildin.action.rejected"
        sig_ref = signature_ref
    elif signature_ref:
        kind = "execution"
        event_type = "ithildin.action.executed"
        sig_ref = signature_ref
    else:
        kind = "proposal"
        event_type = "ithildin.action.staged"
        sig_ref = None

    clean_payload = _sanitize_no_floats(dict(action.payload), "$.payload")
    payload = {
        "action_id": action.action_id,
        "approved": verdict.approved,
        "audit_hash": verdict.audit_hash,
        "idempotency_key": action.idempotency_key,
        "payload": clean_payload,
        "risk_level": action.risk_level.value,
        "target_system": action.target_system,
        "verdict_code": verdict.code,
    }
    summary = (
        f"Ithildin {verdict.code} for {action.action_id} on {action.target_system} "
        f"({action.risk_level.value})"
    )[:280]
    return {
        "producer": PRODUCER,
        "stream": _slug(stream, "ithildin-guard"),
        "event_id": f"{action.action_id}:{verdict.audit_hash[:12]}",
        "event_type": event_type,
        "kind": kind,
        "actor": {
            "type": actor_type,
            "role": _slug(actor_role, "staging-guard"),
            "seal": seal_credential(actor_credential, seal_key),
        },
        "objects": [
            {"type": "target-system", "id": action.target_system},
            {"type": "action", "id": action.action_id},
        ],
        "summary": summary,
        "occurred_at": _normalize_utc_z(action.timestamp_utc),
        "recorded_at": _normalize_utc_z(verdict.evaluated_at_utc),
        "payload": payload,
        "payload_sha256": _payload_hash(payload),
        "signature_ref": sig_ref,
    }


def decision_to_event(
    decision: Any,
    *,
    stream: str = "decide-ledger",
    actor_credential: str | None = None,
    seal_key: bytes | None = None,
    recorded_at: str | datetime | date | None = None,
) -> dict[str, Any]:
    """Convert a DecideStore Decision into an unchained event-envelope/1 record (no PII)."""
    occurred = _normalize_utc_z(decision.date_decided)
    recorded = _normalize_utc_z(recorded_at) if recorded_at is not None else occurred
    statement_preview = " ".join(str(decision.statement).split())
    summary = f"Decision {decision.id} ({decision.status}): {statement_preview}"[:280]
    payload = _sanitize_no_floats(
        {
            "criteria": str(decision.criteria),
            "decision_id": str(decision.id),
            "meeting_id": str(getattr(decision, "meeting_id", "")),
            "origen": str(getattr(decision, "origen", "REUNION")),
            "scope": str(getattr(decision, "scope", "")),
            "status": str(decision.status),
            "version": int(getattr(decision, "version", 1)),
        },
        "$.payload",
    )
    objects = [{"type": "decision", "id": str(decision.id)}]
    meeting_id = getattr(decision, "meeting_id", "")
    if meeting_id:
        objects.append({"type": "meeting", "id": str(meeting_id)})
    return {
        "producer": PRODUCER,
        "stream": _slug(stream, "decide-ledger"),
        "event_id": f"{decision.id}:v{getattr(decision, 'version', 1)}",
        "event_type": "decide.decision.recorded",
        "kind": "record",
        "actor": {
            "type": "person",
            "role": "decision-owner",
            "seal": seal_credential(actor_credential, seal_key),
        },
        "objects": objects,
        "summary": summary,
        "occurred_at": occurred,
        "recorded_at": recorded,
        "payload": payload,
        "payload_sha256": _payload_hash(payload),
        "signature_ref": None,
    }


def seal_stream(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Number, chain, and SHA-256 seal a sequence of unchained events."""
    sealed: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for event in events:
        envelope = {**event, "contract": CONTRACT}
        if previous is None:
            envelope["seq"] = 1
            envelope["prev_hash"] = GENESIS
        else:
            envelope["seq"] = int(previous["seq"]) + 1
            envelope["prev_hash"] = previous["hash"]
        if "payload" in envelope:
            envelope["payload_sha256"] = _payload_hash(envelope["payload"])
        envelope["hash"] = _envelope_hash(envelope)
        sealed.append(envelope)
        previous = envelope
    return sealed


def write_jsonl(path: str | Path, envelopes: Sequence[Mapping[str, Any]]) -> None:
    """Write sealed envelopes as canonical UTF-8 JSON Lines."""
    lines = "".join(
        _canonical_bytes(envelope).decode("utf-8") + "\n" for envelope in envelopes
    )
    Path(path).write_text(lines, encoding="utf-8", newline="\n")
