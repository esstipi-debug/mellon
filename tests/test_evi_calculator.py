"""Tests for the Hubbard EVI / EOL master-data cleaning calculator."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from fdekit.hubbard_evi_calculator import (
    VERDICT_CLEAN,
    VERDICT_IGNORE,
    VERDICT_INDETERMINATE,
    VERDICT_MEASURE_FIRST,
    DefectEconomics,
    EVIConfig,
    Range90,
    evaluate,
    main,
    median_bracket_confidence,
    rule_of_five,
    simulate_defect,
)


def _econ(cost_per_incident=(5.0, 10.0), fix=(4.0, 8.0), inspect=(0.5, 1.0)) -> DefectEconomics:
    return DefectEconomics(
        cost_per_incident_usd=Range90(*cost_per_incident),
        attributable_share=Range90(0.5, 0.8, "uniform"),
        fix_cost_per_defective_sku_usd=Range90(*fix),
        inspect_cost_per_sku_usd=Range90(*inspect),
        cleaning_effectiveness=Range90(0.7, 0.9, "uniform"),
    )


def _cfg(**kw) -> EVIConfig:
    base = dict(n_master_skus=1_000, n_draws=20_000, seed=11, further_measurement_cost_usd=500.0)
    base.update(kw)
    return EVIConfig(**base)


def _run(incidents: int, exposure_days: int = 20, cfg: EVIConfig | None = None, econ=None) -> dict:
    cfg = cfg or _cfg()
    return simulate_defect(
        n_audited=200,
        n_defective=20,
        incidents=incidents,
        exposure_days=exposure_days,
        econ=econ or _econ(),
        cfg=cfg,
        rng=np.random.default_rng(cfg.seed),
    )


# ---------------------------------------------------------------- Rule of Five


def test_rule_of_five_confidence_is_93_75_percent():
    assert median_bracket_confidence(5) == pytest.approx(0.9375)


def test_median_bracket_confidence_rejects_single_observation():
    with pytest.raises(ValueError):
        median_bracket_confidence(1)


def test_rule_of_five_bracket_covers_median_at_expected_rate():
    # Arrange: skewed population with known median.
    rng = np.random.default_rng(3)
    population = rng.lognormal(0.0, 1.0, 50_000)
    median = np.median(population)

    # Act: 2,000 independent Rule-of-Five brackets.
    hits = 0
    for _ in range(2_000):
        b = rule_of_five(population, rng)
        hits += b["bracket_low"] <= median <= b["bracket_high"]

    # Assert: empirical coverage near the theoretical 93.75%.
    assert hits / 2_000 == pytest.approx(0.9375, abs=0.02)


def test_rule_of_five_returns_none_when_sample_too_small():
    assert rule_of_five([1.0, 2.0, 3.0], np.random.default_rng(0)) is None


# --------------------------------------------------------------- Range90


def test_range90_lognormal_reproduces_its_90_percent_interval():
    draws = Range90(10.0, 100.0).sample(np.random.default_rng(0), 200_000)
    p5, p95 = np.percentile(draws, [5, 95])
    assert p5 == pytest.approx(10.0, rel=0.03)
    assert p95 == pytest.approx(100.0, rel=0.03)


@pytest.mark.parametrize(
    "args",
    [(5.0, 1.0), (0.0, 1.0), (0.2, 1.5, "uniform"), (1.0, 2.0, "triangular")],
)
def test_range90_rejects_invalid_specs(args):
    with pytest.raises(ValueError):
        Range90(*args)


# ------------------------------------------------------------ decisions


def test_frequent_costly_incidents_justify_cleaning():
    r = _run(incidents=2_000)
    assert r["verdict"] == VERDICT_CLEAN
    assert r["expected_net_usd"] > 0
    assert r["p_cleaning_pays"] > 0.9


def test_rare_incidents_do_not_justify_cleaning():
    r = _run(incidents=1)
    assert r["verdict"] == VERDICT_IGNORE
    assert r["expected_net_usd"] < 0


def test_contested_decision_with_valuable_information_says_measure_first():
    # Arrange: tune the incident count so expected benefit is near the cost,
    # with wide cost-per-incident uncertainty.
    econ = _econ(cost_per_incident=(0.5, 40.0))
    r = _run(incidents=600, econ=econ, cfg=_cfg(n_master_skus=10_000))

    assert 0.1 < r["p_cleaning_pays"] < 0.9
    assert r["evpi_usd"] > 500.0
    assert r["verdict"] == VERDICT_MEASURE_FIRST


def test_contested_decision_is_not_measured_when_measurement_costs_more_than_evpi():
    econ = _econ(cost_per_incident=(0.5, 40.0))
    cfg = _cfg(n_master_skus=10_000, further_measurement_cost_usd=1e9)
    r = _run(incidents=600, econ=econ, cfg=cfg)
    assert r["verdict"] in (VERDICT_CLEAN, VERDICT_IGNORE)


def test_evpi_equals_eol_of_the_chosen_action():
    r = _run(incidents=60, econ=_econ(cost_per_incident=(0.5, 40.0)))
    chosen = r["eol_if_clean_usd"] if r["expected_net_usd"] > 0 else r["eol_if_ignore_usd"]
    assert r["evpi_usd"] == chosen
    # The chosen action always has the lower expected opportunity loss.
    assert r["evpi_usd"] == min(r["eol_if_clean_usd"], r["eol_if_ignore_usd"])


def test_simulation_is_deterministic_for_a_seed():
    assert _run(incidents=300) == _run(incidents=300)


def test_net_percentiles_are_ordered():
    r = _run(incidents=300)
    assert r["net_usd_p5"] <= r["net_usd_p50"] <= r["net_usd_p95"]


# ---------------------------------------------------------- evaluate()


def _frames(n_days: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for d in range(n_days):
        day = pd.Timestamp("2026-03-02") + pd.Timedelta(days=d)
        for i in range(50):
            ts = day + pd.Timedelta(minutes=i)
            rows.append((f"O{d}{i}", "PICK", ts, "P1", "01-001-1"))
            if i % 5 == 0:
                rows.append((f"O{d}{i}", "PICK_EXCEPTION_LOCATION", ts, "P1", "01-001-1"))
    events = pd.DataFrame(rows, columns=["case_id", "activity", "timestamp", "resource", "location"])
    audit = pd.DataFrame(
        {
            "sku_id": [f"S{i}" for i in range(40)],
            "location_mismatch": [i % 4 == 0 for i in range(40)],
            "dim_out_of_tol": [i % 3 == 0 for i in range(40)],
            "weight_out_of_tol": [i % 5 == 0 for i in range(40)],
            "cube_err_pct": np.linspace(-20, 80, 40),
            "weight_kg_err_pct": np.linspace(0, 50, 40),
        }
    )
    return events, audit


def test_unmapped_defect_is_indeterminate_never_zero():
    events, audit = _frames()
    report = evaluate(events, audit, _cfg())
    w = report["defects"]["weight_out_of_tol"]
    assert w["verdict"] == VERDICT_INDETERMINATE
    assert w["expected_net_usd"] is None
    assert w["evpi_usd"] is None
    assert "weight_out_of_tol" not in report["ranking_by_expected_net"]


def test_mapped_defect_with_zero_incidents_is_computed_not_indeterminate():
    # dim_out_of_tol maps to CARTON_REWORK/REPACK, absent from these frames:
    # a measured zero is evidence, unlike an unmapped class.
    events, audit = _frames()
    d = evaluate(events, audit, _cfg())["defects"]["dim_out_of_tol"]
    assert d["verdict"] == VERDICT_IGNORE
    assert d["expected_net_usd"] < 0


def test_short_observation_window_raises_warning():
    events, audit = _frames(n_days=2)
    assert any("2 operating day" in w for w in evaluate(events, audit, _cfg())["warnings"])
    events, audit = _frames(n_days=6)
    assert evaluate(events, audit, _cfg())["warnings"] == []


def test_report_labels_assumptions_as_illustrative():
    events, audit = _frames()
    assert "ILLUSTRATIVE" in evaluate(events, audit, _cfg())["assumptions"]


def test_missing_columns_fail_loudly():
    events, audit = _frames()
    with pytest.raises(ValueError, match="audit file missing"):
        evaluate(events, audit.drop(columns=["dim_out_of_tol"]), _cfg())
    with pytest.raises(ValueError, match="event log missing"):
        evaluate(events.drop(columns=["timestamp"]), audit, _cfg())


def test_config_rejects_nonsense():
    with pytest.raises(ValueError):
        EVIConfig(n_master_skus=0)
    with pytest.raises(ValueError):
        EVIConfig(n_master_skus=10, n_draws=10)


# ------------------------------------------------------ real kit outputs


def test_cli_runs_on_demo_outputs(demo_out, tmp_path, capsys):
    out = tmp_path / "evi_report.json"
    rc = main(
        [
            "--event-log", str(demo_out / "event_log.csv"),
            "--audit", str(demo_out / "auditoria_maestros.csv"),
            "--n-master-skus", "1800",
            "--draws", "20000",
            "--out", str(out),
        ]
    )
    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert set(report["defects"]) == {"location_mismatch", "dim_out_of_tol", "weight_out_of_tol"}
    assert report["defects"]["weight_out_of_tol"]["verdict"] == VERDICT_INDETERMINATE
    # The demo log covers a single shift, so the extrapolation warning must fire.
    assert report["warnings"]
    assert "WARNING" in capsys.readouterr().out
