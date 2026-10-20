"""Counterfactual causal pipeline: Difference-in-Differences with placebo leads (Pillar 7).

Builds on `fdekit.baseline` rather than replacing it. `diff_in_diff` and
`parallel_trends_check` stay the reference implementations; this module adds
the three things a client's finance team will ask for before signing:

1. **Inference clustered by group x day.** `baseline.diff_in_diff` treats
   every order as independent. Orders picked on the same day share that day's
   volume, staffing, and congestion, so they are not independent. Ignoring the
   correlation shrinks the standard error by roughly sqrt(orders per day) and
   turns day-to-day noise into "significance". The estimator here is OLS on
   y = b0 + b1*treat + b2*post + b3*treat*post, with CR1 cluster-robust
   variance and t critical values on G - 1 degrees of freedom.

2. **Placebo lead tests.** Re-run the DiD inside the pre-period, pretending
   the intervention started on each earlier day. A real effect cannot appear
   before the intervention, so a significant placebo means the
   groups were already diverging and the DiD is biased. The 0.05 level is
   Bonferroni-adjusted across the placebo family. A placebo needs at
   least two clusters per cell; with fewer, the test is reported as
   inconclusive, not as passed.

3. **Charts**: daily group means around the cutoff, and the daily
   treat - control gap with its within-day 95% interval.

The causal claim is SUPPORTED only when the clustered DiD has p < 0.01 AND
every placebo lead is testable with p above the adjusted level AND the
slope-based parallel trends check is conclusive and does not reject. Any failed placebo makes it NOT_SUPPORTED;
anything short of the full evidence makes it INCONCLUSIVE, with the reasons
listed.

Run:
    python -m fdekit.diff_in_diff_analysis --panel out/panel_experimento.csv --out-dir out
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

from fdekit.baseline import diff_in_diff, parallel_trends_check

CAUSAL_ALPHA = 0.01
PLACEBO_ALPHA = 0.05
MIN_CLUSTERS_PER_CELL = 2

CLAIM_SUPPORTED = "SUPPORTED"
CLAIM_NOT_SUPPORTED = "NOT_SUPPORTED"
CLAIM_INCONCLUSIVE = "INCONCLUSIVE"


def _validate(df: pd.DataFrame, value: str, group: str, period: str, time: str) -> pd.DataFrame:
    missing = {value, group, period, time} - set(df.columns)
    if missing:
        raise ValueError(f"panel missing columns: {sorted(missing)}")
    bad_groups = set(df[group].unique()) - {"treat", "control"}
    bad_periods = set(df[period].unique()) - {"pre", "post"}
    if bad_groups or bad_periods:
        raise ValueError(f"unexpected labels: group {sorted(bad_groups)}, period {sorted(bad_periods)}")
    d = df[[value, group, period, time]].copy()
    d[value] = pd.to_numeric(d[value], errors="coerce")
    d[time] = pd.to_datetime(d[time])
    n_bad = int(d[value].isna().sum())
    if n_bad:
        raise ValueError(f"{n_bad} non-numeric or missing values in '{value}': clean them explicitly first")
    return d


def cluster_robust_did(
    df: pd.DataFrame,
    value: str,
    treat: pd.Series,
    post: pd.Series,
    clusters: pd.Series,
) -> dict:
    """OLS DiD with CR1 cluster-robust SE. `treat`/`post` are boolean Series."""
    y = df[value].to_numpy(dtype=float)
    t = treat.to_numpy(dtype=float)
    p = post.to_numpy(dtype=float)
    X = np.column_stack([np.ones_like(y), t, p, t * p])

    cells = pd.DataFrame({"t": t, "p": p, "c": clusters.to_numpy()})
    per_cell = cells.groupby(["t", "p"])["c"].nunique()
    if len(per_cell) < 4:
        raise ValueError("DiD needs all four treat x period cells populated")
    min_cell = int(per_cell.min())

    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta

    codes, _ = pd.factorize(clusters)
    G = int(codes.max()) + 1
    n, k = X.shape
    scores = np.zeros((G, k))
    np.add.at(scores, codes, X * resid[:, None])
    meat = scores.T @ scores
    correction = (G / (G - 1)) * ((n - 1) / (n - k)) if G > 1 else float("nan")
    V = correction * xtx_inv @ meat @ xtx_inv
    se = float(np.sqrt(V[3, 3])) if np.isfinite(V[3, 3]) and V[3, 3] > 0 else float("nan")

    dof = G - 1
    testable = bool(min_cell >= MIN_CLUSTERS_PER_CELL and dof > 0 and np.isfinite(se) and se > 0)
    est = float(beta[3])
    if testable:
        tstat = est / se
        pval = float(2 * stats.t.sf(abs(tstat), dof))
        crit = float(stats.t.ppf(0.975, dof))
        ci = (round(est - crit * se, 3), round(est + crit * se, 3))
    else:
        tstat, pval, ci = float("nan"), None, (None, None)

    return {
        "did_estimate": round(est, 3),
        "se_cluster": round(se, 3) if np.isfinite(se) else None,
        "t_stat": round(tstat, 3) if testable else None,
        "dof": dof,
        "n_clusters": G,
        "min_clusters_per_cell": min_cell,
        "p_value": float(f"{pval:.3g}") if pval is not None else None,
        "ci95_low": ci[0],
        "ci95_high": ci[1],
        "testable": testable,
    }


def _clusters(d: pd.DataFrame, group: str, time: str) -> pd.Series:
    return d[group].astype(str) + "|" + d[time].dt.strftime("%Y-%m-%d")


def placebo_leads(d: pd.DataFrame, value: str, group: str, time: str, cutoff: pd.Timestamp) -> list[dict]:
    """DiD inside the pre-period, faking the intervention at every pre day that
    leaves at least MIN_CLUSTERS_PER_CELL days on each side. Returns [] when the
    pre-period is too short for any such cutoff."""
    pre = d[d[time] < cutoff]
    days = sorted(pre[time].dt.normalize().unique())
    out = []
    for fake in days[MIN_CLUSTERS_PER_CELL : len(days) - MIN_CLUSTERS_PER_CELL + 1]:
        fake = pd.Timestamp(fake)
        res = cluster_robust_did(
            pre, value, pre[group] == "treat", pre[time] >= fake, _clusters(pre, group, time)
        )
        res["fake_cutoff"] = fake.strftime("%Y-%m-%d")
        out.append(res)
    # Bonferroni over the placebo family: with m leads at 0.05 each, a clean
    # design fails at least one by chance far more often than 5% of the time.
    alpha_adj = PLACEBO_ALPHA / len(out) if out else PLACEBO_ALPHA
    for res in out:
        res["alpha_adjusted"] = round(alpha_adj, 5)
        res["passes"] = bool(res["testable"] and res["p_value"] > alpha_adj)
    return out


def daily_gap(d: pd.DataFrame, value: str, group: str, time: str) -> pd.DataFrame:
    """Daily treat - control gap in means, with a within-day 95% interval."""
    g = d.groupby([d[time].dt.normalize(), group])[value].agg(["mean", "var", "size"]).unstack(group)
    gap = g[("mean", "treat")] - g[("mean", "control")]
    se = np.sqrt(g[("var", "treat")] / g[("size", "treat")] + g[("var", "control")] / g[("size", "control")])
    return pd.DataFrame(
        {
            "mean_treat": g[("mean", "treat")],
            "mean_control": g[("mean", "control")],
            "gap": gap,
            "gap_ci_low": gap - 1.96 * se,
            "gap_ci_high": gap + 1.96 * se,
        }
    )


def analyze(
    df: pd.DataFrame,
    value: str = "cycle_min",
    group: str = "group",
    period: str = "period",
    time: str = "day",
) -> dict:
    d = _validate(df, value, group, period, time)
    post_times = d.loc[d[period] == "post", time]
    pre_times = d.loc[d[period] == "pre", time]
    if post_times.empty or pre_times.empty:
        raise ValueError("panel needs both pre and post observations")
    cutoff = post_times.min().normalize()
    if pre_times.max() >= cutoff:
        raise ValueError("pre-period observations overlap the first post-period day")

    iid = diff_in_diff(d, value, group, period)
    clustered = cluster_robust_did(
        d, value, d[group] == "treat", d[period] == "post", _clusters(d, group, time)
    )
    placebos = placebo_leads(d, value, group, time, cutoff)
    trends = parallel_trends_check(d[d[period] == "pre"], value, group, time, cutoff)

    reasons: list[str] = []
    placebo_failed = any(p["testable"] and not p["passes"] for p in placebos)
    placebo_conclusive = bool(placebos) and all(p["testable"] for p in placebos)
    if placebo_failed:
        bad = [p["fake_cutoff"] for p in placebos if p["testable"] and not p["passes"]]
        reasons.append(f"placebo lead significant at fake cutoff(s) {bad}: groups diverged before treatment")
    if not placebo_conclusive:
        n_pre = d.loc[d[period] == "pre", time].dt.normalize().nunique()
        reasons.append(
            f"placebo leads not testable with {n_pre} pre-period day(s): each fake cell needs "
            f">= {MIN_CLUSTERS_PER_CELL} days, so the pre-period needs >= {2 * MIN_CLUSTERS_PER_CELL} days"
        )
    if trends.get("parallel_trends_ok") is False:
        reasons.append("slope-based parallel trends check rejects")
    elif not trends.get("conclusive", False):
        reasons.append("slope-based parallel trends check is inconclusive: " + str(trends.get("reason", "")))
    if not clustered["testable"]:
        reasons.append("clustered DiD not testable: fewer than 2 day-clusters in some cell")
    elif clustered["p_value"] >= CAUSAL_ALPHA:
        reasons.append(
            f"clustered DiD p = {clustered['p_value']} >= {CAUSAL_ALPHA}: effect not distinguishable "
            "from day-to-day variation"
        )
    if iid["p_value"] is not None and clustered["p_value"] is not None:
        if iid["p_value"] < CAUSAL_ALPHA <= clustered["p_value"]:
            reasons.append(
                f"order-level p = {iid['p_value']} looks significant only because it treats orders "
                "on the same day as independent"
            )

    if placebo_failed or trends.get("parallel_trends_ok") is False:
        claim = CLAIM_NOT_SUPPORTED
    elif (
        clustered["testable"]
        and clustered["p_value"] < CAUSAL_ALPHA
        and placebo_conclusive
        and trends.get("conclusive", False)
    ):
        claim = CLAIM_SUPPORTED
    else:
        claim = CLAIM_INCONCLUSIVE

    return {
        "metric": value,
        "cutoff": cutoff.strftime("%Y-%m-%d"),
        "causal_claim": claim,
        "reasons": reasons,
        "did_clustered": clustered,
        "did_order_level_iid": {k: iid[k] for k in ("did_estimate", "se", "p_value", "ci_low", "ci_high", "means")},
        "placebo_leads": placebos,
        "parallel_trends": trends,
        "thresholds": {"causal_alpha": CAUSAL_ALPHA, "placebo_alpha": PLACEBO_ALPHA},
        "_daily": daily_gap(d, value, group, time),
    }


def plot(result: dict, out_dir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    daily: pd.DataFrame = result["_daily"]
    cutoff = pd.Timestamp(result["cutoff"])
    c = result["did_clustered"]
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(daily.index, daily["mean_control"], "o-", color="#6b7280", label="Control")
    ax.plot(daily.index, daily["mean_treat"], "o-", color="#1d4ed8", label="Treated")
    ax.axvline(cutoff, color="#b91c1c", ls="--", lw=1, label="Intervention")
    ax.set_ylabel(f"Mean {result['metric']}")
    ax.set_title("Daily group means around the intervention")
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    p1 = out_dir / "did_group_means.png"
    fig.savefig(p1, dpi=200)
    plt.close(fig)
    paths.append(p1)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    pre = daily.index < cutoff
    for mask, color, lab in ((pre, "#6b7280", "Pre-period"), (~pre, "#1d4ed8", "Post-period")):
        sub = daily[mask]
        ax.errorbar(
            sub.index, sub["gap"],
            yerr=[sub["gap"] - sub["gap_ci_low"], sub["gap_ci_high"] - sub["gap"]],
            fmt="o", color=color, capsize=3, label=lab,
        )
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(cutoff, color="#b91c1c", ls="--", lw=1)
    p_txt = "n/a" if c["p_value"] is None else f"{c['p_value']:.3g}"
    ax.set_title(
        f"Treated - control gap by day\nDiD {c['did_estimate']:+.2f} "
        f"(clustered p = {p_txt}, G = {c['n_clusters']}) | causal claim: {result['causal_claim']}"
    )
    ax.set_ylabel(f"Gap in mean {result['metric']} (within-day 95% CI)")
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    p2 = out_dir / "did_event_study.png"
    fig.savefig(p2, dpi=200)
    plt.close(fig)
    paths.append(p2)
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Difference-in-Differences with clustered inference and placebo leads")
    ap.add_argument("--panel", type=Path, default=Path("out/panel_experimento.csv"))
    ap.add_argument("--value", default="cycle_min")
    ap.add_argument("--out-dir", type=Path, default=Path("out"))
    args = ap.parse_args(argv)

    result = analyze(pd.read_csv(args.panel), value=args.value)
    charts = plot(result, args.out_dir)
    report = {k: v for k, v in result.items() if not k.startswith("_")}
    report["charts"] = [str(p) for p in charts]
    (args.out_dir / "did_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    c, i = result["did_clustered"], result["did_order_level_iid"]
    print(f"causal claim: {result['causal_claim']}")
    print(f"DiD estimate: {c['did_estimate']:+.3f} {args.value}")
    print(f"  order-level (iid) p = {i['p_value']}   clustered by group x day p = {c['p_value']} (G = {c['n_clusters']})")
    for p in result["placebo_leads"]:
        print(f"  placebo lead at {p['fake_cutoff']}: testable={p['testable']} p={p['p_value']}")
    for r in result["reasons"]:
        print(f"  - {r}")
    print(f"report and charts written to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
