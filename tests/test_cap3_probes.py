"""Property and model-checking tests for Chapter 3 decoupled FSM and saturation frontier."""

import math
from hypothesis import given, settings, strategies as st
import pytest

from fdekit.sim.littles_law import mm_c_wait
from probes.cap3_delta_projection import (
    A,
    Config,
    D,
    E,
    MOVEMENTS,
    QuarantineBuffer,
    REACHABLE_STATES,
    Rejected,
    S,
    check_all,
    delta,
    initial_state,
)
from probes.quarantine_capacity import (
    classify,
    dock_saturation,
    floor_saturation,
    quarantine_load,
    saturation_frontier,
)


def test_mm_c_wait_converts_hourly_rates_to_real_seconds():
    # M/M/1 with lambda=1/h, mu=2/h -> rho=0.5, Wq = 0.5 h = 1800 s, W = 1.0 h = 3600 s.
    res = mm_c_wait(arrival_rate=1.0, service_rate=2.0, servers=1, rate_unit="per_hour")
    assert res["wq_native"] == pytest.approx(0.5)
    assert res["wq_s"] == pytest.approx(1800.0)
    assert res["w_total_s"] == pytest.approx(3600.0)
    res_sec = mm_c_wait(arrival_rate=1.0, service_rate=2.0, servers=1, rate_unit="per_second")
    assert res_sec["wq_s"] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        mm_c_wait(1.0, 2.0, 1, rate_unit="per_day")


def test_reachable_space_is_12_of_64_and_satisfies_all_invariants():
    assert len(S) * len(A) * len(D) == 64
    tuples_3d = {(c.s, c.a, c.d) for c in REACHABLE_STATES}
    assert len(REACHABLE_STATES) == 12
    assert len(tuples_3d) == 12
    for cfg in REACHABLE_STATES:
        assert check_all(cfg) == [], f"Invariant violated in {cfg}"


def test_delta_is_total_over_entire_512_cartesian_product():
    for s in S:
        for a in A:
            for d in D:
                cfg = Config(s=s, a=a, d=d, bwart=("103",) if a is not A.NONE else ())
                for ev in E:
                    out = delta(cfg, ev)
                    assert isinstance(out, (Config, Rejected))


def test_theorem_t2_carrier_departs_while_lot_remains_held_in_103():
    cfg = initial_state()
    for ev in (E.GATE_ARRIVE, E.WEIGH_OK, E.UNLOAD_START):
        out = delta(cfg, ev)
        assert isinstance(out, Config)
        cfg = out
    # Cannot depart mid-unloading
    assert isinstance(delta(cfg, E.DEPART), Rejected)

    # Discrepancy puts lot in HELD while keeping 103 active; truck can now depart
    held = delta(cfg, E.COUNT_FAIL)
    assert isinstance(held, Config) and held.s is S.HELD and held.a is A.BLOCKED_103
    departed = delta(held, E.DEPART)
    assert isinstance(departed, Config)
    assert departed.d is D.DEPARTED and departed.a is A.BLOCKED_103

    # Pre-105 vendor rejection issues 124 (not 122)
    returned = delta(departed, E.RESOLVE_RETURN)
    assert isinstance(returned, Config)
    assert returned.a is A.RETURNED_124
    assert returned.bwart == ("103", "124")
    assert "124" in MOVEMENTS and "122" in MOVEMENTS


def test_quarantine_buffer_imputes_overflow_without_dropping_lot():
    buf = QuarantineBuffer(capacity=1, occupants=[], overflow_events=[])
    ev1 = buf.admit("DELIV-01", "CC-QA", 1.0)
    assert ev1["kind"] == "ADMITTED"
    ev2 = buf.admit("DELIV-02", "CC-BUYER", 1.5)
    assert ev2["kind"] == "OVERFLOW_IMPUTED"
    assert ev2["excess"] == 1
    assert len(buf.overflow_events) == 1
    buf.release("DELIV-01")
    assert buf.load == 1


@settings(max_examples=200)
@given(
    docks=st.integers(min_value=1, max_value=12),
    mu=st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False),
    buf=st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    res_h=st.floats(min_value=1e-6, max_value=72.0, allow_nan=False, allow_infinity=False),
    ret=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_saturation_frontier_handles_all_floats_including_subnormals(docks, mu, buf, res_h, ret):
    f = saturation_frontier(docks, mu, buf, res_h, ret)
    assert f["lambda_governing"] <= dock_saturation(docks, mu) + 1e-12
    assert f["lambda_governing"] <= floor_saturation(buf, ret, res_h) + 1e-12
    # Explicit subnormal underflow check
    assert floor_saturation(buf, 5e-324, 0.5) == math.inf
    c = classify(lam=0.5 * f["lambda_governing"], docks=docks, service_rate_per_h=mu, buffer_positions=buf, resolution_h=res_h, retention_rate=ret)
    assert c["state"] == "OPERATIONAL"
    assert quarantine_load(10.0, 0.2, 4.0) == pytest.approx(8.0)
