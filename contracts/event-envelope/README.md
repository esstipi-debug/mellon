# Event envelope, version 1

One shape for the events that every system publishes, so that a reader can cross what several systems did without sharing their databases. Each system keeps its own records; what travels is the envelope.

Status: version 1, 2026-11-22.

| File | What it is |
|---|---|
| `README.md` | This contract |
| `envelope.schema.json` | The same rules as JSON Schema (draft 2020-12) |
| `envelope.py` | Reference implementation, standard library only: seal, validate, verify a stream |
| `examples/valid-stream.jsonl` | A valid stream of four envelopes |
| `examples/invalid-cases.json` | Fourteen streams a reader must reject, each with the reason |
| `test_envelope.py` | The checks of everything above |

## A stream is a chain

- A producer publishes one or more streams. Each stream is one hash chain: envelopes numbered 1, 2, 3… without gaps, each one carrying the hash of the one before. The first carries `"prev_hash": "GENESIS"`.
- Nothing in a stream is edited or deleted. A correction is a new envelope.
- Transport is a JSON Lines file (one envelope per line, in canonical form) or any channel that keeps the order. If the link drops, envelopes wait; they are not lost or reordered.
- A reader verifies the whole chain and fails closed: after an envelope that does not validate, nothing that follows is trusted.

## Fields

| Field | Type | Rule |
|---|---|---|
| `contract` | string | Exactly `event-envelope/1` |
| `producer` | string | The system that publishes: lowercase, digits and `-`, 2 to 40 characters |
| `stream` | string | The chain inside that producer, same form |
| `seq` | integer | 1 or more, consecutive within the stream |
| `event_id` | string | The producer's own id, 1 to 128 characters, unique in the stream |
| `event_type` | string | The producer's own vocabulary: lowercase, digits, `_`, `.` and `-` |
| `kind` | string | One of the six kinds below |
| `actor` | object | `type`, `role` and `seal` only (see People) |
| `objects` | array | Up to 50 `{type, id}`: what the event is about (a delivery, a SKU, a bin) |
| `summary` | string | 1 to 280 characters a person can read, without personal data |
| `occurred_at` | string | When it happened, UTC in RFC 3339 with `Z`: `2026-11-22T13:05:00Z` |
| `recorded_at` | string | When the producer recorded it, same form |
| `payload` | object, optional | The producer's own data, with no floating-point numbers |
| `payload_sha256` | string | SHA-256 of the canonical `payload`; without a payload, the hash of the producer's own record |
| `attachments` | array, optional | `{type, sha256}`: media travel by hash, never inline |
| `signature_ref` | string or null | The approval this event relies on, in the signer's own ledger. Required for `signature`, `execution` and `undo` |
| `prev_hash` | string | `GENESIS` for seq 1, and only for seq 1; otherwise the `hash` of the previous envelope |
| `hash` | string | SHA-256 of the canonical envelope without `hash` |

Any other top-level field is rejected: extra data goes in `payload`.

## Kinds

| `kind` | What it says |
|---|---|
| `record` | A fact was observed or measured |
| `alert` | Something needs attention |
| `proposal` | An agent or a model suggests a change. A proposal never changes anything by itself |
| `signature` | A named person approved or rejected |
| `execution` | A change was applied to a system of record |
| `undo` | A change was rolled back |

A change to a system of record shows up only as an `execution` or an `undo`, and its `signature_ref` points to the approval that allowed it.

## People

- `actor` has only `type` (`person`, `agent` or `system`), `role` (a function such as `shift-lead`, never a name) and `seal`. It never carries a name, an email, a badge number or any other direct identifier.
- `seal` is an opaque keyed hash of the credential, for example HMAC-SHA256 with a key the producer keeps. It ties a closure to whoever did it without exposing who that is. It is null when there is no person.
- Readers aggregate by role, shift, asset or cohort. They do not rank, score or discipline individuals by `seal`.
- Audio, photos and documents never travel inline: `attachments` carries only their SHA-256.

## Canonical form and hashes

- Canonical JSON: keys sorted by code point, no whitespace (`,` and `:` as separators), UTF-8, strings escaped as JSON, and no floating-point numbers anywhere. Use integers (minor units, grams, cents) or decimal strings. Field names are ASCII, so code-point order equals UTF-16 order and other languages reach the same bytes.
- Hashes are SHA-256 in lowercase hex.
- Check value: the first line of `examples/valid-stream.jsonl` hashes to `c0642e4b2aeca42074222d2744e8324c9b005419755a14613518e852577f492b`. An implementation in another language must reach the same value.

JSON Schema cannot state three of these rules, and only `envelope.py` checks them: no floating-point numbers, hashes recomputed from the canonical form, and the chain across envelopes.

## Versions

A reader rejects a `contract` it does not know. Any new field or any change to a rule is a new version: `event-envelope/1` does not change.

## Checking

From the repository root:

```bash
python contracts/event-envelope/envelope.py verify STREAM.jsonl
```

```bash
python -m pytest contracts/event-envelope -q
```
