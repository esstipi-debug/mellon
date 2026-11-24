"""Event envelope, version 1: one shape for the events that every system publishes.

Reference implementation, standard library only. A producer seals each event into
its stream with `seal`; a reader checks one envelope with `validate` and a whole
stream with `verify_stream`. From the repository root:

    python contracts/event-envelope/envelope.py verify STREAM.jsonl [...]

The contract is README.md in this folder; envelope.schema.json states the same rules
as JSON Schema, and examples/ holds a valid stream and the cases it must reject.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

CONTRACT = "event-envelope/1"
GENESIS = "GENESIS"
KINDS = ("record", "alert", "proposal", "signature", "execution", "undo")
# A signature says that a named person approved or rejected; an execution or an undo says
# that a system of record changed. Each one points to the approval that allowed it.
SIGNED_KINDS = ("signature", "execution", "undo")
ACTOR_TYPES = ("person", "agent", "system")
ACTOR_FIELDS = ("type", "role", "seal")
REQUIRED = (
    "contract",
    "producer",
    "stream",
    "seq",
    "event_id",
    "event_type",
    "kind",
    "actor",
    "objects",
    "summary",
    "occurred_at",
    "recorded_at",
    "payload_sha256",
    "signature_ref",
    "prev_hash",
    "hash",
)
OPTIONAL = ("payload", "attachments")
MAX_SUMMARY = 280
MAX_OBJECTS = 50
MAX_EVENT_ID = 128

_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")


# --- Canonical form and hashes -------------------------------------------------


def canonical(value: Any) -> bytes:
    """Canonical JSON: keys sorted, no whitespace, UTF-8, and no floating-point numbers."""
    _reject_floats(value, "$")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _reject_floats(value: Any, path: str) -> None:
    if isinstance(value, float):
        raise ValueError(
            f"{path}: floating-point number {value!r}; use an integer or a decimal string"
        )
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_floats(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_floats(item, f"{path}[{index}]")


def payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()


def envelope_hash(envelope: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical envelope without its own `hash` field."""
    return hashlib.sha256(
        canonical({key: value for key, value in envelope.items() if key != "hash"})
    ).hexdigest()


# --- Producing -----------------------------------------------------------------


