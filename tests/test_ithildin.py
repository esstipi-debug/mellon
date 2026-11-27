"""Unit tests for fdekit.ithildin (guards, probes, triggers)."""

from datetime import datetime, timezone

import pytest

from fdekit.ithildin import (
    ConditionalTrigger,
    IthildinGuard,
    IthildinTriggerRegistry,
    PassiveEventProbe,
    RiskLevel,
    StagingAction,
)

# --- Tests for IthildinGuard ---


def test_guard_requires_sufficient_entropy():
    with pytest.raises(ValueError, match="at least 16 bytes"):
        IthildinGuard(secret_key=b"too-short")


def test_staging_action_validation():
    with pytest.raises(ValueError, match="action_id"):
        StagingAction(
            action_id="",
            risk_level=RiskLevel.READ,
            target_system="SAP",
            payload={"a": 1},
            idempotency_key="k1",
            timestamp_utc="2026-10-20T12:00:00Z",
        )

    with pytest.raises(ValueError, match="idempotency_key"):
        StagingAction(
            action_id="act-1",
            risk_level=RiskLevel.READ,
            target_system="SAP",
            payload={"a": 1},
            idempotency_key="",
            timestamp_utc="2026-10-20T12:00:00Z",
        )


def test_guard_signature_and_tamper_detection():
    secret = b"super-secure-secret-key-2026-entropy"
    guard = IthildinGuard(secret)

    action = StagingAction(
        action_id="act-101",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="WMS_MANHATTAN",
        payload={"order_id": "ORD-99", "status": "HOLD"},
        idempotency_key="idemp-101",
        timestamp_utc="2026-10-20T12:00:00Z",
    )

    token = guard.sign_action(action)
    assert token.startswith("ithildin-v1-")
    assert guard.verify_signature(action, token) is True

    # Tampering with payload
    tampered_action = StagingAction(
        action_id="act-101",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="WMS_MANHATTAN",
        payload={"order_id": "ORD-99", "status": "CANCELLED"},  # altered
        idempotency_key="idemp-101",
        timestamp_utc="2026-10-20T12:00:00Z",
    )
    assert guard.verify_signature(tampered_action, token) is False


def test_guard_evaluation_flow_and_idempotency():
    secret = b"super-secure-secret-key-2026-entropy"
    guard = IthildinGuard(secret)

    action = StagingAction(
        action_id="act-201",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="ERP_SAP",
        payload={"item": "SKU-01", "qty": 10},
        idempotency_key="idemp-unique-201",
        timestamp_utc="2026-10-20T12:00:00Z",
    )
    token = guard.sign_action(action)

    # 1. First commit: should be approved
    verdict1 = guard.evaluate_and_commit(action, token, now_utc="2026-10-20T12:05:00Z")
    assert verdict1.approved is True
    assert verdict1.code == "APPROVED_FOR_WRITEBACK"
    assert len(guard.audit_ledger) == 1

    # 2. Duplicate attempt with identical idempotency key: should be rejected
    verdict2 = guard.evaluate_and_commit(action, token, now_utc="2026-10-20T12:06:00Z")
    assert verdict2.approved is False
    assert verdict2.code == "REJECTED_DUPLICATE_IDEMPOTENCY"
    assert len(guard.audit_ledger) == 2


def test_guard_rejects_irreversible_without_rollback():
    secret = b"super-secure-secret-key-2026-entropy"
    guard = IthildinGuard(secret)

    # Without rollback plan
    action_no_rb = StagingAction(
        action_id="act-danger-1",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="ERP_SAP",
        payload={"delete_ledger": True},
        idempotency_key="idemp-danger-1",
        timestamp_utc="2026-10-20T12:00:00Z",
        rollback_plan=None,
    )
    token1 = guard.sign_action(action_no_rb)
    v1 = guard.evaluate_and_commit(action_no_rb, token1, now_utc="2026-10-20T12:05:00Z")
    assert v1.approved is False
    assert v1.code == "REJECTED_IRREVERSIBLE_WITHOUT_ROLLBACK"

    # With rollback plan
    action_with_rb = StagingAction(
        action_id="act-danger-2",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="ERP_SAP",
        payload={"delete_ledger": True},
        idempotency_key="idemp-danger-2",
        timestamp_utc="2026-10-20T12:00:00Z",
        rollback_plan={"restore_snapshot_id": "snap-9988"},
    )
    token2 = guard.sign_action(action_with_rb)
    v2 = guard.evaluate_and_commit(action_with_rb, token2, now_utc="2026-10-20T12:05:00Z")
    assert v2.approved is True
    assert v2.code == "APPROVED_FOR_WRITEBACK"


