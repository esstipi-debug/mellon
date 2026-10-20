"""Applied Information Economics for master-data cleaning (Pillar 3).

Decides, per master-data defect class, whether cleaning is worth its cost, and
how much it is worth paying to measure further before deciding. The method is
Douglas Hubbard's (How to Measure Anything): every uncertain input is a
calibrated 90% interval, a vectorized Monte Carlo propagates them to the net
value of the cleaning decision, and the Expected Opportunity Loss (EOL) of the
best decision is the Expected Value of Perfect Information (EVPI), the ceiling
on what any further measurement can be worth.

Inputs, both produced by `fdekit demo` or by a real site audit:

    event_log.csv           5-column process contract. Incident frequency is
                            counted from the exception activities each defect
                            class plausibly causes (DEFECT_INCIDENT_MAP).
    auditoria_maestros.csv  physical audit of a master-data sample. Defect rate
                            per class comes from here, as a Beta posterior.

What is data and what is assumption is kept separate on purpose. Defect rates
and incident counts come from the files. Cost per incident, attributable share,
fix cost, and cleaning effectiveness are NOT in the files; they are explicit
90% intervals in `DefectEconomics`, to be replaced with client-calibrated
ranges. The defaults are illustrative and labeled as such in every report.

Why attribution is an input and not estimated: linking an exception event to a
SKU needs order lines or a unique location -> SKU map. The generated master has
non-unique `home_location`, so that link is ambiguous, and estimating the
attributable fraction from an ambiguous join would launder a guess into a
number. `fdekit.dataquality.link_defects_to_rework` does it properly when
order lines exist.

Loud degradation: a defect class with no corroborating activity in the event
log gets verdict INDETERMINATE and `None` values. It is never reported as
zero loss, because absence of a signal in this log is not absence of loss.

Run:
    python -m fdekit.hubbard_evi_calculator \
        --event-log out/event_log.csv --audit out/auditoria_maestros.csv \
        --n-master-skus 1800 --out out/evi_report.json
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

# A 90% interval of a normal spans +-1.645 sigma, so 3.29 sigma in total.
_Z90_SPAN = 3.29

# Exception activities each defect class plausibly causes. An empty tuple means
# the 5-column log carries no signal for that class.
DEFECT_INCIDENT_MAP: Mapping[str, tuple[str, ...]] = {
    "location_mismatch": ("PICK_EXCEPTION_LOCATION",),
    "dim_out_of_tol": ("CARTON_REWORK", "REPACK"),
    "weight_out_of_tol": (),
}

# Numeric error column used for the Rule of Five magnitude bracket.
DEFECT_MAGNITUDE_COLUMN: Mapping[str, str | None] = {
    "location_mismatch": None,
    "dim_out_of_tol": "cube_err_pct",
    "weight_out_of_tol": "weight_kg_err_pct",
}

# Below this many observed operating days, the incident rate is extrapolated
# from too little history to capture day-to-day variance.
MIN_OBSERVATION_DAYS = 5

# A decision is "contested" when the probability that cleaning pays sits
# between these bounds; only then can more measurement change the decision.
CONTESTED_BAND = (0.10, 0.90)

VERDICT_CLEAN = "CLEAN"
VERDICT_IGNORE = "IGNORE"
VERDICT_MEASURE_FIRST = "MEASURE_FIRST"
VERDICT_INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class Range90:
    """Calibrated 90% confidence interval for an uncertain input.

    `lognormal` suits strictly positive quantities with right skew (costs);
    `uniform` suits bounded shares in [0, 1].
    """

    lo: float
    hi: float
    dist: str = "lognormal"

    def __post_init__(self) -> None:
        if self.hi < self.lo:
            raise ValueError(f"Range90 upper bound {self.hi} below lower bound {self.lo}")
        if self.dist not in ("lognormal", "uniform"):
            raise ValueError(f"unsupported distribution: {self.dist}")
        if self.dist == "lognormal" and self.lo <= 0:
            raise ValueError("lognormal Range90 requires lo > 0")
        if self.dist == "uniform" and not (0.0 <= self.lo and self.hi <= 1.0):
            raise ValueError("uniform Range90 is reserved for shares in [0, 1]")

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        if self.lo == self.hi:
            return np.full(n, float(self.lo))
        if self.dist == "uniform":
            return rng.uniform(self.lo, self.hi, n)
        mu = (math.log(self.lo) + math.log(self.hi)) / 2
        sigma = (math.log(self.hi) - math.log(self.lo)) / _Z90_SPAN
        return rng.lognormal(mu, sigma, n)


@dataclass(frozen=True)
class DefectEconomics:
    """Uncertain economics of one defect class. All money in USD."""

    cost_per_incident_usd: Range90
    attributable_share: Range90
    fix_cost_per_defective_sku_usd: Range90
    inspect_cost_per_sku_usd: Range90
    cleaning_effectiveness: Range90


# ILLUSTRATIVE DEFAULTS. Replace with ranges calibrated with the client's
# operations and finance leads before any number leaves the building.
DEFAULT_ECONOMICS: Mapping[str, DefectEconomics] = {
    "location_mismatch": DefectEconomics(
        cost_per_incident_usd=Range90(4.0, 15.0),
        attributable_share=Range90(0.50, 0.90, "uniform"),
        fix_cost_per_defective_sku_usd=Range90(3.0, 8.0),
        inspect_cost_per_sku_usd=Range90(0.40, 1.20),
        cleaning_effectiveness=Range90(0.70, 0.95, "uniform"),
    ),
    "dim_out_of_tol": DefectEconomics(
        cost_per_incident_usd=Range90(2.0, 9.0),
        attributable_share=Range90(0.30, 0.80, "uniform"),
        fix_cost_per_defective_sku_usd=Range90(4.0, 12.0),
        inspect_cost_per_sku_usd=Range90(0.80, 2.00),
        cleaning_effectiveness=Range90(0.60, 0.90, "uniform"),
    ),
    "weight_out_of_tol": DefectEconomics(
        cost_per_incident_usd=Range90(1.0, 20.0),
        attributable_share=Range90(0.10, 0.60, "uniform"),
        fix_cost_per_defective_sku_usd=Range90(2.0, 6.0),
        inspect_cost_per_sku_usd=Range90(0.50, 1.50),
        cleaning_effectiveness=Range90(0.60, 0.90, "uniform"),
    ),
}


@dataclass(frozen=True)
class EVIConfig:
    n_master_skus: int
    operating_days_per_year: int = 300
    horizon_years: float = 1.0
    further_measurement_cost_usd: float = 2_000.0
    n_draws: int = 100_000
    seed: int = 7
    economics: Mapping[str, DefectEconomics] = field(default_factory=lambda: dict(DEFAULT_ECONOMICS))
    assumptions_label: str = "ILLUSTRATIVE DEFAULTS - not client-calibrated"

    def __post_init__(self) -> None:
        if self.n_master_skus <= 0:
            raise ValueError("n_master_skus must be positive")
        if self.operating_days_per_year <= 0 or self.horizon_years <= 0:
            raise ValueError("operating_days_per_year and horizon_years must be positive")
        if self.n_draws < 1_000:
            raise ValueError("n_draws below 1000 gives unstable tail estimates")


def median_bracket_confidence(n: int) -> float:
    """Probability that the population median lies between the min and max of
    `n` random draws. For n = 5 this is Hubbard's Rule of Five: 93.75%."""
    if n < 2:
        raise ValueError("need at least 2 observations to bracket a median")
    return 1.0 - 2.0 * 0.5**n


