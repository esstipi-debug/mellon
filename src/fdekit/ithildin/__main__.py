"""Stdlib-only runnable mechanism proof for fdekit.ithildin on BPI 2019 P2P logs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .boundary import (
    BoundaryViolation,
    ColumnSemanticsProbe,
    DataTaint,
    ExecutionMode,
    ScopedIthildinGuard,
    UntrustedPayloadFence,
)
from .envelope_bridge import (
    _canonical_bytes,
    _normalize_utc_z,
    boundary_rejection_to_event,
    seal_stream,
    verdict_to_event,
    write_jsonl,
)
from .guards import IthildinGuard, RiskLevel, StagingAction

STREAM_NAME = "ithildin-bpi2019-demo"
_DEMO_SECRET = b"mellon-ithildin-bpi2019-demo-key"


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach CLI arguments for the BPI 2019 boundary verification runner."""
    parser.add_argument("csv_path", type=Path, help="Path to BPI-style P2P CSV log")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output path for the sealed event-envelope/1 JSONL stream",
    )
    parser.add_argument(
        "--activity",
        default="Record Goods Receipt",
        help="Activity name to evaluate (default: 'Record Goods Receipt')",
    )
    parser.add_argument(
        "--case-col",
        default="caso",
        help="Case identifier column name (default: 'caso')",
    )
    parser.add_argument(
        "--value-col",
        default="Cumulative net worth (EUR)",
        help="Numeric value column to probe (default: 'Cumulative net worth (EUR)')",
    )
    parser.add_argument(
        "--ref-col",
        default="po_item_value_eur",
        help="Reference PO item value column (default: 'po_item_value_eur')",
    )
    parser.add_argument(
        "--as-of-utc",
        default=None,
        help="Deterministic UTC ISO timestamp override (defaults to max CSV timestamp)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary",
    )
    return parser


def _resolve_as_of_utc(rows: list[dict[str, str]], override: str | None) -> str:
    if override is not None:
        return _normalize_utc_z(override)
    parsed: list[datetime] = []
    for row in rows:
        raw = (row.get("time:timestamp") or row.get("timestamp") or "").strip()
        if not raw:
            continue
        norm = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        parsed.append(dt.astimezone(timezone.utc))
    if not parsed:
        raise ValueError("CSV contains no valid timestamps and --as-of-utc was not provided")
    return _normalize_utc_z(max(parsed))