def test_staging_action_approved_by_validation_and_hmac_coverage():
    with pytest.raises(ValueError, match="approved_by cannot be blank"):
        StagingAction(
            action_id="act-app-blank",
            risk_level=RiskLevel.REVERSIBLE,
            target_system="SAP",
            payload={"a": 1},
            idempotency_key="k-app-blank",
            timestamp_utc="2026-10-20T12:00:00Z",
            approved_by="   ",
        )

    guard = IthildinGuard(b"super-secure-secret-key-2026-entropy")
    action = StagingAction(
        action_id="act-app-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="SAP",
        payload={"a": 1},
        idempotency_key="k-app-1",
        timestamp_utc="2026-10-20T12:00:00Z",
        approved_by="planner-maria",
    )
    token = guard.sign_action(action)
    assert guard.verify_signature(action, token) is True

    spoofed = StagingAction(
        action_id="act-app-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="SAP",
        payload={"a": 1},
        idempotency_key="k-app-1",
        timestamp_utc="2026-10-20T12:00:00Z",
        approved_by="planner-other",
    )
    assert guard.verify_signature(spoofed, token) is False


def test_guard_ttl_expiration_and_invalid_timestamp():
    with pytest.raises(ValueError, match="ttl_seconds"):
        IthildinGuard(b"super-secure-secret-key-2026-entropy", ttl_seconds=0)

    guard = IthildinGuard(b"super-secure-secret-key-2026-entropy")
    action = StagingAction(
        action_id="act-ttl-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="ERP_SAP",
        payload={"sku": "SKU-1"},
        idempotency_key="k-ttl-1",
        timestamp_utc="2026-10-20T12:00:00Z",
    )
    token = guard.sign_action(action)

    expired = guard.evaluate_and_commit(action, token, now_utc="2026-10-20T12:15:01Z")
    assert expired.approved is False
    assert expired.code == "REJECTED_EXPIRED_ACTION"

    future_skew = guard.evaluate_and_commit(action, token, now_utc="2026-10-20T11:54:59Z")
    assert future_skew.approved is False
    assert future_skew.code == "REJECTED_EXPIRED_ACTION"

    boundary_ok = guard.evaluate_and_commit(
        action,
        token,
        now_utc=datetime(2026, 10, 20, 12, 15, 0, tzinfo=timezone.utc),
    )
    assert boundary_ok.approved is True
    assert boundary_ok.code == "APPROVED_FOR_WRITEBACK"

    naive_action = StagingAction(
        action_id="act-naive-1",
        risk_level=RiskLevel.READ,
        target_system="ERP_SAP",
        payload={"sku": "SKU-1"},
        idempotency_key="k-naive-1",
        timestamp_utc="2026-10-20T12:00:00",
    )
    v_naive = guard.evaluate_and_commit(naive_action, guard.sign_action(naive_action))
    assert v_naive.approved is False
    assert v_naive.code == "REJECTED_INVALID_TIMESTAMP"


def test_guard_sqlite_persistence_across_instances(tmp_path):
    db_path = tmp_path / "guard.db"
    secret = b"super-secure-secret-key-2026-entropy"
    guard_a = IthildinGuard(secret, store_path=db_path)

    action = StagingAction(
        action_id="act-sql-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="ERP_SAP",
        payload={"sku": "SKU-99"},
        idempotency_key="k-sql-1",
        timestamp_utc="2026-10-20T12:00:00Z",
    )
    token = guard_a.sign_action(action)
    v1 = guard_a.evaluate_and_commit(action, token, now_utc="2026-10-20T12:05:00Z")
    assert v1.approved is True

    guard_b = IthildinGuard(secret, store_path=db_path)
    v2 = guard_b.evaluate_and_commit(action, token, now_utc="2026-10-20T12:06:00Z")
    assert v2.approved is False
    assert v2.code == "REJECTED_DUPLICATE_IDEMPOTENCY"

    # Confirm no Windows file lock prevents removing the SQLite file after guard calls
    db_path.unlink()
    assert not db_path.exists()


def test_guard_rejects_placeholder_and_non_executable_rollback_plans():
    guard = IthildinGuard(b"super-secure-secret-key-2026-entropy")
    bad_plans = [
        {"todo": "later"},
        {"notes": "manual fix"},
        {"strategy": "tbd"},
        {"steps": []},
        {"strategy": "compensate", "fixme": "check later"},
    ]
    for idx, plan in enumerate(bad_plans):
        action = StagingAction(
            action_id=f"act-bad-rb-{idx}",
            risk_level=RiskLevel.IRREVERSIBLE,
            target_system="ERP_SAP",
            payload={"writeoff": 10},
            idempotency_key=f"k-bad-rb-{idx}",
            timestamp_utc="2026-10-20T12:00:00Z",
            rollback_plan=plan,
        )
        verdict = guard.evaluate_and_commit(
            action,
            guard.sign_action(action),
            now_utc="2026-10-20T12:01:00Z",
        )
        assert verdict.approved is False
        assert verdict.code == "REJECTED_INVALID_ROLLBACK_PLAN"

    good_action = StagingAction(
        action_id="act-good-rb",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="ERP_SAP",
        payload={"writeoff": 10},
        idempotency_key="k-good-rb",
        timestamp_utc="2026-10-20T12:00:00Z",
        rollback_plan={"restore_snapshot": "snap-1", "steps": ["reverse_je"]},
    )
    good_verdict = guard.evaluate_and_commit(
        good_action,
        guard.sign_action(good_action),
        now_utc="2026-10-20T12:01:00Z",
    )
    assert good_verdict.approved is True
    assert good_verdict.code == "APPROVED_FOR_WRITEBACK"


