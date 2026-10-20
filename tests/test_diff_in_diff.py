"""Tests for the Difference-in-Differences pipeline with clustered inference and placebo leads.

Synthetic panels with a known ground truth are the only way to test a causal
estimator: the test knows the true effect, so it can check that the pipeline
finds it, does not invent one, and rejects a design whose pre-trends diverge.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from fdekit.diff_in_diff_analysis import (
    CLAIM_INCONCLUSIVE,
    CLAIM_NOT_SUPPORTED,
    CLAIM_SUPPORTED,
    analyze,
    cluster_robust_did,
    main,
    placebo_leads,
    plot,
)


def build_panel(
    *,
    effect: float = 0.0,
    n_pre: int = 12,
    n_post: int = 12,
    day_sd: float = 0.3,
    order_sd: float = 3.0,
    n_per_day: int = 150,
    pre_trend_gap_per_day: float = 0.0,
    seed: int = 1,
) -> pd.DataFrame:
    """Panel with known effect. Each group-day gets its own shock (day_sd)."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-01-05")
    rows = []
    for g in ("control", "treat"):
        for i in range(n_pre + n_post):
            post = i >= n_pre
            day = start + pd.Timedelta(days=i)
            mu = 50.0 + 0.2 * i + rng.normal(0, day_sd)
            if g == "treat":
                mu += 2.0
                if not post:
                    mu += pre_trend_gap_per_day * i
                else:
                    mu += pre_trend_gap_per_day * n_pre + effect
            vals = rng.normal(mu, order_sd, n_per_day)
            rows.extend((v, g, "post" if post else "pre", day.strftime("%Y-%m-%d")) for v in vals)
    return pd.DataFrame(rows, columns=["cycle_min", "group", "period", "day"])


# --------------------------------------------------------- estimator


def test_known_effect_is_recovered_and_supported():
    r = analyze(build_panel(effect=-5.0))
    c = r["did_clustered"]
    assert c["ci95_low"] <= -5.0 <= c["ci95_high"]
    assert c["p_value"] < 0.01
    assert all(p["passes"] for p in r["placebo_leads"])
    assert r["causal_claim"] == CLAIM_SUPPORTED, r["reasons"]


def test_no_effect_is_not_claimed():
    r = analyze(build_panel(effect=0.0, seed=4))
    assert r["did_clustered"]["p_value"] > 0.05
    assert r["causal_claim"] != CLAIM_SUPPORTED


def test_diverging_pre_trends_fail_the_placebo_and_block_the_claim():
    # A true effect exists, but the groups were already drifting apart.
    r = analyze(build_panel(effect=-5.0, pre_trend_gap_per_day=0.8))
    assert any(p["testable"] and not p["passes"] for p in r["placebo_leads"])
    assert r["causal_claim"] == CLAIM_NOT_SUPPORTED


def test_point_estimate_matches_baseline_diff_in_diff():
    r = analyze(build_panel(effect=-3.0))
    assert r["did_clustered"]["did_estimate"] == pytest.approx(r["did_order_level_iid"]["did_estimate"], abs=1e-3)


def test_day_shocks_inflate_clustered_se_above_iid_se():
    r = analyze(build_panel(effect=0.0, day_sd=4.0, seed=9))
    assert r["did_clustered"]["se_cluster"] > 3 * r["did_order_level_iid"]["se"]


def test_order_level_significance_from_day_noise_is_called_out():
    # Large day shocks, many orders per day: iid inference sees "significance"
    # in noise; the clustered test does not.
    panel = build_panel(effect=0.0, day_sd=6.0, n_pre=3, n_post=3, n_per_day=800, seed=2)
    r = analyze(panel)
    if r["did_order_level_iid"]["p_value"] < 0.01:
        assert r["did_clustered"]["p_value"] >= 0.01
        assert any("independent" in reason for reason in r["reasons"])
    assert r["causal_claim"] != CLAIM_SUPPORTED


# ------------------------------------------------------------ placebo


def test_three_pre_days_cannot_support_a_placebo_test():
    r = analyze(build_panel(effect=-5.0, n_pre=3, n_post=3))
    assert r["placebo_leads"] == []
    assert r["causal_claim"] == CLAIM_INCONCLUSIVE
    assert any("placebo leads not testable" in reason for reason in r["reasons"])


def test_placebo_cutoffs_leave_two_days_each_side():
    panel = build_panel(n_pre=6, n_post=2)
    d = panel.assign(day=pd.to_datetime(panel["day"]))
    leads = placebo_leads(d, "cycle_min", "group", "day", pd.Timestamp("2026-01-11"))
    assert [p["fake_cutoff"] for p in leads] == ["2026-01-07", "2026-01-08", "2026-01-09"]
    assert all(p["testable"] for p in leads)


def test_cluster_did_flags_single_cluster_cells_as_untestable():
    panel = build_panel(n_pre=1, n_post=1)
    d = panel.assign(day=pd.to_datetime(panel["day"]))
    res = cluster_robust_did(
        d, "cycle_min", d["group"] == "treat", d["period"] == "post", d["group"] + d["day"].astype(str)
    )
    assert res["testable"] is False
    assert res["p_value"] is None


# --------------------------------------------------------- validation


def test_missing_column_fails_loudly():
    with pytest.raises(ValueError, match="missing columns"):
        analyze(build_panel().drop(columns=["day"]))


def test_unexpected_labels_fail_loudly():
    panel = build_panel()
    panel.loc[0, "group"] = "pilot"
    with pytest.raises(ValueError, match="unexpected labels"):
        analyze(panel)


def test_non_numeric_metric_fails_loudly_instead_of_dropping_rows():
    panel = build_panel()
    panel["cycle_min"] = panel["cycle_min"].astype(object)
    panel.loc[0, "cycle_min"] = "n/a"
    with pytest.raises(ValueError, match="non-numeric"):
        analyze(panel)


def test_overlapping_pre_and_post_days_fail():
    panel = build_panel()
    panel.loc[panel.index[-1], "period"] = "pre"
    with pytest.raises(ValueError, match="overlap"):
        analyze(panel)


# ---------------------------------------------------- charts and CLI


def test_charts_are_written(tmp_path):
    paths = plot(analyze(build_panel(effect=-5.0)), tmp_path)
    assert [p.name for p in paths] == ["did_group_means.png", "did_event_study.png"]
    assert all(p.stat().st_size > 10_000 for p in paths)


def test_cli_on_demo_panel_refuses_an_unsupported_causal_claim(demo_out, tmp_path, capsys):
    rc = main(["--panel", str(demo_out / "panel_experimento.csv"), "--out-dir", str(tmp_path)])
    assert rc == 0
    report = json.loads((tmp_path / "did_report.json").read_text(encoding="utf-8"))
    # The demo panel has 3 pre-period days: no placebo is testable, so no
    # causal claim can be supported regardless of the point estimate.
    assert report["placebo_leads"] == []
    assert report["causal_claim"] != CLAIM_SUPPORTED
    assert (tmp_path / "did_event_study.png").exists()
    assert "causal claim" in capsys.readouterr().out
