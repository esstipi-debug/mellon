"""
Formal property and model-checking oracle for Chapter 3 decoupled FSM projection.
Verifies totality, determinism, reachability of (s, a, d) space, negative invariant controls,
and physical buffer overflow accounting without dropping lots.
"""

from __future__ import annotations

import itertools
import unittest
from collections import deque

from hypothesis import given, settings, strategies as st

try:
    from probes import cap3_delta_projection as m
    from probes.cap3_delta_projection import A, Config, D, E, QuarantineBuffer, Rejected, S, delta
except ImportError:
    import cap3_delta_projection as m
    from cap3_delta_projection import A, Config, D, E, QuarantineBuffer, Rejected, S, delta

INITIAL_STATE = Config(s=S.ANNOUNCED, a=A.NONE, d=D.DOCKED)


def explore(start: Config = INITIAL_STATE) -> dict[Config, dict]:
    """Exhaustive BFS over S x A x D Cartesian product. Records parents to trace paths."""
    visited = {start: {"prev": None, "event": None}}
    queue = deque([start])
    while queue:
        cfg = queue.popleft()
        for ev in E:
            r = delta(cfg, ev)
            if isinstance(r, Rejected) or r in visited:
                continue
            visited[r] = {"prev": cfg, "event": ev}
            queue.append(r)
    return visited


class TestTotality(unittest.TestCase):
    def test_delta_is_total_across_full_cartesian_product(self):
        """64 configurations x 8 events x 3 movement history variants: no unhandled exceptions."""
        n = accepted = rejected = 0
        for s, a, d in itertools.product(S, A, D):
            for bwart in ((), ("103",), ("103", "105")):
                cfg = Config(s=s, a=a, d=d, bwart=bwart)
                for ev in E:
                    n += 1
                    r = delta(cfg, ev)
                    self.assertIsInstance(r, (Config, Rejected), msg=f"{cfg} + {ev}")
                    if isinstance(r, Config):
                        accepted += 1
                    else:
                        rejected += 1
                        self.assertTrue(r.reason)
        self.assertEqual(n, 8 * 4 * 2 * 3 * len(E))
        self.assertGreater(accepted, 0)
        self.assertGreater(rejected, 0)

    def test_delta_is_deterministic(self):
        cfg = Config(s=S.UNLOADING, a=A.BLOCKED_103, d=D.DOCKED, bwart=("103",))
        self.assertEqual(delta(cfg, E.COUNT_FAIL), delta(cfg, E.COUNT_FAIL))

    @settings(max_examples=200, deadline=None)
    @given(events=st.lists(st.sampled_from(list(E)), min_size=1, max_size=25))
    def test_arbitrary_sequences_never_crash(self, events):
        cfg = INITIAL_STATE
        for ev in events:
            r = delta(cfg, ev)
            if isinstance(r, Rejected):
                continue
            cfg = r
            self.assertEqual(m.check_all(cfg), [], msg=f"Invariant broken in {cfg}")


class TestReachability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.space = explore()

    def path_to(self, target: Config) -> list[E]:
        out, cfg = [], target
        while self.space[cfg]["prev"] is not None:
            out.append(self.space[cfg]["event"])
            cfg = self.space[cfg]["prev"]
        return list(reversed(out))

    def test_held_at_0230_state_is_reachable(self):
        """Carrier departed, physical lot held in quarantine, invoice arrested under 103."""
        target = Config(s=S.HELD, a=A.BLOCKED_103, d=D.DEPARTED, bwart=("103",))
        self.assertIn(target, self.space)
        self.assertEqual(
            self.path_to(target),
            [E.GATE_ARRIVE, E.WEIGH_OK, E.UNLOAD_START, E.COUNT_FAIL, E.DEPART],
        )
        self.assertEqual(m.check_all(target), [])

    def test_all_reachable_states_satisfy_all_invariants(self):
        for cfg in self.space:
            self.assertEqual(m.check_all(cfg), [], msg=f"Counterexample: {cfg}")

    def test_no_105_without_prior_103(self):
        for cfg in self.space:
            if "105" in cfg.bwart:
                i = cfg.bwart.index("105")
                self.assertIn("103", cfg.bwart[:i], msg=f"{cfg}")
            if "124" in cfg.bwart:
                i = cfg.bwart.index("124")
                self.assertIn("103", cfg.bwart[:i], msg=f"{cfg}")
                self.assertNotIn("105", cfg.bwart[:i], msg=f"124 requires non-valuated 103: {cfg}")
                self.assertIs(cfg.a, A.RETURNED_124)

    def test_no_release_without_count(self):
        """RELEASED_105 only reachable via COUNT_OK or RESOLVE_RELEASE, never via DEPART."""
        for cfg in self.space:
            if cfg.a is A.RELEASED_105:
                self.assertIn(cfg.s, {S.CLEARED, S.RELEASED}, msg=f"{cfg}")

    def test_reachable_space_strictly_constrains_product(self):
        """Reachable space yields exactly 12 of 64 configurations (18.75%)."""
        self.assertLess(len(self.space), 8 * 4 * 2)
        self.assertEqual(len(self.space), 12)
        self.assertEqual(len(m.REACHABLE_STATES), 12)
        self.assertEqual(set(m.REACHABLE_STATES), set(self.space))
        for cfg in self.space:
            if cfg.d is D.DEPARTED:
                self.assertNotEqual(cfg.s, S.UNLOADING)


