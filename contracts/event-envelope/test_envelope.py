"""The event envelope: the valid example passes, and every invalid case fails for its stated reason.

Outside the kit's test suite, like the other contracts at the root. From the repository root:

    python -m pytest contracts/event-envelope -q
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("envelope", HERE / "envelope.py")
env = importlib.util.module_from_spec(_spec)
sys.modules["envelope"] = env
_spec.loader.exec_module(env)

VALID = HERE / "examples" / "valid-stream.jsonl"
CASES = json.loads(
    (HERE / "examples" / "invalid-cases.json").read_text(encoding="utf-8")
)
SCHEMA = json.loads((HERE / "envelope.schema.json").read_text(encoding="utf-8"))
FIRST_HASH = "c0642e4b2aeca42074222d2744e8324c9b005419755a14613518e852577f492b"


def _event(**changes):
    base = {
        "producer": "test-producer",
        "stream": "main",
        "event_id": "e-1",
        "event_type": "thing.recorded",
        "kind": "record",
        "actor": {"type": "system", "role": "monitor", "seal": None},
        "objects": [],
        "summary": "Something was recorded.",
        "occurred_at": "2026-11-22T10:00:00Z",
        "recorded_at": "2026-11-22T10:00:00Z",
        "payload": {"units": 3},
        "signature_ref": None,
    }
    return {**base, **changes}


def test_the_valid_example_is_a_whole_chain():
    stream = env.read_jsonl(VALID)
    assert env.verify_stream(stream) == []
    assert [envelope["seq"] for envelope in stream] == [1, 2, 3, 4]
    assert [envelope["kind"] for envelope in stream] == [
        "record",
        "proposal",
        "signature",
        "execution",
    ]


def test_the_first_hash_is_pinned_for_other_implementations():
    # The README publishes this value: an implementation in another language must reach it too.
    assert env.read_jsonl(VALID)[0]["hash"] == FIRST_HASH
    assert FIRST_HASH in (HERE / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", CASES, ids=[case["case"] for case in CASES])
def test_every_invalid_case_fails_for_its_reason(case):
    errors = env.verify_stream(case["stream"])
    assert any(case["error"] in error for error in errors), errors


def test_seal_chains_and_any_edit_breaks_the_chain():
    first = env.seal(_event())
    second = env.seal(_event(event_id="e-2", kind="proposal"), first)
    assert env.verify_stream([first, second]) == []
    assert second["prev_hash"] == first["hash"]
    assert env.verify_stream([{**first, "summary": "Edited."}, second]) != []
    assert env.verify_stream([second]) == [
        "envelope 1: the stream starts at seq 2, not 1"
    ]


def test_an_execution_points_to_its_approval():
    applied = env.seal(_event(kind="execution", signature_ref="approval-1"))
    assert env.validate(applied) == []
    assert env.validate(env.seal(_event(kind="undo"))) == [
        "an undo needs signature_ref: the approval that allowed it"
    ]


def test_without_a_payload_the_producer_keeps_the_hash_of_its_own_record():
    event = {key: value for key, value in _event().items() if key != "payload"}
    assert env.validate(env.seal({**event, "payload_sha256": "a" * 64})) == []


def test_floats_never_enter_a_hash_or_a_stream(tmp_path):
    with pytest.raises(ValueError, match="floating-point"):
        env.canonical({"weight_kg": 12.5})
    path = tmp_path / "stream.jsonl"
    path.write_text('{"weight_kg": 12.5}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1: floating-point"):
        env.read_jsonl(path)


def test_written_streams_are_canonical_and_read_back_the_same(tmp_path):
    stream = env.read_jsonl(VALID)
    copy = tmp_path / "copy.jsonl"
    env.write_jsonl(copy, stream)
    assert env.read_jsonl(copy) == stream
    assert copy.read_text(encoding="utf-8") == VALID.read_text(encoding="utf-8")


def test_the_schema_states_the_same_rules_as_the_code():
    properties = SCHEMA["properties"]
    assert tuple(SCHEMA["required"]) == env.REQUIRED
    assert set(properties) == set(env.REQUIRED) | set(env.OPTIONAL)
    assert properties["contract"]["const"] == env.CONTRACT
    assert tuple(properties["kind"]["enum"]) == env.KINDS
    assert (
        tuple(SCHEMA["allOf"][0]["if"]["properties"]["kind"]["enum"])
        == env.SIGNED_KINDS
    )
    actor = SCHEMA["$defs"]["actor"]
    assert tuple(actor["properties"]["type"]["enum"]) == env.ACTOR_TYPES
    assert tuple(actor["required"]) == env.ACTOR_FIELDS


def test_the_command_line(tmp_path, capsys):
    assert env.main(["verify", str(VALID)]) == 0
    assert (
        "4 envelopes from example-dock/receiving, chain intact"
        in capsys.readouterr().out
    )
    lines = VALID.read_text(encoding="utf-8").splitlines()
    broken = tmp_path / "broken.jsonl"
    broken.write_text(f"{lines[0]}\n{lines[2]}\n", encoding="utf-8")
    assert env.main(["verify", str(broken)]) == 1
    assert "there is a gap" in capsys.readouterr().out
    assert env.main([]) == 2
