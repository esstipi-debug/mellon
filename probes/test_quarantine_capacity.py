"""
Empirical and analytical validation of dock vs. quarantine floor saturation frontier (Little's Law).
16 formal unit tests covering Little's Law identity, Erlang C parity, monotonicity, and classification.
"""

from __future__ import annotations

import math
import unittest

from hypothesis import given, settings, strategies as st

try:
    from probes import quarantine_capacity as qc
except ImportError:
    import quarantine_capacity as qc


class TestRepositoryParity(unittest.TestCase):
    """Parity against fdekit.sim.littles_law.mm_c_wait module."""

    def test_mm_c_numeric_parity_with_mellon(self):
        from fdekit.sim.littles_law import mm_c_wait

        for lam, mu, c in [(4.0, 3.0, 2), (9.0, 2.5, 5), (0.5, 2.0, 1), (17.0, 6.0, 4)]:
            repo = mm_c_wait(lam, mu, c)
            mine = qc._erlang_c_wait(lam, mu, c)
            self.assertAlmostEqual(repo["rho"], mine["rho"], places=3)
            # Both calculate identical math; wq_native is in hours, wq_s in seconds
            self.assertAlmostEqual(repo.get("wq_native", repo["wq_s"] / 3600.0), mine["wq_h"], delta=0.05)
            self.assertAlmostEqual(repo["lq"], mine["lq"], delta=0.05)


class TestIdentities(unittest.TestCase):
    def test_floor_load_is_exact_little_identity(self):
        lam, r, R = 12.0, 0.25, 6.0
        self.assertAlmostEqual(qc.quarantine_load(lam, r, R), lam * r * R, places=12)

    def test_at_floor_ceiling_load_equals_buffer_capacity(self):
        V, r, R = 40.0, 0.30, 8.0
        lam_star = qc.floor_saturation(V, r, R)
        self.assertAlmostEqual(qc.quarantine_load(lam_star, r, R), V, places=9)

    def test_at_dock_ceiling_utilization_equals_target(self):
        c, mu, target = 4, 2.5, 0.85
        lam_star = qc.dock_saturation(c, mu, target)
        self.assertAlmostEqual(lam_star / (c * mu), target, places=12)

    def test_zero_retention_imposes_no_floor_ceiling(self):
        # retention_rate = 0.0: all units clear dock directly (105), none occupy floor
        self.assertEqual(qc.floor_saturation(10.0, 0.0, 5.0), math.inf)

    def test_rho_one_has_no_finite_expectation(self):
        q = qc._erlang_c_wait(10.0, 5.0, 2)  # rho = 1 exact
        self.assertFalse(q["stable"])
        self.assertEqual(q["wq_h"], math.inf)


class TestFrontier(unittest.TestCase):
    def test_critical_retention_r_star_equalizes_both_ceilings(self):
        c, mu, V, R, target = 6, 2.0, 90.0, 10.0, 0.85
        f = qc.saturation_frontier(c, mu, V, R, retention_rate=0.5, utilization_target=target)
        r_star = f["retention_critical"]
        self.assertGreater(r_star, 0.0)
        self.assertLess(r_star, 1.0)
        lam_dock = qc.dock_saturation(c, mu, target)
        lam_floor = qc.floor_saturation(V, r_star, R)
        self.assertAlmostEqual(lam_dock, lam_floor, places=6)

    def test_governing_constraint_is_minimum_of_both_ceilings(self):
        c, mu, V, R, target = 6, 2.0, 90.0, 10.0, 0.85
        for r in (0.05, 0.2, 0.5, 0.8, 0.95):
            f = qc.saturation_frontier(c, mu, V, R, r, target)
            self.assertAlmostEqual(
                f["lambda_governing"], min(f["lambda_dock_max"], f["lambda_floor_max"]), places=9
            )

    def test_deterministic(self):
        args = (5, 2.2, 60.0, 7.0, 0.4, 0.85)
        self.assertEqual(qc.saturation_frontier(*args), qc.saturation_frontier(*args))