def seal(
    event: Mapping[str, Any], previous: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """The event as the next envelope of its stream: numbered, chained and hashed.

    `event` brings every field except `contract`, `seq`, `prev_hash` and `hash`, and
    except `payload_sha256` when it brings a `payload`. `previous` is the last envelope
    of the same stream, or None for the first one. Nothing is checked here: run
    `validate` on the result.
    """
    envelope = {**event, "contract": CONTRACT}
    if previous is None:
        envelope["seq"], envelope["prev_hash"] = 1, GENESIS
    else:
        envelope["seq"], envelope["prev_hash"] = (
            int(previous["seq"]) + 1,
            previous["hash"],
        )
    if "payload" in envelope:
        envelope["payload_sha256"] = payload_hash(envelope["payload"])
    envelope["hash"] = envelope_hash(envelope)
    return envelope


def write_jsonl(path: str | Path, envelopes: Iterable[Mapping[str, Any]]) -> None:
    """One envelope per line, in canonical form."""
    lines = "".join(
        canonical(envelope).decode("utf-8") + "\n" for envelope in envelopes
    )
    Path(path).write_text(lines, encoding="utf-8", newline="\n")


# --- Reading -------------------------------------------------------------------


def read_jsonl(path: str | Path) -> list[Any]:
    """The envelopes of a JSON Lines file. A line that is not JSON, or that carries a float, stops the read."""
    envelopes = []
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                envelopes.append(json.loads(line, parse_float=_float_in_line))
            except ValueError as exc:
                raise ValueError(f"{path}, line {number}: {exc}") from exc
    return envelopes


def _float_in_line(text: str) -> float:
    raise ValueError(
        f"floating-point number {text}; use an integer or a decimal string"
    )


def validate(envelope: Any) -> list[str]:
    """What is wrong with one envelope; an empty list if nothing is."""
    if not isinstance(envelope, Mapping):
        return ["the envelope is not a JSON object"]
    errors = [f"missing field: {field}" for field in REQUIRED if field not in envelope]
    if errors:
        return errors
    errors = [
        f"unknown field: {field} (extra data goes in payload)"
        for field in sorted(set(envelope) - set(REQUIRED) - set(OPTIONAL))
    ]
    try:
        canonical(envelope)
    except ValueError as exc:
        return [*errors, str(exc)]
    return (
        errors
        + _check_identity(envelope)
        + _check_actor(envelope["actor"])
        + _check_content(envelope)
        + _check_hashes(envelope)
    )


def _check_identity(envelope: Mapping[str, Any]) -> list[str]:
    errors = []
    if envelope["contract"] != CONTRACT:
        errors.append(
            f"contract is {envelope['contract']!r}; this reader knows {CONTRACT!r}"
        )
    for field, pattern in (
        ("producer", _SLUG),
        ("stream", _SLUG),
        ("event_type", _EVENT_TYPE),
    ):
        if not isinstance(envelope[field], str) or not pattern.match(envelope[field]):
            errors.append(
                f"{field} {envelope[field]!r} does not match {pattern.pattern}"
            )
    if not _is_count(envelope["seq"]):
        errors.append(f"seq must be an integer of 1 or more, not {envelope['seq']!r}")
    event_id = envelope["event_id"]
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= MAX_EVENT_ID:
        errors.append(f"event_id must be a string of 1 to {MAX_EVENT_ID} characters")
    if envelope["kind"] not in KINDS:
        errors.append(f"kind {envelope['kind']!r} must be one of: {', '.join(KINDS)}")
    for field in ("occurred_at", "recorded_at"):
        value = envelope[field]
        if not isinstance(value, str) or not _UTC.match(value):
            errors.append(
                f"{field} {value!r} must be UTC in RFC 3339, like 2026-11-22T13:05:00Z"
            )
            continue
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{field} {value!r} is not a valid UTC calendar date/time")
    return errors


def _check_actor(actor: Any) -> list[str]:
    if not isinstance(actor, Mapping):
        return ["actor must be an object with type, role and seal"]
    errors = [
        f"actor carries {field!r}: an actor has only type, role and seal, never a name or an id"
        for field in sorted(set(actor) - set(ACTOR_FIELDS))
    ]
    errors += [
        f"actor is missing {field!r}" for field in ACTOR_FIELDS if field not in actor
    ]
    if errors:
        return errors
    if actor["type"] not in ACTOR_TYPES:
        errors.append(
            f"actor type {actor['type']!r} must be one of: {', '.join(ACTOR_TYPES)}"
        )
    if not isinstance(actor["role"], str) or not _SLUG.match(actor["role"]):
        errors.append(
            f"actor role {actor['role']!r} must be a lowercase function, like shift-lead"
        )
    seal_value = actor["seal"]
    if seal_value is not None and (
        not isinstance(seal_value, str) or not _HEX64.match(seal_value)
    ):
        errors.append(
            "actor seal must be null or an opaque keyed hash: 64 lowercase hex characters"
        )
    return errors


def _check_content(envelope: Mapping[str, Any]) -> list[str]:
    errors = []
    summary = envelope["summary"]
    if not isinstance(summary, str) or not 1 <= len(summary) <= MAX_SUMMARY:
        errors.append(f"summary must be a string of 1 to {MAX_SUMMARY} characters")
    objects = envelope["objects"]
    if (
        not isinstance(objects, list)
        or len(objects) > MAX_OBJECTS
        or not all(_is_ref(o, "id") for o in objects)
    ):
        errors.append(
            f"objects must be a list of up to {MAX_OBJECTS} items, each {{type, id}} as strings"
        )
    if "attachments" in envelope:
        attachments = envelope["attachments"]
        if not isinstance(attachments, list) or not all(
            _is_ref(a, "sha256", _HEX64) for a in attachments
        ):
            errors.append(
                "attachments must be a list of {type, sha256}: media travel by hash, never inline"
            )
    if "payload" in envelope and not isinstance(envelope["payload"], Mapping):
        errors.append("payload must be an object")
    reference = envelope["signature_ref"]
    if reference is not None and (not isinstance(reference, str) or not reference):
        errors.append("signature_ref must be null or a non-empty string")
    if envelope["kind"] in SIGNED_KINDS and reference is None:
        article = "an" if str(envelope["kind"])[:1] in "aeiou" else "a"
        errors.append(
            f"{article} {envelope['kind']} needs signature_ref: the approval that allowed it"
        )
    return errors


def _check_hashes(envelope: Mapping[str, Any]) -> list[str]:
    errors = []
    declared = envelope["payload_sha256"]
    if not isinstance(declared, str) or not _HEX64.match(declared):
        errors.append("payload_sha256 must be 64 lowercase hex characters")
    elif isinstance(envelope.get("payload"), Mapping) and declared != payload_hash(
        envelope["payload"]
    ):
        errors.append("payload_sha256 does not match the payload")
    previous = envelope["prev_hash"]
    if previous != GENESIS and (
        not isinstance(previous, str) or not _HEX64.match(previous)
    ):
        errors.append(f"prev_hash must be {GENESIS} or 64 lowercase hex characters")
    elif _is_count(envelope["seq"]) and (envelope["seq"] == 1) != (previous == GENESIS):
        errors.append(f"prev_hash is {GENESIS} for seq 1, and only for seq 1")
    if envelope["hash"] != envelope_hash(envelope):
        errors.append("hash does not match the envelope: it changed after sealing")
    return errors


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _is_ref(item: Any, second: str, pattern: re.Pattern[str] | None = None) -> bool:
    if not isinstance(item, Mapping) or set(item) != {"type", second}:
        return False
    if not all(isinstance(item[key], str) and item[key] for key in item):
        return False
    return pattern is None or bool(pattern.match(item[second]))


def verify_stream(envelopes: Sequence[Any]) -> list[str]:
    """Every envelope valid, all from one producer and stream, numbered 1, 2, 3... and chained without a gap.

    It fails closed: after an envelope that does not validate, nothing that follows can be trusted.
    """
    errors: list[str] = []
    seen: set[str] = set()
    first = previous = None
    for index, envelope in enumerate(envelopes, start=1):
        problems = validate(envelope)
        if problems:
            return errors + [f"envelope {index}: {problem}" for problem in problems]
        if first is None:
            first = envelope
            if envelope["seq"] != 1:
                return errors + [
                    f"envelope {index}: the stream starts at seq {envelope['seq']}, not 1"
                ]
        else:
            link_errors = _check_link(index, first, previous, envelope)
            if link_errors:
                return errors + link_errors
        if envelope["event_id"] in seen:
            return errors + [
                f"envelope {index}: event_id {envelope['event_id']!r} repeats"
            ]
        seen.add(envelope["event_id"])
        previous = envelope
    return errors


def _check_link(
    index: int,
    first: Mapping[str, Any],
    previous: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> list[str]:
    errors = []
    origin, own = (
        (first["producer"], first["stream"]),
        (envelope["producer"], envelope["stream"]),
    )
    if own != origin:
        errors.append(
            f"envelope {index}: belongs to {'/'.join(own)}, not {'/'.join(origin)}"
        )
    if envelope["seq"] != previous["seq"] + 1:
        errors.append(
            f"envelope {index}: seq {envelope['seq']} after {previous['seq']}: there is a gap or a repeat"
        )
    if envelope["prev_hash"] != previous["hash"]:
        errors.append(
            f"envelope {index}: prev_hash does not match the hash of envelope {index - 1}"
        )
    return errors


# --- Command line --------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[0] != "verify":
        print("usage: envelope.py verify STREAM.jsonl [...]", file=sys.stderr)
        return 2
    status = 0
    for path in args[1:]:
        try:
            envelopes = read_jsonl(path)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            status = 1
            continue
        errors = verify_stream(envelopes)
        for error in errors:
            print(f"ERROR: {path}: {error}")
        if errors:
            status = 1
        elif envelopes:
            last = envelopes[-1]
            print(
                f"OK: {path}: {len(envelopes)} envelopes from {last['producer']}/{last['stream']}, "
                f"chain intact, last hash {last['hash'][:12]}"
            )
        else:
            print(f"OK: {path}: empty stream")
    return status


if __name__ == "__main__":
    sys.exit(main())
