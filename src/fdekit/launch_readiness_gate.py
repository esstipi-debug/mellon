"""Launch-readiness gate: interlock ad spend with stock and dispatch capacity (Pillar 4).

Marketing buys demand; the DC has to ship it. This gate reads one inventory +
campaign snapshot and decides, per SKU, whether its digital ad budget (Google
Ads / Meta) should be kept, reduced, or paused, based on the probability of a
stockout before the next replenishment. It then checks that the demand left
after those changes fits the DC's dispatch capacity.

The gate NEVER calls an ad platform. Every budget change is emitted as a
signed changeset under the Ithildin pattern (`fdekit.ithildin.IthildinGuard`):

    * HMAC-SHA256 signature over the canonical action, including its expiry;
    * 900-second TTL: an approval older than that is rejected, because the
      stock position it was computed from has drifted;
    * idempotency key per (snapshot, campaign, action, new budget);
    * rollback plan restoring the previous budget (risk level REVERSIBLE).

Inputs:
    inventory_ads_snapshot.csv  one row per SKU x campaign. The copy under
                                `examples/launch_gate/` is SYNTHETIC
                                (`synthesize_snapshot`); a real deployment
                                joins the WMS stock position with the ad
                                platform's campaign export.
    dimensionamiento.csv        staffing sweep from `fdekit demo`: orders per
                                hour by number of pickers. Used only as the
                                dispatch-capacity constraint; it holds no stock
                                or lead-time data.

Stockout model: demand over the protection interval L is approximated as
Normal(d*L, sqrt(L*sd_d^2 + d^2*sd_L^2)). L is the time to the next scheduled
receipt when one exists, otherwise the replenishment lead time (with its
variance). Budget reduction assumes ad-driven demand scales linearly with
budget, which is an approximation to be replaced by the channel's measured
response curve.

Loud degradation: a row with missing or invalid stock or demand fields gets
HOLD_FOR_REVIEW and no changeset. It is never treated as zero stock or zero demand.

Run:
    FDE_GATE_HMAC_KEY=... python -m fdekit.launch_readiness_gate \
        --snapshot examples/launch_gate/inventory_ads_snapshot.csv \
        --capacity out/dimensionamiento.csv --pickers 6 --shift-hours 16
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

from fdekit.ithildin import IthildinGuard, RiskLevel, StagingAction, StagingVerdict

CHANGESET_TTL_SECONDS = 900
HMAC_KEY_ENV = "FDE_GATE_HMAC_KEY"

DECISION_KEEP = "KEEP"
DECISION_REDUCE = "REDUCE"
DECISION_PAUSE = "PAUSE"
DECISION_HOLD = "HOLD_FOR_REVIEW"

RUN_STAGED = "STAGED"
RUN_HANDOFF = "HANDOFF"
RUN_ESCALATED = "ESCALATED"

CODE_EXPIRED_TTL = "REJECTED_EXPIRED_TTL"

SNAPSHOT_COLUMNS = (
    "snapshot_date",
    "sku_id",
    "on_hand_units",
    "allocated_units",
    "daily_demand_units",
    "demand_sd_units",
    "replenishment_lead_time_days",
    "lead_time_sd_days",
    "next_receipt_in_days",
    "channel",
    "campaign_id",
    "daily_budget_usd",
    "ad_driven_demand_share",
)
_NUMERIC_REQUIRED = (
    "on_hand_units",
    "allocated_units",
    "daily_demand_units",
    "demand_sd_units",
    "replenishment_lead_time_days",
    "lead_time_sd_days",
    "daily_budget_usd",
    "ad_driven_demand_share",
)


@dataclass(frozen=True)
class GatePolicy:
    pause_stockout_probability: float = 0.50
    reduce_stockout_probability: float = 0.10
    min_budget_scale: float = 0.20
    units_per_order: float = 3.0
    max_picker_utilization: float = 0.95

    def __post_init__(self) -> None:
        if not 0 < self.reduce_stockout_probability < self.pause_stockout_probability < 1:
            raise ValueError("require 0 < reduce threshold < pause threshold < 1")
        if not 0 <= self.min_budget_scale < 1:
            raise ValueError("min_budget_scale must be in [0, 1)")
        if self.units_per_order <= 0:
            raise ValueError("units_per_order must be positive")


@dataclass(frozen=True)
class SkuDecision:
    sku_id: str
    campaign_id: str
    channel: str
    decision: str
    reason: str
    available_units: float | None
    protection_days: float | None
    stockout_probability: float | None
    current_budget_usd: float | None
    new_budget_usd: float | None
    projected_daily_demand_units: float | None


@dataclass(frozen=True)
class Changeset:
    action: StagingAction
    token: str
    expires_at_utc: str

    def to_json(self) -> dict:
        a = asdict(self.action)
        a["risk_level"] = self.action.risk_level.value
        return {"action": a, "token": self.token, "expires_at_utc": self.expires_at_utc}


# ------------------------------------------------------------- stock model


def stockout_probability(
    available: float,
    daily_demand: float,
    demand_sd: float,
    protection_days: float,
    lead_time_sd: float,
) -> float:
    """P(demand over the protection interval exceeds available stock)."""
    if available <= 0:
        return 1.0
    mu = daily_demand * protection_days
    sigma = math.sqrt(protection_days * demand_sd**2 + daily_demand**2 * lead_time_sd**2)
    if sigma == 0:
        return 1.0 if mu > available else 0.0
    return float(1.0 - stats.norm.cdf((available - mu) / sigma))


def _protection(row: pd.Series) -> tuple[float, float]:
    lead, lead_sd = float(row["replenishment_lead_time_days"]), float(row["lead_time_sd_days"])
    receipt = row.get("next_receipt_in_days")
    if receipt is not None and not pd.isna(receipt) and 0 <= float(receipt) < lead:
        # A scheduled receipt has a known date: no lead-time variance applies.
        return float(receipt), 0.0
    return lead, lead_sd


def _invalid_reason(row: pd.Series) -> str | None:
    missing = [c for c in _NUMERIC_REQUIRED if pd.isna(row.get(c))]
    if missing:
        return f"missing fields {missing}: stock position not trustworthy"
    if row["daily_demand_units"] < 0 or row["demand_sd_units"] < 0 or row["daily_budget_usd"] < 0:
        return "negative demand, demand SD, or budget"
    if row["replenishment_lead_time_days"] <= 0 or row["lead_time_sd_days"] < 0:
        return "non-positive lead time or negative lead-time SD"
    if not 0 <= row["ad_driven_demand_share"] <= 1:
        return "ad_driven_demand_share outside [0, 1]"
    if row["allocated_units"] < 0 or row["on_hand_units"] < 0:
        return "negative on-hand or allocated units"
    return None


def decide_sku(row: pd.Series, policy: GatePolicy) -> SkuDecision:
    base = dict(sku_id=str(row["sku_id"]), campaign_id=str(row["campaign_id"]), channel=str(row["channel"]))
    invalid = _invalid_reason(row)
    if invalid:
        budget = None if pd.isna(row.get("daily_budget_usd")) else float(row["daily_budget_usd"])
        return SkuDecision(
            **base, decision=DECISION_HOLD, reason=invalid, available_units=None, protection_days=None,
            stockout_probability=None, current_budget_usd=budget, new_budget_usd=None,
            projected_daily_demand_units=None,
        )

    available = float(row["on_hand_units"] - row["allocated_units"])
    demand = float(row["daily_demand_units"])
    sd = float(row["demand_sd_units"])
    budget = float(row["daily_budget_usd"])
    share = float(row["ad_driven_demand_share"])
    days, lead_sd = _protection(row)
    p = stockout_probability(available, demand, sd, days, lead_sd)
    organic = demand * (1 - share)
    ad_demand = demand * share

    def out(decision: str, reason: str, new_budget: float, scale: float) -> SkuDecision:
        return SkuDecision(
            **base, decision=decision, reason=reason, available_units=available, protection_days=days,
            stockout_probability=round(p, 4), current_budget_usd=budget, new_budget_usd=round(new_budget, 2),
            projected_daily_demand_units=round(organic + ad_demand * scale, 3),
        )

    if available <= 0:
        return out(DECISION_PAUSE, "out of stock: every ad click is wasted spend", 0.0, 0.0)
    if p >= policy.pause_stockout_probability:
        return out(
            DECISION_PAUSE,
            f"P(stockout before replenishment in {days:g} d) = {p:.0%} >= pause threshold",
            0.0,
            0.0,
        )
    if p >= policy.reduce_stockout_probability and ad_demand > 0:
        # Largest daily demand that keeps P(stockout) at the reduce threshold.
        z = float(stats.norm.ppf(1 - policy.reduce_stockout_probability))
        sigma = math.sqrt(days * sd**2 + demand**2 * lead_sd**2)
        sustainable = max(0.0, (available - z * sigma) / days)
        scale = float(np.clip((sustainable - organic) / ad_demand, 0.0, 1.0))
        if scale >= 1.0:
            # On the threshold itself the full budget is still sustainable: a
            # "REDUCE" that reduces nothing would be a changeset with no change.
            return out(DECISION_KEEP, f"P(stockout) = {p:.0%}: at threshold, full budget sustainable", budget, 1.0)
        if scale < policy.min_budget_scale:
            return out(
                DECISION_PAUSE,
                f"P(stockout) = {p:.0%}; sustainable budget below {policy.min_budget_scale:.0%} of current",
                0.0,
                0.0,
            )
        return out(
            DECISION_REDUCE,
            f"P(stockout) = {p:.0%} >= reduce threshold; budget scaled to {scale:.0%}",
            budget * scale,
            scale,
        )
    return out(DECISION_KEEP, f"P(stockout) = {p:.0%}: stock covers the protection interval", budget, 1.0)


# ------------------------------------------------------- capacity interlock


def dispatch_capacity(capacity: pd.DataFrame, n_pickers: int, shift_hours: float) -> dict:
    """Orders/day the DC can ship at the staffed level, from the staffing sweep."""
    need = {"n_pickers", "throughput_per_h", "picker_util"}
    if need - set(capacity.columns):
        raise ValueError(f"capacity file missing columns: {sorted(need - set(capacity.columns))}")
    row = capacity.loc[capacity["n_pickers"] == n_pickers]
    if row.empty:
        raise ValueError(f"no staffing row for n_pickers={n_pickers}; available: {sorted(capacity['n_pickers'])}")
    r = row.iloc[0]
    return {
        "n_pickers": int(n_pickers),
        "shift_hours": float(shift_hours),
        "orders_per_day": round(float(r["throughput_per_h"]) * shift_hours, 1),
        "picker_utilization": float(r["picker_util"]),
    }


# --------------------------------------------------------------- changesets


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_changeset(
    decision: SkuDecision,
    snapshot_date: str,
    guard: IthildinGuard,
    now: datetime | None = None,
    ttl_seconds: int = CHANGESET_TTL_SECONDS,
) -> Changeset:
    """Signed, expiring, reversible budget change for one PAUSE/REDUCE decision."""
    if decision.decision not in (DECISION_PAUSE, DECISION_REDUCE):
        raise ValueError(f"no changeset for decision {decision.decision}")
    now = now or _now()
    expires = (now + timedelta(seconds=ttl_seconds)).isoformat()
    key_src = f"{snapshot_date}|{decision.channel}|{decision.campaign_id}|{decision.decision}|{decision.new_budget_usd}"
    action = StagingAction(
        action_id=f"lrg-{decision.channel}-{decision.campaign_id}-{decision.decision.lower()}",
        risk_level=RiskLevel.REVERSIBLE,
        target_system=decision.channel,
        payload={
            "op": "set_daily_budget",
            "campaign_id": decision.campaign_id,
            "sku_id": decision.sku_id,
            "daily_budget_usd": decision.new_budget_usd,
            "previous_daily_budget_usd": decision.current_budget_usd,
            "stockout_probability": decision.stockout_probability,
            "reason": decision.reason,
            "snapshot_date": snapshot_date,
            # Inside the signed payload: editing the expiry breaks the signature.
            "expires_at_utc": expires,
        },
        idempotency_key=hashlib.sha256(key_src.encode("utf-8")).hexdigest(),
        timestamp_utc=now.isoformat(),
        rollback_plan={
            "op": "set_daily_budget",
            "campaign_id": decision.campaign_id,
            "daily_budget_usd": decision.current_budget_usd,
        },
    )
    return Changeset(action=action, token=guard.sign_action(action), expires_at_utc=expires)


def authorize_changeset(changeset: Changeset, guard: IthildinGuard, now: datetime | None = None) -> StagingVerdict:
    """TTL check, then the Ithildin guard (signature, idempotency, rollback).

    The expiry is read from the signed payload, never from the envelope, so a
    tampered envelope cannot extend the window.
    """
    now = now or _now()
    signed_expiry = datetime.fromisoformat(str(changeset.action.payload.get("expires_at_utc")))
    if now > signed_expiry:
        return StagingVerdict(
            approved=False,
            code=CODE_EXPIRED_TTL,
            reason=(
                f"approval window of {CHANGESET_TTL_SECONDS}s elapsed at {signed_expiry.isoformat()}: "
                "stock position has drifted, re-run the gate"
            ),
            audit_hash=hashlib.sha256(changeset.action.canonical_bytes()).hexdigest(),
            evaluated_at_utc=now.isoformat(),
        )
    return guard.evaluate_and_commit(changeset.action, changeset.token)


# ------------------------------------------------------------------- runner


def run_gate(
    snapshot: pd.DataFrame,
    capacity: pd.DataFrame,
    guard: IthildinGuard,
    n_pickers: int,
    shift_hours: float,
    policy: GatePolicy | None = None,
    now: datetime | None = None,
) -> dict:
    policy = policy or GatePolicy()
    missing = set(SNAPSHOT_COLUMNS) - set(snapshot.columns)
    if missing:
        raise ValueError(f"snapshot missing columns: {sorted(missing)}")
    if snapshot.empty:
        raise ValueError("snapshot is empty")
    dates = snapshot["snapshot_date"].dropna().unique()
    if len(dates) != 1:
        raise ValueError(f"snapshot must cover exactly one date, found {list(dates)}")
    snapshot_date = str(dates[0])

    decisions = [decide_sku(row, policy) for _, row in snapshot.iterrows()]
    changesets = [
        build_changeset(d, snapshot_date, guard, now=now)
        for d in decisions
        if d.decision in (DECISION_PAUSE, DECISION_REDUCE)
    ]

    cap = dispatch_capacity(capacity, n_pickers, shift_hours)
    held = [d for d in decisions if d.decision == DECISION_HOLD]
    projected_units = sum(d.projected_daily_demand_units or 0.0 for d in decisions if d.decision != DECISION_HOLD)
    projected_orders = projected_units / policy.units_per_order
    capacity_breach = projected_orders > cap["orders_per_day"]
    util_breach = cap["picker_utilization"] > policy.max_picker_utilization

    if capacity_breach or util_breach:
        run_outcome = RUN_ESCALATED
    elif held:
        run_outcome = RUN_HANDOFF
    else:
        run_outcome = RUN_STAGED

    def spend(pred) -> float:
        return round(sum(d.current_budget_usd or 0.0 for d in decisions if pred(d)), 2)

    oos_spend = spend(lambda d: d.available_units is not None and d.available_units <= 0)
    paused_spend = spend(lambda d: d.decision == DECISION_PAUSE)
    reduced_saving = round(
        sum((d.current_budget_usd or 0) - (d.new_budget_usd or 0) for d in decisions if d.decision == DECISION_REDUCE),
        2,
    )
    counts = {k: sum(d.decision == k for d in decisions) for k in (DECISION_KEEP, DECISION_REDUCE, DECISION_PAUSE, DECISION_HOLD)}

    return {
        "snapshot_date": snapshot_date,
        "run_outcome": run_outcome,
        "requires_human_signoff": True,
        "decision_counts": counts,
        "ad_spend_on_oos_usd_per_day": oos_spend,
        "ad_spend_paused_usd_per_day": paused_spend,
        "ad_spend_reduced_usd_per_day": reduced_saving,
        "dispatch_capacity": cap,
        "projected_orders_per_day": round(projected_orders, 1),
        "capacity_breach": bool(capacity_breach),
        "utilization_breach": bool(util_breach),
        "held_for_review": [asdict(d) for d in held],
        "decisions": [asdict(d) for d in decisions],
        "changesets": changesets,
    }


# ---------------------------------------------------------- synthetic data


def synthesize_snapshot(seed: int = 7, n_skus: int = 40, snapshot_date: str = "2026-03-02") -> pd.DataFrame:
    """SYNTHETIC inventory + campaign snapshot for demonstrating the gate.

    Deliberately mixes healthy SKUs, out-of-stock SKUs, SKUs that will run out
    before replenishment, SKUs rescued by a scheduled receipt, and one row with
    a missing stock count. Not client data.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_skus):
        demand = round(float(rng.gamma(2.0, 6.0)), 2)
        lead = int(rng.choice([3, 5, 7, 10, 14]))
        cover_days = float(rng.choice([0.0, 2.0, 5.0, 9.0, 15.0, 25.0, 40.0], p=[0.1, 0.12, 0.13, 0.15, 0.15, 0.2, 0.15]))
        on_hand = float(round(demand * cover_days))
        rows.append(
            {
                "snapshot_date": snapshot_date,
                "sku_id": f"S{i + 1:05d}",
                "on_hand_units": on_hand,
                "allocated_units": float(round(on_hand * float(rng.uniform(0.0, 0.15)))),
                "daily_demand_units": demand,
                "demand_sd_units": round(demand * float(rng.uniform(0.2, 0.6)), 2),
                "replenishment_lead_time_days": lead,
                "lead_time_sd_days": round(lead * float(rng.uniform(0.1, 0.35)), 2),
                "next_receipt_in_days": float(rng.integers(1, lead)) if rng.random() < 0.3 else np.nan,
                "channel": "google_ads" if i % 2 == 0 else "meta",
                "campaign_id": f"CMP-{1000 + i}",
                "daily_budget_usd": round(float(rng.uniform(15, 220)), 2),
                "ad_driven_demand_share": round(float(rng.uniform(0.2, 0.7)), 2),
                "data_provenance": "SYNTHETIC",
            }
        )
    df = pd.DataFrame(rows)
    df.loc[n_skus // 2, "on_hand_units"] = np.nan  # an uncounted location
    return df


# --------------------------------------------------------------------- CLI


def _guard_from_env() -> IthildinGuard:
    key = os.environ.get(HMAC_KEY_ENV)
    if not key:
        raise SystemExit(f"{HMAC_KEY_ENV} is not set: refusing to sign changesets with a default key")
    return IthildinGuard(key.encode("utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Interlock ad budgets with stock and dispatch capacity")
    ap.add_argument("--snapshot", type=Path, default=Path("examples/launch_gate/inventory_ads_snapshot.csv"))
    ap.add_argument("--capacity", type=Path, default=Path("out/dimensionamiento.csv"))
    ap.add_argument("--pickers", type=int, required=True)
    ap.add_argument("--shift-hours", type=float, default=16.0)
    ap.add_argument("--out-dir", type=Path, default=Path("out"))
    ap.add_argument("--write-synthetic", type=Path, help="write the synthetic snapshot to this path and exit")
    args = ap.parse_args(argv)

    if args.write_synthetic:
        args.write_synthetic.parent.mkdir(parents=True, exist_ok=True)
        synthesize_snapshot().to_csv(args.write_synthetic, index=False)
        print(f"SYNTHETIC snapshot written to {args.write_synthetic}")
        return 0

    guard = _guard_from_env()
    report = run_gate(pd.read_csv(args.snapshot), pd.read_csv(args.capacity), guard, args.pickers, args.shift_hours)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "launch_gate_changesets.jsonl").open("w", encoding="utf-8") as fh:
        for cs in report["changesets"]:
            fh.write(json.dumps(cs.to_json(), default=str) + "\n")
    summary = {k: v for k, v in report.items() if k != "changesets"}
    summary["n_changesets"] = len(report["changesets"])
    (args.out_dir / "launch_gate_report.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(f"run outcome: {report['run_outcome']} (human sign-off required before writeback)")
    print(f"decisions: {report['decision_counts']}")
    print(f"ad spend on out-of-stock SKUs: USD {report['ad_spend_on_oos_usd_per_day']:,.2f}/day")
    print(f"paused: USD {report['ad_spend_paused_usd_per_day']:,.2f}/day; reduced: USD {report['ad_spend_reduced_usd_per_day']:,.2f}/day")
    print(
        f"projected {report['projected_orders_per_day']} orders/day vs capacity "
        f"{report['dispatch_capacity']['orders_per_day']} ({'BREACH' if report['capacity_breach'] else 'ok'})"
    )
    print(f"{len(report['changesets'])} signed changesets (TTL {CHANGESET_TTL_SECONDS}s) in {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