class TestDecoupling(unittest.TestCase):
    """Core thesis: carrier departure is decoupled from accounting accreditation."""

    def test_depart_does_not_depend_on_accounting_coordinate(self):
        for a in A:
            for s in (S.HELD, S.CLEARED, S.RELEASED, S.RETURNED):
                cfg = Config(s=s, a=a, d=D.DOCKED, bwart=("103",))
                r = delta(cfg, E.DEPART)
                self.assertIsInstance(r, Config, msg=f"DEPART blocked in {cfg}")
                self.assertIs(r.d, D.DEPARTED)
                self.assertIs(r.a, a, msg="DEPART modified accounting state")
        # Negative control: carrier cannot depart mid-unloading
        mid_unload = Config(s=S.UNLOADING, a=A.BLOCKED_103, d=D.DOCKED, bwart=("103",))
        self.assertIsInstance(delta(mid_unload, E.DEPART), Rejected)

    def test_quarantine_retention_does_not_block_departure(self):
        held = Config(s=S.HELD, a=A.BLOCKED_103, d=D.DOCKED, bwart=("103",))
        self.assertIsInstance(delta(held, E.DEPART), Config)

    def test_conditional_103_persists_across_carrier_departure(self):
        r = delta(Config(s=S.HELD, a=A.BLOCKED_103, d=D.DOCKED, bwart=("103",)), E.DEPART)
        self.assertIs(r.a, A.BLOCKED_103)
        self.assertEqual(r.bwart, ("103",))


class TestNegativeControl(unittest.TestCase):
    """Negative controls: ensures invariants legitimately fail on invalid synthesized states."""

    def test_departure_without_gr_is_detected(self):
        invalid = Config(s=S.UNLOADING, a=A.NONE, d=D.DEPARTED, bwart=())
        self.assertIn("NO_DEPARTURE_WITHOUT_GR", m.check_all(invalid))

    def test_release_without_count_is_detected(self):
        invalid = Config(s=S.UNLOADING, a=A.RELEASED_105, d=D.DOCKED, bwart=("105",))
        self.assertIn("LOT_NEVER_FREE_WITHOUT_COUNT", m.check_all(invalid))

    def test_gr_from_void_is_detected(self):
        invalid = Config(s=S.ANNOUNCED, a=A.BLOCKED_103, d=D.DOCKED, bwart=("103",))
        self.assertIn("NO_GR_FROM_VOID", m.check_all(invalid))


class TestBuffer(unittest.TestCase):
    def test_overflow_imputes_without_dropping(self):
        b = QuarantineBuffer(capacity=2, occupants=[], overflow_events=[])
        self.assertEqual(b.admit("D1", "CC-DOCK", 2.5)["kind"], "ADMITTED")
        self.assertEqual(b.admit("D2", "CC-DOCK", 2.6)["kind"], "ADMITTED")
        ev = b.admit("D3", "CC-SUPERVISOR", 2.7)
        self.assertEqual(ev["kind"], "OVERFLOW_IMPUTED")
        self.assertEqual(ev["excess"], 1)
        self.assertEqual(ev["cost_center"], "CC-SUPERVISOR")
        self.assertEqual(b.load, 3)
        self.assertEqual(len(b.overflow_events), 1)

    def test_no_duplicate_admission(self):
        b = QuarantineBuffer(capacity=5, occupants=[], overflow_events=[])
        b.admit("D1", "CC", 0.0)
        with self.assertRaises(ValueError):
            b.admit("D1", "CC", 0.0)

    def test_cannot_release_non_occupant(self):
        b = QuarantineBuffer(capacity=5, occupants=[], overflow_events=[])
        with self.assertRaises(ValueError):
            b.release("D9")

    def test_inconsistent_initial_capacity_raises(self):
        with self.assertRaises(ValueError):
            QuarantineBuffer(capacity=1, occupants=["D1", "D2"], overflow_events=[])

    @settings(max_examples=200, deadline=None)
    @given(
        capacity=st.integers(min_value=0, max_value=8),
        ops=st.lists(st.tuples(st.sampled_from(["in", "out"]), st.integers(0, 12)), max_size=40),
    )
    def test_occupancy_only_exceeds_capacity_with_logged_event(self, capacity, ops):
        b = QuarantineBuffer(capacity=capacity, occupants=[], overflow_events=[])
        for kind, i in ops:
            did = f"D{i}"
            if kind == "in" and did not in b.occupants:
                b.admit(did, "CC", 0.0)
            elif kind == "out" and did in b.occupants:
                b.release(did)
            excess = max(0, b.load - capacity)
            if excess > 0:
                self.assertTrue(b.overflow_events, msg="excess without logged imputation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