def rule_of_five(values: Sequence[float] | pd.Series, rng: np.random.Generator, n: int = 5) -> dict | None:
    """Bracket the median of `values` from `n` random draws without replacement.

    Returns None (not an empty bracket) when there are fewer than `n` values.
    """
    arr = pd.Series(values, dtype=float).dropna().to_numpy()
    if arr.size < n:
        return None
    draw = rng.choice(arr, size=n, replace=False)
    return {
        "n_draws": n,
        "bracket_low": round(float(draw.min()), 3),
        "bracket_high": round(float(draw.max()), 3),
        "confidence": median_bracket_confidence(n),
        "full_sample_median": round(float(np.median(arr)), 3),
        "full_sample_n": int(arr.size),
    }


def observation_days(events: pd.DataFrame) -> int:
    ts = pd.to_datetime(events["timestamp"])
    return int(ts.dt.normalize().nunique())


def count_incidents(events: pd.DataFrame, activities: Sequence[str]) -> int:
    return int(events["activity"].isin(list(activities)).sum())


def _validate_inputs(events: pd.DataFrame, audit: pd.DataFrame, defects: Sequence[str]) -> None:
    missing_ev = {"case_id", "activity", "timestamp"} - set(events.columns)
    if missing_ev:
        raise ValueError(f"event log missing columns: {sorted(missing_ev)}")
    missing_au = {"sku_id", *defects} - set(audit.columns)
    if missing_au:
        raise ValueError(f"audit file missing columns: {sorted(missing_au)}")
    if audit.empty or events.empty:
        raise ValueError("event log and audit must both be non-empty")


