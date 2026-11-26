"""Tests for fdekit.ithildin.boundary and boundary_rejection_to_event."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from fdekit.ithildin import (
    BoundaryViolation,
    ColumnSemanticsProbe,
    DataTaint,
    ExecutionMode,
    IterativeSplitProbe,
    IthildinGuard,
    RiskLevel,
    ScopedIthildinGuard,
    SemanticsClass,
    StagingAction,
    UntrustedPayloadFence,
    boundary_rejection_to_event,
    seal_stream,
    verify_numeric_conservation,
    write_jsonl,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ENVELOPE_MOD_PATH = REPO_ROOT / "contracts" / "event-envelope" / "envelope.py"


def _load_reference_contract():
    spec = importlib.util.spec_from_file_location("mellon_envelope_ref_b", ENVELOPE_MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mellon_envelope_ref_b"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_fence_rejects_nested_control_fields_nan_missing_and_bidi():
    fence = UntrustedPayloadFence()

    with pytest.raises(BoundaryViolation) as exc_ctrl:
        fence.validate_payload({"po": "PO-1", "nested": [{"auto_approve": True}]})
    assert exc_ctrl.value.code == "PROMPT_INJECTION_CONTROL_FIELD"
    assert "$.nested[0].auto_approve" in exc_ctrl.value.paths

    with pytest.raises(BoundaryViolation) as exc_nan:
        fence.validate_payload({"qty": float("nan")})
    assert exc_nan.value.code == "NON_FINITE_NUMBER"

    with pytest.raises(BoundaryViolation) as exc_bidi:
        fence.validate_payload({"note": "clean\u202ehidden"})
    assert exc_bidi.value.code == "INVISIBLE_CONTROL_CHAR"

    with pytest.raises(BoundaryViolation) as exc_req:
        fence.validate_payload({"sku": "A"}, required_keys=("sku", "uom_code"))
    assert exc_req.value.code == "MISSING_REQUIRED_FIELD"

    clean = fence.validate_payload(
        {"sku": "SKU-1", "uom_code": "EA", "qty": Decimal("10")},
        required_keys=("sku", "uom_code"),
    )
    assert clean == {"sku": "SKU-1", "uom_code": "EA", "qty": Decimal("10")}


def test_scoped_guard_enforces_mode_and_untrusted_ai_sod():
    guard = IthildinGuard(b"ithildin-scoped-secret-key-2026!!")
    ro = ScopedIthildinGuard(guard, mode=ExecutionMode.FORENSIC_READONLY)

    write_action = StagingAction(
        action_id="act-ro-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="erp-odoo",
        payload={"sku": "SKU-1", "qty": 5},
        idempotency_key="k-ro-1",
        timestamp_utc="2026-11-26T12:00:00Z",
    )
    v_ro = ro.evaluate_scoped(
        write_action,
        guard.sign_action(write_action),
        taint=DataTaint.VERIFIED_STRUCTURED,
    )
    assert v_ro.approved is False
    assert v_ro.code == "REJECTED_MODE_FORBIDS_MUTATION"

    review = ScopedIthildinGuard(guard, mode=ExecutionMode.STAGING_REVIEW)
    # Missing human_verifier or matching initiator fails SoD
    v_sod_missing = review.evaluate_scoped(
        write_action,
        guard.sign_action(write_action),
        taint=DataTaint.UNTRUSTED_AI,
        initiator_id="agent-1",
        human_verifier="",
    )
    assert v_sod_missing.approved is False
    assert v_sod_missing.code == "REJECTED_UNTRUSTED_AI_SOD"

    v_sod_same = review.evaluate_scoped(
        write_action,
        guard.sign_action(write_action),
        taint=DataTaint.UNTRUSTED_AI,
        initiator_id="user-1",
        human_verifier="user-1",
    )
    assert v_sod_same.approved is False
    assert v_sod_same.code == "REJECTED_UNTRUSTED_AI_SOD"

    v_ok = review.evaluate_scoped(
        write_action,
        guard.sign_action(write_action),
        taint=DataTaint.UNTRUSTED_AI,
        initiator_id="agent-1",
        human_verifier="planner-maria",
    )
    assert v_ok.approved is True
    assert v_ok.code == "APPROVED_FOR_WRITEBACK"


def test_verify_numeric_conservation():
    src = "Evaluated 1,250 lines with 10.00 EUR variance and 0 errors."
    ok = verify_numeric_conservation(
        src, "We checked 1250 lines; variance is 10 EUR with 0 errors."
    )
    assert ok.ok is True

    drifted = verify_numeric_conservation(
        src, "We checked 1250 lines; variance is 12.00 EUR with 0 errors."
    )
    assert drifted.ok is False
    assert "10" in drifted.missing_numbers
    assert "12" in drifted.invented_numbers


def test_column_semantics_probe_detects_bpi_repeated_snapshot_and_cumulative():
    probe = ColumnSemanticsProbe()

    # Repeated snapshot (each GR repeats full PO item value, sum != ref)
    repeated_rows = [
        {"case": "PO-1", "amt": "100.00", "ref": "100.00"},
        {"case": "PO-1", "amt": "100.00", "ref": "100.00"},
        {"case": "PO-2", "amt": "250.00", "ref": "250.00"},
        {"case": "PO-2", "amt": "250.00", "ref": "250.00"},
    ]
    r_rep = probe.inspect(
        repeated_rows, case_col="case", value_col="amt", ref_value_col="ref"
    )
    assert r_rep.status == SemanticsClass.REPEATED_SNAPSHOT
    assert r_rep.safe_to_sum is False

    # Monotonic cumulative
    cum_rows = [
        {"case": "PO-1", "amt": "40", "ref": "100"},
        {"case": "PO-1", "amt": "100", "ref": "100"},
        {"case": "PO-2", "amt": "50", "ref": "120"},
        {"case": "PO-2", "amt": "120", "ref": "120"},
    ]
    r_cum = probe.inspect(
        cum_rows, case_col="case", value_col="amt", ref_value_col="ref"
    )
    assert r_cum.status == SemanticsClass.MONOTONIC_CUMULATIVE
    assert r_cum.safe_to_sum is False

    # Clean additive
    add_rows = [
        {"case": "PO-1", "amt": "40", "ref": "100"},
        {"case": "PO-1", "amt": "60", "ref": "100"},
        {"case": "PO-2", "amt": "70", "ref": "120"},
        {"case": "PO-2", "amt": "50", "ref": "120"},
    ]
    r_add = probe.inspect(
        add_rows, case_col="case", value_col="amt", ref_value_col="ref"
    )
    assert r_add.status == SemanticsClass.INCREMENTAL_ADDITIVE
    assert r_add.safe_to_sum is True

    # Unreadable rows block safe_to_sum and NOT_EVALUABLE when too few cases
    r_empty = probe.inspect(
        [{"case": "PO-1", "amt": "bad"}], case_col="case", value_col="amt"
    )
    assert r_empty.status == SemanticsClass.NOT_EVALUABLE
    assert r_empty.unreadable_rows == 1
    assert r_empty.safe_to_sum is False


def test_iterative_split_probe_catches_multistep_and_ignores_recurring_volume():
    probe = IterativeSplitProbe()
    rows = [
        # Iterative split: 5 steps * 250 = 1250 > 1000 within 5 days
        {"vendor": "V-SPLIT", "amt": "250", "day": "2026-11-01"},
        {"vendor": "V-SPLIT", "amt": "250", "day": "2026-11-02"},
        {"vendor": "V-SPLIT", "amt": "250", "day": "2026-11-03"},
        {"vendor": "V-SPLIT", "amt": "250", "day": "2026-11-04"},
        {"vendor": "V-SPLIT", "amt": "250", "day": "2026-11-05"},
        # Recurring high volume: 5 * 900 = 4500 > 3 * 1000 ceiling -> excluded
        {"vendor": "V-REC", "amt": "900", "day": "2026-11-01"},
        {"vendor": "V-REC", "amt": "900", "day": "2026-11-02"},
        {"vendor": "V-REC", "amt": "900", "day": "2026-11-03"},
        {"vendor": "V-REC", "amt": "900", "day": "2026-11-04"},
        {"vendor": "V-REC", "amt": "900", "day": "2026-11-05"},
        # Unreadable row
        {"vendor": "V-BAD", "amt": "N/A", "day": "not-a-date"},
    ]
    alerts, unreadable = probe.detect(
        rows,
        entity_col="vendor",
        amount_col="amt",
        date_col="day",
        threshold=Decimal("1000"),
        window_days=7,
    )
    assert unreadable == 1
    assert len(alerts) == 1
    assert alerts[0].entity_id == "V-SPLIT"
    assert alerts[0].step_count == 5
    assert alerts[0].rolling_sum == Decimal("1250")


def test_boundary_rejection_emits_valid_event_envelope(tmp_path):
    ref = _load_reference_contract()
    ev = boundary_rejection_to_event(
        "PROMPT_INJECTION_CONTROL_FIELD",
        "Forbidden control key smuggled: $.auto_approve",
        target_system="erp-odoo",
        action_id="act-inj-01",
        taint=DataTaint.UNTRUSTED_AI.value,
        occurred_at="2026-11-26T10:00:00-03:00",
        paths=("$.auto_approve",),
    )
    stream = seal_stream([ev])
    assert ref.verify_stream(stream) == []
    out_path = tmp_path / "boundary.jsonl"
    write_jsonl(out_path, stream)
    assert ref.main(["verify", str(out_path)]) == 0


def test_fdekit_ithildin_is_stdlib_only():
    src = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import sys; before = set(sys.modules); import fdekit.ithildin; "
        "added = {m.split('.')[0] for m in set(sys.modules) - before}; "
        "print(sorted(added - set(sys.stdlib_module_names) - {'fdekit'}))"
    )
    env = {**os.environ, "PYTHONPATH": str(src)}
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env
    )
    assert proc.stdout.strip() == "[]"