def run_boundary_demo(
    csv_path: Path,
    *,
    out_path: Path | None = None,
    activity: str = "Record Goods Receipt",
    case_col: str = "caso",
    value_col: str = "Cumulative net worth (EUR)",
    ref_col: str = "po_item_value_eur",
    as_of_utc: str | None = None,
) -> dict[str, Any]:
    """Run baseline vs ColumnSemanticsProbe vs ScopedIthildinGuard and seal envelopes."""
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file is empty: {csv_path}")

    activity_col = (
        "concept:name"
        if "concept:name" in fieldnames
        else ("activity" if "activity" in fieldnames else None)
    )
    activity_rows = (
        [r for r in rows if r.get(activity_col) == activity]
        if activity_col is not None and activity
        else rows
    )
    if not activity_rows:
        raise ValueError(f"No rows found matching activity={activity!r} in {csv_path}")

    resolved_utc = _resolve_as_of_utc(rows, as_of_utc)

    # a) Naive SQL/pandas baseline per case on activity rows
    by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in activity_rows:
        cid = (row.get(case_col) or "").strip()
        if cid:
            by_case[cid].append(row)

    naive_sum = Decimal("0")
    actual_po = Decimal("0")
    false_over_receipt_cases = 0
    for cid in sorted(by_case):
        case_rows = by_case[cid]
        case_naive = sum((Decimal(r[value_col].strip()) for r in case_rows), Decimal("0"))
        case_ref = Decimal(case_rows[-1][ref_col].strip())
        naive_sum += case_naive
        actual_po += case_ref
        if case_naive > case_ref * Decimal("1.01"):
            false_over_receipt_cases += 1

    inflation_factor = (
        (naive_sum / actual_po).quantize(Decimal("0.01"))
        if actual_po > 0
        else Decimal("0.00")
    )

    # b) ColumnSemanticsProbe
    probe = ColumnSemanticsProbe()
    semantics = probe.inspect(
        activity_rows,
        case_col=case_col,
        value_col=value_col,
        ref_value_col=ref_col,
    )

    # c) Guarded AI actions under FORENSIC_READONLY + UntrustedPayloadFence
    guard = IthildinGuard(_DEMO_SECRET)
    scoped = ScopedIthildinGuard(guard, mode=ExecutionMode.FORENSIC_READONLY)

    action_1 = StagingAction(
        action_id="bpi2019-erp-writeback-01",
        risk_level=RiskLevel.IRREVERSIBLE,
        target_system="sap-s4hana-mm",
        payload={
            "operation": "post_over_receipt_block",
            "activity": activity,
            "naive_sum_eur": format(naive_sum, "f"),
            "actual_po_value_eur": format(actual_po, "f"),
            "inflation_factor": format(inflation_factor, "f"),
            "flagged_cases": false_over_receipt_cases,
            "semantics_status": semantics.status.value,
        },
        idempotency_key="bpi2019-writeback-01",
        timestamp_utc=resolved_utc,
    )
    verdict_1 = scoped.evaluate_scoped(
        action_1,
        guard.sign_action(action_1),
        taint=DataTaint.UNTRUSTED_AI,
        initiator_id="ai-audit-agent",
        evaluated_at_utc=resolved_utc,
    )

    action_2 = StagingAction(
        action_id="bpi2019-ai-query-02",
        risk_level=RiskLevel.READ,
        target_system="sap-s4hana-mm",
        payload={
            "query": "release_blocked_po_items",
            "flagged_cases": false_over_receipt_cases,
            "auto_approve": True,
        },
        idempotency_key="bpi2019-query-02",
        timestamp_utc=resolved_utc,
    )
    verdict_2 = scoped.evaluate_scoped(
        action_2,
        guard.sign_action(action_2),
        taint=DataTaint.UNTRUSTED_AI,
        initiator_id="ai-audit-agent",
        evaluated_at_utc=resolved_utc,
    )

    fence_code = verdict_2.code
    fence_detail = verdict_2.reason
    fence_paths: tuple[str, ...] = ()
    try:
        UntrustedPayloadFence().validate_payload(action_2.payload)
    except BoundaryViolation as exc:
        fence_code = exc.code
        fence_detail = exc.detail
        fence_paths = exc.paths

    # d) Deterministic event-envelope/1 stream
    events = [
        verdict_to_event(action_1, verdict_1, stream=STREAM_NAME),
        verdict_to_event(action_2, verdict_2, stream=STREAM_NAME),
        boundary_rejection_to_event(
            fence_code,
            fence_detail,
            target_system=action_2.target_system,
            action_id=action_2.action_id,
            taint=DataTaint.UNTRUSTED_AI.value,
            occurred_at=resolved_utc,
            recorded_at=resolved_utc,
            stream=STREAM_NAME,
            paths=fence_paths,
        ),
    ]
    sealed = seal_stream(events)
    jsonl_bytes = "".join(
        _canonical_bytes(env).decode("utf-8") + "\n" for env in sealed
    ).encode("utf-8")
    stream_sha256 = hashlib.sha256(jsonl_bytes).hexdigest()

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(out_path, sealed)

    return {
        "csv_path": str(csv_path),
        "out_path": str(out_path) if out_path is not None else None,
        "as_of_utc": resolved_utc,
        "activity": activity,
        "total_csv_rows": len(rows),
        "activity_rows": len(activity_rows),
        "total_cases": len(by_case),
        "multi_event_cases": semantics.multi_event_cases,
        "naive_sum_eur": format(naive_sum, "f"),
        "actual_po_value_eur": format(actual_po, "f"),
        "inflation_factor": format(inflation_factor, "f"),
        "naive_false_over_receipt_cases": false_over_receipt_cases,
        "semantics_status": semantics.status.value,
        "safe_to_sum": semantics.safe_to_sum,
        "all_equal_ratio": format(semantics.all_equal_ratio, "f"),
        "sum_matches_ref_ratio": (
            format(semantics.sum_matches_ref_ratio, "f")
            if semantics.sum_matches_ref_ratio is not None
            else None
        ),
        "last_matches_ref_ratio": (
            format(semantics.last_matches_ref_ratio, "f")
            if semantics.last_matches_ref_ratio is not None
            else None
        ),
        "action_1_code": verdict_1.code,
        "action_2_code": verdict_2.code,
        "boundary_event_code": fence_code,
        "envelope_count": len(sealed),
        "stream_sha256": stream_sha256,
    }


def run_cli(args: argparse.Namespace) -> int:
    """Execute the boundary demo from parsed CLI arguments."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    result = run_boundary_demo(
        args.csv_path,
        out_path=args.out,
        activity=args.activity,
        case_col=args.case_col,
        value_col=args.value_col,
        ref_col=args.ref_col,
        as_of_utc=args.as_of_utc,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        out_label = result["out_path"] or "<not written; pass --out to save>"
        print(f"BPI Boundary Check ({result['csv_path']})")
        print(
            f"  Cases: {result['total_cases']} ({result['multi_event_cases']} multi-event) | "
            f"Activity rows ({result['activity']}): {result['activity_rows']} / {result['total_csv_rows']}"
        )
        print(
            f"  Naive SUM: {result['naive_sum_eur']} EUR vs Actual PO: {result['actual_po_value_eur']} EUR "
            f"({result['inflation_factor']}x inflation, {result['naive_false_over_receipt_cases']} false over-receipt cases)"
        )
        print(
            f"  ColumnSemanticsProbe: {result['semantics_status']} | safe_to_sum={result['safe_to_sum']} | "
            f"all_equal_ratio={result['all_equal_ratio']}"
        )
        print(
            f"  ScopedIthildinGuard (FORENSIC_READONLY): "
            f"action_1={result['action_1_code']}, action_2={result['action_2_code']}"
        )
        print(
            f"  Sealed stream ({result['envelope_count']} event-envelope/1 records): "
            f"out={out_label} | sha256={result['stream_sha256']}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for `python -m fdekit.ithildin`."""
    parser = configure_parser(
        argparse.ArgumentParser(
            prog="python -m fdekit.ithildin",
            description="Stdlib-only BPI 2019 boundary verification demo.",
        )
    )
    args = parser.parse_args(argv)
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