def simulate_defect(
    *,
    n_audited: int,
    n_defective: int,
    incidents: int,
    exposure_days: int,
    econ: DefectEconomics,
    cfg: EVIConfig,
    rng: np.random.Generator,
) -> dict:
    """Vectorized Monte Carlo of the clean-vs-ignore decision for one defect class.

    net = annual benefit x horizon - one-time cleaning cost
    benefit = incident rate x attributable share x effectiveness x cost per incident
    cost = master size x inspect cost + master size x defect rate x fix cost
    """
    n = cfg.n_draws
    # Beta(1, 1) prior on the defect rate, updated with the audit sample.
    defect_rate = rng.beta(1 + n_defective, 1 + n_audited - n_defective, n)
    # Jeffreys Gamma posterior on a Poisson incident rate per operating day.
    rate_per_day = rng.gamma(incidents + 0.5, 1.0 / exposure_days, n)

    annual_benefit = (
        rate_per_day
        * cfg.operating_days_per_year
        * econ.attributable_share.sample(rng, n)
        * econ.cleaning_effectiveness.sample(rng, n)
        * econ.cost_per_incident_usd.sample(rng, n)
    )
    cleaning_cost = cfg.n_master_skus * (
        econ.inspect_cost_per_sku_usd.sample(rng, n)
        + defect_rate * econ.fix_cost_per_defective_sku_usd.sample(rng, n)
    )
    net = annual_benefit * cfg.horizon_years - cleaning_cost

    eol_clean = float(np.maximum(-net, 0.0).mean())
    eol_ignore = float(np.maximum(net, 0.0).mean())
    expected_net = float(net.mean())
    choose_clean = expected_net > 0
    evpi = eol_clean if choose_clean else eol_ignore
    p_pays = float((net > 0).mean())
    p5, p50, p95 = np.percentile(net, [5, 50, 95])

    contested = CONTESTED_BAND[0] < p_pays < CONTESTED_BAND[1]
    if contested and evpi > cfg.further_measurement_cost_usd:
        verdict = VERDICT_MEASURE_FIRST
        reason = (
            f"decision is contested (P(cleaning pays) = {p_pays:.0%}) and perfect information "
            f"is worth USD {evpi:,.0f}, above the USD {cfg.further_measurement_cost_usd:,.0f} "
            "cost of measuring further: measure the widest input before committing"
        )
    elif choose_clean:
        verdict = VERDICT_CLEAN
        reason = f"expected net USD {expected_net:,.0f} over the horizon; P(cleaning pays) = {p_pays:.0%}"
    else:
        verdict = VERDICT_IGNORE
        reason = (
            f"expected net USD {expected_net:,.0f}: cleaning costs more than it recovers; "
            f"P(cleaning pays) = {p_pays:.0%}"
        )

    return {
        "verdict": verdict,
        "reason": reason,
        "defect_rate_mean": round(float(defect_rate.mean()), 4),
        "incidents_per_operating_day_mean": round(float(rate_per_day.mean()), 2),
        "annual_benefit_usd_mean": round(float(annual_benefit.mean()), 0),
        "cleaning_cost_usd_mean": round(float(cleaning_cost.mean()), 0),
        "expected_net_usd": round(expected_net, 0),
        "net_usd_p5": round(float(p5), 0),
        "net_usd_p50": round(float(p50), 0),
        "net_usd_p95": round(float(p95), 0),
        "p_cleaning_pays": round(p_pays, 4),
        "eol_if_clean_usd": round(eol_clean, 0),
        "eol_if_ignore_usd": round(eol_ignore, 0),
        "evpi_usd": round(evpi, 0),
    }


def _indeterminate(defect: str, n_audited: int, n_defective: int) -> dict:
    return {
        "verdict": VERDICT_INDETERMINATE,
        "reason": (
            f"no activity in the event log is mapped to '{defect}', so its loss frequency "
            "is unmeasured. This is NOT zero loss: measure the loss directly (e.g., carrier "
            "weight-discrepancy claims) before deciding."
        ),
        "defect_rate_mean": round((1 + n_defective) / (2 + n_audited), 4),
        "incidents_per_operating_day_mean": None,
        "annual_benefit_usd_mean": None,
        "cleaning_cost_usd_mean": None,
        "expected_net_usd": None,
        "net_usd_p5": None,
        "net_usd_p50": None,
        "net_usd_p95": None,
        "p_cleaning_pays": None,
        "eol_if_clean_usd": None,
        "eol_if_ignore_usd": None,
        "evpi_usd": None,
    }