class TestMonotonicity(unittest.TestCase):
    @settings(max_examples=300, deadline=None)
    @given(
        lam=st.floats(min_value=0.01, max_value=100.0),
        dlam=st.floats(min_value=0.01, max_value=10.0),
        r=st.floats(min_value=0.01, max_value=1.0),
        R=st.floats(min_value=0.5, max_value=48.0),
    )
    def test_load_is_strictly_increasing_in_lambda(self, lam, dlam, r, R):
        self.assertGreater(qc.quarantine_load(lam + dlam, r, R), qc.quarantine_load(lam, r, R))

    @settings(max_examples=300, deadline=None)
    @given(
        lam=st.floats(min_value=0.01, max_value=100.0),
        r1=st.floats(min_value=0.0, max_value=0.9),
        dr=st.floats(min_value=0.01, max_value=0.09),
        R=st.floats(min_value=0.5, max_value=48.0),
    )
    def test_load_is_strictly_increasing_in_retention(self, lam, r1, dr, R):
        self.assertGreater(qc.quarantine_load(lam, r1 + dr, R), qc.quarantine_load(lam, r1, R))

    @settings(max_examples=200, deadline=None)
    @given(
        c=st.integers(min_value=1, max_value=20),
        mu=st.floats(min_value=0.2, max_value=8.0),
        V=st.floats(min_value=1.0, max_value=500.0),
        R=st.floats(min_value=0.5, max_value=48.0),
        r=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_above_frontier_at_least_one_constraint_violated(self, c, mu, V, R, r):
        f = qc.saturation_frontier(c, mu, V, R, r)
        lam = f["lambda_governing"] * 1.05
        if not math.isfinite(lam):
            return
        violates_dock = lam > f["lambda_dock_max"]
        violates_floor = qc.quarantine_load(lam, r, R) > V
        self.assertTrue(violates_dock or violates_floor)

    @settings(max_examples=200, deadline=None)
    @given(
        c=st.integers(min_value=1, max_value=20),
        mu=st.floats(min_value=0.2, max_value=8.0),
        V=st.floats(min_value=1.0, max_value=500.0),
        R=st.floats(min_value=0.5, max_value=48.0),
        r=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_below_frontier_no_constraint_violated(self, c, mu, V, R, r):
        f = qc.saturation_frontier(c, mu, V, R, r)
        lam = f["lambda_governing"] * 0.95
        if not math.isfinite(lam):
            return
        self.assertLessEqual(lam, f["lambda_dock_max"])
        self.assertLessEqual(qc.quarantine_load(lam, r, R), V)


class TestClassification(unittest.TestCase):
    def test_floor_overflow_triggers_break_glass(self):
        # High retention: floor constraint binds before dock
        # rho = 15/18 = 0.8333 (dock stable); L = 15 * 0.9 * 2.0 = 27 > 20 positions
        res = qc.classify(
            lam=15.0, docks=6, service_rate_per_h=3.0,
            buffer_positions=20.0, resolution_h=2.0, retention_rate=0.9,
        )
        self.assertEqual(res["state"], "FLOOR_OVERFLOW")
        self.assertTrue(res["break_glass_required"])
        self.assertLess(res["headroom_positions"], 0)
        self.assertIn("FLOOR_OVER_CAPACITY", res["violations"])
        self.assertNotIn("RHO_GTE_1", res["violations"])

    def test_dock_collapse_when_rho_gte_one(self):
        res = qc.classify(
            lam=100.0, docks=2, service_rate_per_h=3.0,
            buffer_positions=1000.0, resolution_h=2.0, retention_rate=0.5,
        )
        self.assertEqual(res["state"], "DOCK_COLLAPSE")
        self.assertIsNone(res["wq_h"])
        self.assertTrue(res["break_glass_required"])

    def test_operational_with_positive_headroom(self):
        res = qc.classify(
            lam=5.0, docks=6, service_rate_per_h=3.0,
            buffer_positions=200.0, resolution_h=4.0, retention_rate=0.2,
        )
        self.assertEqual(res["state"], "OPERATIONAL")
        self.assertFalse(res["break_glass_required"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
