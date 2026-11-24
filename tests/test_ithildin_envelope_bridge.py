"""Interoperability tests for fdekit.ithildin.envelope_bridge against event-envelope/1."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fdekit.decide import Decision
from fdekit.ithildin import (
    IthildinGuard,
    RiskLevel,
    StagingAction,
    decision_to_event,
    seal_credential,
    seal_stream,
    verdict_to_event,
    write_jsonl,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ENVELOPE_MOD_PATH = REPO_ROOT / "contracts" / "event-envelope" / "envelope.py"


def _load_reference_contract():
    spec = importlib.util.spec_from_file_location("mellon_envelope_ref", ENVELOPE_MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mellon_envelope_ref"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ithildin_verdicts_emit_valid_event_envelope_stream(tmp_path):
    ref = _load_reference_contract()
    guard = IthildinGuard(b"ithildin-bridge-secret-0123456789")
    seal_key = b"actor-credential-seal-key-012345"

    staged_action = StagingAction(
        action_id="act-stage-01",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="erp-odoo",
        payload={"sku": "SKU-10", "qty_minor": 250, "unit_price_dec": Decimal("14.50")},
        idempotency_key="idemp-stage-01",
        timestamp_utc="2026-11-24T09:00:00-03:00",
    )
    v_staged = guard.evaluate_and_commit(staged_action, guard.sign_action(staged_action))

    rejected_action = StagingAction(
        action_id="act-bad-02",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="erp-sap",
        payload={"sku": "SKU-20", "qty_minor": 10},
        idempotency_key="idemp-bad-02",
        timestamp_utc="2026-11-24T12:05:00Z",
        rollback_plan=None,
    )
    v_rejected = guard.evaluate_and_commit(rejected_action, guard.sign_action(rejected_action))

    exec_action = StagingAction(
        action_id="act-exec-03",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="erp-odoo",
        payload={"sku": "SKU-30", "qty_minor": 40},
        idempotency_key="idemp-exec-03",
        timestamp_utc="2026-11-24T12:10:00Z",
        rollback_plan={"restore_snapshot": "snap-1"},
    )
    v_exec = guard.evaluate_and_commit(exec_action, guard.sign_action(exec_action))

    events = [
        verdict_to_event(staged_action, v_staged, actor_credential="planner-01", seal_key=seal_key),
        verdict_to_event(rejected_action, v_rejected),
        verdict_to_event(
            exec_action,
            v_exec,
            actor_type="person",
            actor_role="shift-lead",
            actor_credential="badge-771",
            seal_key=seal_key,
            signature_ref="sig-ledger-009",
        ),
    ]
    assert [ev["kind"] for ev in events] == ["proposal", "alert", "execution"]
    assert events[0]["occurred_at"] == "2026-11-24T12:00:00Z"
    assert events[0]["payload"]["payload"]["unit_price_dec"] == "14.50"

    stream = seal_stream(events)
    assert ref.verify_stream(stream) == []

    out_path = tmp_path / "ithildin.jsonl"
    write_jsonl(out_path, stream)
    assert ref.read_jsonl(out_path) == stream
    assert ref.main(["verify", str(out_path)]) == 0


def test_decision_to_event_omits_pii_and_passes_reference_contract(tmp_path):
    ref = _load_reference_contract()
    seal_key = b"decide-seal-secret-key-012345678"
    decision = Decision(
        id="D-001",
        statement="Limitar recepcion sin conteo ciego en muelle norte.",
        owner="Marcela Perez",
        date_decided=date(2026, 11, 20),
        criteria="unverified_release == 0",
        rationale="Evitar stock fantasma antes de ERP.",
        meeting_id="2026-11-20-ops",
        scope="bodega-norte",
    )
    ev = decision_to_event(
        decision,
        actor_credential=decision.owner,
        seal_key=seal_key,
        recorded_at="2026-11-20T15:30:00Z",
    )
    stream = seal_stream([ev])
    assert ref.verify_stream(stream) == []
    assert "Marcela Perez" not in repr(stream)
    assert ev["actor"] == {
        "type": "person",
        "role": "decision-owner",
        "seal": seal_credential("Marcela Perez", seal_key),
    }

    out_path = tmp_path / "decide.jsonl"
    write_jsonl(out_path, stream)
    assert ref.main(["verify", str(out_path)]) == 0


def test_envelope_bridge_rejects_floats_and_short_seal_key():
    guard = IthildinGuard(b"ithildin-bridge-secret-0123456789")
    action = StagingAction(
        action_id="act-float-01",
        risk_level=RiskLevel.READ,
        target_system="erp",
        payload={"weight_kg": 12.5},
        idempotency_key="idemp-float-01",
        timestamp_utc="2026-11-24T12:00:00Z",
    )
    verdict = guard.evaluate_and_commit(action, guard.sign_action(action))
    with pytest.raises(ValueError, match="floating-point"):
        verdict_to_event(action, verdict)

    with pytest.raises(ValueError, match="16 bytes"):
        seal_credential("badge-1", b"too-short")