def evaluate(
    events: pd.DataFrame,
    audit: pd.DataFrame,
    cfg: EVIConfig,
    incident_map: Mapping[str, Sequence[str]] = DEFECT_INCIDENT_MAP,
) -> dict:
    """Run the EVI analysis for every defect class in `incident_map`."""
    defects = list(incident_map)
    _validate_inputs(events, audit, defects)
    missing_econ = set(defects) - set(cfg.economics)
    if missing_econ:
        raise ValueError(f"no economics configured for: {sorted(missing_econ)}")

    rng = np.random.default_rng(cfg.seed)
    days = observation_days(events)
    warnings: list[str] = []
    if days < MIN_OBSERVATION_DAYS:
        warnings.append(
            f"incident rates extrapolated from {days} operating day(s) (< {MIN_OBSERVATION_DAYS}): "
            "day-to-day variance is not captured and the benefit interval is too narrow. "
            "Pull at least a week of task events before presenting the ranking."
        )

    results: dict[str, dict] = {}
    for defect in defects:
        flags = audit[defect].astype(bool)
        n_audited, n_defective = int(flags.size), int(flags.sum())
        activities = tuple(incident_map[defect])
        if activities:
            row = simulate_defect(
                n_audited=n_audited,
                n_defective=n_defective,
                incidents=count_incidents(events, activities),
                exposure_days=days,
                econ=cfg.economics[defect],
                cfg=cfg,
                rng=rng,
            )
        else:
            row = _indeterminate(defect, n_audited, n_defective)

        mag_col = DEFECT_MAGNITUDE_COLUMN.get(defect)
        if mag_col and mag_col in audit.columns:
            row["rule_of_five_magnitude"] = {
                "column": mag_col,
                **(rule_of_five(audit.loc[flags, mag_col], rng) or {"bracket": None}),
            }
        else:
            row["rule_of_five_magnitude"] = None
        row.update(
            n_audited=n_audited,
            n_defective=n_defective,
            incident_activities=list(activities),
        )
        results[defect] = row

    ranked = sorted(
        (d for d in results if results[d]["expected_net_usd"] is not None),
        key=lambda d: results[d]["expected_net_usd"],
        reverse=True,
    )
    return {
        "assumptions": cfg.assumptions_label,
        "n_master_skus": cfg.n_master_skus,
        "operating_days_per_year": cfg.operating_days_per_year,
        "horizon_years": cfg.horizon_years,
        "observation_days": days,
        "n_draws": cfg.n_draws,
        "seed": cfg.seed,
        "warnings": warnings,
        "ranking_by_expected_net": ranked,
        "defects": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Hubbard EVI / EOL for master-data cleaning decisions")
    ap.add_argument("--event-log", type=Path, default=Path("out/event_log.csv"))
    ap.add_argument("--audit", type=Path, default=Path("out/auditoria_maestros.csv"))
    ap.add_argument("--n-master-skus", type=int, required=True, help="SKUs in the full item master")
    ap.add_argument("--operating-days", type=int, default=300)
    ap.add_argument("--horizon-years", type=float, default=1.0)
    ap.add_argument("--measurement-cost", type=float, default=2_000.0)
    ap.add_argument("--draws", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("out/evi_report.json"))
    args = ap.parse_args(argv)

    cfg = EVIConfig(
        n_master_skus=args.n_master_skus,
        operating_days_per_year=args.operating_days,
        horizon_years=args.horizon_years,
        further_measurement_cost_usd=args.measurement_cost,
        n_draws=args.draws,
        seed=args.seed,
    )
    report = evaluate(pd.read_csv(args.event_log), pd.read_csv(args.audit), cfg)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"assumptions: {report['assumptions']}")
    for w in report["warnings"]:
        print(f"WARNING: {w}")
    for defect, row in report["defects"].items():
        evpi = "None" if row["evpi_usd"] is None else f"USD {row['evpi_usd']:,.0f}"
        print(f"{defect:<20} {row['verdict']:<14} EVPI {evpi:<14} {row['reason']}")
    print(f"report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