# --- Tests for PassiveEventProbe ---


def test_passive_probe_empty_records():
    probe = PassiveEventProbe()
    report = probe.inspect([])
    assert report.total_records == 0
    assert report.is_safe_for_inference is False
    assert report.quality_score == 0.0


def test_passive_probe_clean_data():
    probe = PassiveEventProbe()
    records = [
        {
            "case_id": "CASE-1",
            "activity": "RECEIVE",
            "timestamp": "2026-10-20T10:00:00+00:00",
            "resource": "OP-01",
            "location": "DOCK-1",
        },
        {
            "case_id": "CASE-1",
            "activity": "PUTAWAY",
            "timestamp": "2026-10-20T10:30:00+00:00",
            "resource": "OP-02",
            "location": "AISLE-3",
        },
    ]
    report = probe.inspect(records)
    assert report.total_records == 2
    assert report.missing_columns == ()
    assert report.unparseable_timestamps == 0
    assert report.tz_naive_timestamps == 0
    assert report.out_of_order_cases == 0
    assert report.quality_score >= 0.95
    assert report.is_safe_for_inference is True


def test_passive_probe_detects_anomalies():
    probe = PassiveEventProbe()
    records = [
        # Missing location, tz-naive timestamp
        {
            "case_id": "CASE-2",
            "activity": "PICK",
            "timestamp": "2026-10-20T11:00:00",
            "resource": "OP-01",
        },
        # Corrupt timestamp
        {
            "case_id": "CASE-2",
            "activity": "PACK",
            "timestamp": "invalid-datetime-string",
            "resource": "OP-02",
        },
    ]
    report = probe.inspect(records)
    assert "location" in report.missing_columns
    assert report.unparseable_timestamps == 1
    assert report.tz_naive_timestamps == 1
    assert report.is_safe_for_inference is False


# --- Tests for ConditionalTrigger and Registry ---


def test_conditional_trigger_illumination_and_cooldown():
    trigger = ConditionalTrigger(
        name="high_latency_warning",
        predicate=lambda ev: ev.get("latency_ms", 0) > 500,
        cooldown_seconds=10.0,
    )

    # 1. Does not meet predicate
    res1 = trigger.evaluate({"latency_ms": 120}, current_epoch=1000.0)
    assert res1.illuminated is False

    # 2. Meets predicate -> Illuminated
    res2 = trigger.evaluate({"latency_ms": 750}, current_epoch=1001.0)
    assert res2.illuminated is True
    assert res2.silenced_by_cooldown is False

    # 3. Meets predicate during cooldown -> Silenced
    res3 = trigger.evaluate({"latency_ms": 800}, current_epoch=1005.0)
    assert res3.illuminated is False
    assert res3.silenced_by_cooldown is True

    # 4. Meets predicate after cooldown expiry -> Illuminated
    res4 = trigger.evaluate({"latency_ms": 900}, current_epoch=1012.0)
    assert res4.illuminated is True
    assert res4.silenced_by_cooldown is False


def test_trigger_registry():
    t1 = ConditionalTrigger(
        name="t1", predicate=lambda ev: ev.get("tag") == "alert", cooldown_seconds=0
    )
    t2 = ConditionalTrigger(
        name="t2", predicate=lambda ev: ev.get("urgent") is True, cooldown_seconds=0
    )

    reg = IthildinTriggerRegistry([t1, t2])
    illuminated = reg.get_illuminated({"tag": "alert", "urgent": False}, current_epoch=100.0)

    assert len(illuminated) == 1
    assert illuminated[0].trigger_name == "t1"


def test_guard_rejects_nan_in_canonical_bytes():
    guard = IthildinGuard(b"super-secure-secret-key-2026-entropy")
    action = StagingAction(
        action_id="act-nan-1",
        risk_level=RiskLevel.REVERSIBLE,
        target_system="ERP_SAP",
        payload={"qty": float("nan")},
        idempotency_key="idemp-nan-1",
        timestamp_utc="2026-10-20T12:00:00Z",
    )
    with pytest.raises(ValueError):
        guard.sign_action(action)
