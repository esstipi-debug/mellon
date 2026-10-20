"""Tests for the launch-readiness gate (ad spend x stock x dispatch capacity)."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fdekit.ithildin import IthildinGuard
from fdekit.launch_readiness_gate import (
    CHANGESET_TTL_SECONDS,
    CODE_EXPIRED_TTL,
    DECISION_HOLD,
    DECISION_KEEP,
    DECISION_PAUSE,
    DECISION_REDUCE,
    HMAC_KEY_ENV,
    RUN_ESCALATED,
    RUN_HANDOFF,
    RUN_STAGED,
    GatePolicy,
    authorize_changeset,
    build_changeset,
    decide_sku,
    dispatch_capacity,
    main,
    run_gate,
    stockout_probability,
    synthesize_snapshot,
)

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "launch_gate" / "inventory_ads_snapshot.csv"
T0 = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
KEY = b"test-key-for-hmac-0123456789"

CAPACITY = pd.DataFrame(
    {
        "n_pickers": [4, 6],
        "throughput_per_h": [60.7, 80.0],
        "picker_util": [0.998, 0.891],
    }
)


def _row(**kw) -> pd.Series:
    base = dict(
        snapshot_date="2026-03-02",
        sku_id="S00001",
        on_hand_units=500.0,
        allocated_units=0.0,
        daily_demand_units=10.0,
        demand_sd_units=3.0,
        replenishment_lead_time_days=7,
        lead_time_sd_days=1.0,
        next_receipt_in_days=np.nan,
        channel="google_ads",
        campaign_id="CMP-1",
        daily_budget_usd=100.0,
        ad_driven_demand_share=0.5,
    )
    base.update(kw)
    return pd.Series(base)


def _snapshot(*rows: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


@pytest.fixture
def guard() -> IthildinGuard:
    return IthildinGuard(KEY)


# ---------------------------------------------------------- stock model


def test_no_available_stock_means_certain_stockout():
    assert stockout_probability(0, 10, 2, 7, 1) == 1.0


def test_ample_cover_means_negligible_stockout():
    assert stockout_probability(10_000, 10, 2, 7, 1) < 1e-6


def test_stockout_probability_matches_normal_at_mean():
    # Available exactly equals expected demand: P = 0.5.
    assert stockout_probability(70, 10, 3, 7, 0) == pytest.approx(0.5)


def test_zero_variance_is_deterministic():
    assert stockout_probability(69, 10, 0, 7, 0) == 1.0
    assert stockout_probability(71, 10, 0, 7, 0) == 0.0


# ----------------------------------------------------------- decisions

POLICY = GatePolicy()


def test_healthy_sku_keeps_budget():
    d = decide_sku(_row(), POLICY)
    assert d.decision == DECISION_KEEP
    assert d.new_budget_usd == 100.0


def test_out_of_stock_sku_is_paused():
    d = decide_sku(_row(on_hand_units=20, allocated_units=20), POLICY)
    assert d.decision == DECISION_PAUSE
    assert d.new_budget_usd == 0.0
    assert d.stockout_probability == 1.0


def test_sku_that_runs_out_before_replenishment_is_paused():
    d = decide_sku(_row(on_hand_units=40), POLICY)
    assert d.decision == DECISION_PAUSE


def test_scheduled_receipt_shortens_protection_interval():
    # 40 units cover 4 days; a receipt in 2 days rescues the SKU.
    d = decide_sku(_row(on_hand_units=40, next_receipt_in_days=2), POLICY)
    assert d.protection_days == 2.0
    assert d.decision == DECISION_KEEP


def test_receipt_later_than_lead_time_is_ignored():
    d = decide_sku(_row(next_receipt_in_days=30), POLICY)
    assert d.protection_days == 7.0


def test_borderline_sku_has_budget_reduced_not_paused():
    # Expected demand 70 over 7 days; 80 available (P ~ 0.20) puts P(stockout) between thresholds.
    d = decide_sku(_row(on_hand_units=80, demand_sd_units=4.0, lead_time_sd_days=0.5), POLICY)
    assert POLICY.reduce_stockout_probability <= d.stockout_probability < POLICY.pause_stockout_probability
    assert d.decision == DECISION_REDUCE
    assert 0 < d.new_budget_usd < 100.0
    # Reduced plan lowers projected demand below the original.
    assert d.projected_daily_demand_units < 10.0


def test_reduction_below_minimum_scale_becomes_pause():
    strict = GatePolicy(min_budget_scale=0.99)
    d = decide_sku(_row(on_hand_units=80, demand_sd_units=4.0, lead_time_sd_days=0.5), strict)
    assert d.decision == DECISION_PAUSE


@pytest.mark.parametrize(
    "field,value",
    [
        ("on_hand_units", np.nan),
        ("daily_demand_units", np.nan),
        ("daily_demand_units", -1.0),
        ("replenishment_lead_time_days", 0),
        ("ad_driven_demand_share", 1.5),
    ],
)
def test_invalid_rows_are_held_never_treated_as_zero(field, value):
    d = decide_sku(_row(**{field: value}), POLICY)
    assert d.decision == DECISION_HOLD
    assert d.stockout_probability is None
    assert d.new_budget_usd is None


def test_policy_rejects_inverted_thresholds():
    with pytest.raises(ValueError):
        GatePolicy(pause_stockout_probability=0.1, reduce_stockout_probability=0.5)


# ---------------------------------------------------------- changesets


def test_changeset_signature_verifies_and_commits_once(guard):
    d = decide_sku(_row(on_hand_units=0), POLICY)
    cs = build_changeset(d, "2026-03-02", guard, now=T0)

    first = authorize_changeset(cs, guard, now=T0 + timedelta(seconds=60))
    second = authorize_changeset(cs, guard, now=T0 + timedelta(seconds=61))

    assert first.approved and first.code == "APPROVED_FOR_WRITEBACK"
    assert not second.approved and second.code == "REJECTED_DUPLICATE_IDEMPOTENCY"


def test_changeset_expires_after_900_seconds(guard):
    d = decide_sku(_row(on_hand_units=0), POLICY)
    cs = build_changeset(d, "2026-03-02", guard, now=T0)

    late = authorize_changeset(cs, guard, now=T0 + timedelta(seconds=CHANGESET_TTL_SECONDS + 1))

    assert CHANGESET_TTL_SECONDS == 900
    assert not late.approved
    assert late.code == CODE_EXPIRED_TTL


def test_tampered_budget_breaks_signature(guard):
    d = decide_sku(_row(on_hand_units=0), POLICY)
    cs = build_changeset(d, "2026-03-02", guard, now=T0)
    forged_action = dataclasses.replace(cs.action, payload={**cs.action.payload, "daily_budget_usd": 999.0})
    forged = dataclasses.replace(cs, action=forged_action)

    v = authorize_changeset(forged, guard, now=T0)

    assert not v.approved and v.code == "FORBIDDEN_INVALID_SIGNATURE"


def test_extending_the_expiry_breaks_signature(guard):
    d = decide_sku(_row(on_hand_units=0), POLICY)
    cs = build_changeset(d, "2026-03-02", guard, now=T0)
    far = (T0 + timedelta(days=1)).isoformat()
    forged_action = dataclasses.replace(cs.action, payload={**cs.action.payload, "expires_at_utc": far})
    forged = dataclasses.replace(cs, action=forged_action, expires_at_utc=far)

    v = authorize_changeset(forged, guard, now=T0 + timedelta(hours=1))

    assert not v.approved and v.code == "FORBIDDEN_INVALID_SIGNATURE"


def test_changeset_is_reversible_with_rollback_to_previous_budget(guard):
    d = decide_sku(_row(on_hand_units=0, daily_budget_usd=123.45), POLICY)
    cs = build_changeset(d, "2026-03-02", guard, now=T0)
    assert cs.action.risk_level.value == "REVERSIBLE"
    assert cs.action.rollback_plan["daily_budget_usd"] == 123.45
    assert cs.action.payload["daily_budget_usd"] == 0.0


def test_keep_decision_produces_no_changeset(guard):
    with pytest.raises(ValueError):
        build_changeset(decide_sku(_row(), POLICY), "2026-03-02", guard, now=T0)


def test_wrong_key_cannot_authorize(guard):
    d = decide_sku(_row(on_hand_units=0), POLICY)
    cs = build_changeset(d, "2026-03-02", guard, now=T0)
    other = IthildinGuard(b"another-key-0123456789abcdef")
    assert authorize_changeset(cs, other, now=T0).code == "FORBIDDEN_INVALID_SIGNATURE"


# ------------------------------------------------------------ run level


def test_run_with_all_valid_rows_is_staged(guard):
    snap = _snapshot(_row(), _row(sku_id="S2", campaign_id="CMP-2", on_hand_units=0))
    r = run_gate(snap, CAPACITY, guard, n_pickers=6, shift_hours=16, now=T0)
    assert r["run_outcome"] == RUN_STAGED
    assert r["requires_human_signoff"] is True
    assert r["decision_counts"][DECISION_PAUSE] == 1
    assert len(r["changesets"]) == 1
    assert r["ad_spend_on_oos_usd_per_day"] == 100.0


def test_run_with_a_held_row_is_handoff(guard):
    snap = _snapshot(_row(), _row(sku_id="S2", campaign_id="CMP-2", on_hand_units=np.nan))
    r = run_gate(snap, CAPACITY, guard, n_pickers=6, shift_hours=16, now=T0)
    assert r["run_outcome"] == RUN_HANDOFF
    assert [h["sku_id"] for h in r["held_for_review"]] == ["S2"]


def test_demand_above_dispatch_capacity_escalates(guard):
    snap = _snapshot(_row(on_hand_units=1e7, daily_demand_units=10_000.0))
    r = run_gate(snap, CAPACITY, guard, n_pickers=6, shift_hours=1, now=T0)
    assert r["capacity_breach"] is True
    assert r["run_outcome"] == RUN_ESCALATED


def test_saturated_staffing_level_escalates(guard):
    r = run_gate(_snapshot(_row()), CAPACITY, guard, n_pickers=4, shift_hours=16, now=T0)
    assert r["utilization_breach"] is True
    assert r["run_outcome"] == RUN_ESCALATED


def test_capacity_lookup_requires_known_staffing_level():
    with pytest.raises(ValueError, match="no staffing row"):
        dispatch_capacity(CAPACITY, n_pickers=99, shift_hours=8)
    assert dispatch_capacity(CAPACITY, 6, 10)["orders_per_day"] == 800.0


def test_snapshot_must_have_single_date_and_all_columns(guard):
    two_dates = _snapshot(_row(), _row(snapshot_date="2026-03-03", sku_id="S2"))
    with pytest.raises(ValueError, match="exactly one date"):
        run_gate(two_dates, CAPACITY, guard, 6, 16, now=T0)
    with pytest.raises(ValueError, match="missing columns"):
        run_gate(_snapshot(_row()).drop(columns=["campaign_id"]), CAPACITY, guard, 6, 16, now=T0)


# ------------------------------------------------- example data and CLI


def test_committed_example_matches_generator():
    committed = pd.read_csv(EXAMPLE)
    regenerated = synthesize_snapshot()
    pd.testing.assert_frame_equal(committed, regenerated, check_dtype=False)
    assert (committed["data_provenance"] == "SYNTHETIC").all()


def test_example_snapshot_exercises_every_decision(guard):
    r = run_gate(pd.read_csv(EXAMPLE), CAPACITY, guard, 6, 16, now=T0)
    for k in (DECISION_KEEP, DECISION_REDUCE, DECISION_PAUSE, DECISION_HOLD):
        assert r["decision_counts"][k] >= 1, k


def test_cli_refuses_to_run_without_signing_key(monkeypatch, demo_out, tmp_path):
    monkeypatch.delenv(HMAC_KEY_ENV, raising=False)
    with pytest.raises(SystemExit, match=HMAC_KEY_ENV):
        main(["--snapshot", str(EXAMPLE), "--capacity", str(demo_out / "dimensionamiento.csv"),
              "--pickers", "6", "--out-dir", str(tmp_path)])


def test_cli_end_to_end_on_demo_capacity(monkeypatch, demo_out, tmp_path):
    monkeypatch.setenv(HMAC_KEY_ENV, KEY.decode())
    rc = main(["--snapshot", str(EXAMPLE), "--capacity", str(demo_out / "dimensionamiento.csv"),
               "--pickers", "6", "--out-dir", str(tmp_path)])
    assert rc == 0
    report = json.loads((tmp_path / "launch_gate_report.json").read_text(encoding="utf-8"))
    lines = (tmp_path / "launch_gate_changesets.jsonl").read_text(encoding="utf-8").splitlines()
    assert report["n_changesets"] == len(lines) > 0
    assert all(json.loads(l)["token"].startswith("ithildin-v1-") for l in lines)
