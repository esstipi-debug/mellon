"""
cap3_delta_projection.py
========================
Three-coordinate inbound state-machine projection for Chapter 3:

    s  physical lot state
    a  accounting accreditation state (reference movement code posted)
    d  carrier truck state (truck may depart once unloading/count finishes while lot stays held)

Design principle:
    Conditional blocked receipt ('103') is the default entry gate prior to physical
    verification; unrestricted release ('105') requires verified count; pre-release
    vendor rejection uses '124' (reversing blocked quantity without an FI entry),
    whereas '122' applies solely after a prior '105' valuation release.

Scope note:
    Movement codes ('103', '105', '124', '122') and OBYC account keys ('BSX', 'WRX')
    represent standard reference MM-IM/OBYC ledger schemas and must be verified against
    each target system's chart-of-accounts configuration before production cutover.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable


class S(str, Enum):
    ANNOUNCED = "ANNOUNCED"
    GATE_ARRIVED = "GATE_ARRIVED"
    WEIGHED_IN = "WEIGHED_IN"
    UNLOADING = "UNLOADING"
    HELD = "HELD"
    CLEARED = "CLEARED"
    RELEASED = "RELEASED"
    RETURNED = "RETURNED"


class A(str, Enum):
    NONE = "NONE"
    BLOCKED_103 = "BLOCKED_103"
    RELEASED_105 = "RELEASED_105"
    RETURNED_124 = "RETURNED_124"


class D(str, Enum):
    DOCKED = "DOCKED"
    DEPARTED = "DEPARTED"


class E(str, Enum):
    GATE_ARRIVE = "GATE_ARRIVE"
    WEIGH_OK = "WEIGH_OK"
    UNLOAD_START = "UNLOAD_START"
    COUNT_OK = "COUNT_OK"
    COUNT_FAIL = "COUNT_FAIL"
    RESOLVE_RELEASE = "RESOLVE_RELEASE"
    RESOLVE_RETURN = "RESOLVE_RETURN"
    DEPART = "DEPART"


MOVEMENTS: dict[str, dict[str, str]] = {
    "103": {
        "effect": "goods receipt into GR blocked stock (non-valuated)",
        "debit": "-",
        "credit": "-",
        "status": "reference MM-IM standard (no FI document generated on non-valuated 103)",
    },
    "105": {
        "effect": "release from GR blocked stock to unrestricted-use inventory",
        "debit": "BSX inventory",
        "credit": "WRX GR/IR clearing",
        "status": "reference OBYC standard (confirm valuation class mapping)",
    },
    "124": {
        "effect": "return to vendor directly from GR blocked stock (reverses 103)",
        "debit": "-",
        "credit": "-",
        "status": "reference MM-IM standard (reverses blocked quantity without FI entry)",
    },
    "122": {
        "effect": "return delivery to vendor from valuated stock (post-105 only)",
        "debit": "WRX GR/IR clearing",
        "credit": "BSX inventory",
        "status": "reference OBYC standard (applicable only after prior 105 release)",
    },
}


@dataclass(frozen=True)
class Config:
    s: S
    a: A
    d: D
    bwart: tuple[str, ...] = ()

    def __str__(self) -> str:  # pragma: no cover
        return f"({self.s.value}, {self.a.value}, {self.d.value}, bwart={list(self.bwart)})"


@dataclass(frozen=True)
class Rejected:
    reason: str
    detail: str


Outcome = Config | Rejected


def _post(cfg: Config, bwart: str, a: A) -> Config:
    return replace(cfg, a=a, bwart=cfg.bwart + (bwart,))


def delta(cfg: Config, event: E) -> Outcome:
    """Total transition function: never raises; returns Config or Rejected for all pairs."""
    s, a, d = cfg.s, cfg.a, cfg.d

    if event is E.GATE_ARRIVE:
        if s is not S.ANNOUNCED:
            return Rejected("ILLEGAL", f"GATE_ARRIVE requires ANNOUNCED, got {s.value}")
        return replace(cfg, s=S.GATE_ARRIVED)

    if event is E.WEIGH_OK:
        if s is not S.GATE_ARRIVED:
            return Rejected("ILLEGAL", f"WEIGH_OK requires GATE_ARRIVED, got {s.value}")
        return _post(replace(cfg, s=S.WEIGHED_IN), "103", A.BLOCKED_103)

    if event is E.UNLOAD_START:
        if s is not S.WEIGHED_IN:
            return Rejected("ILLEGAL", f"UNLOAD_START requires WEIGHED_IN, got {s.value}")
        return replace(cfg, s=S.UNLOADING)

    if event is E.COUNT_OK:
        if s is not S.UNLOADING:
            return Rejected("ILLEGAL", f"COUNT_OK requires UNLOADING, got {s.value}")
        if a is not A.BLOCKED_103:
            return Rejected("NO_BLOCKED_GR", f"COUNT_OK without prior 103 (a={a.value})")
        return _post(replace(cfg, s=S.CLEARED), "105", A.RELEASED_105)

    if event is E.COUNT_FAIL:
        if s is not S.UNLOADING:
            return Rejected("ILLEGAL", f"COUNT_FAIL requires UNLOADING, got {s.value}")
        if a is not A.BLOCKED_103:
            return Rejected("NO_BLOCKED_GR", f"COUNT_FAIL without prior 103 (a={a.value})")
        return replace(cfg, s=S.HELD)

    if event is E.RESOLVE_RELEASE:
        if s is not S.HELD:
            return Rejected("ILLEGAL", f"RESOLVE_RELEASE requires HELD, got {s.value}")
        if a is not A.BLOCKED_103:
            return Rejected("NO_BLOCKED_GR", f"RESOLVE_RELEASE without prior 103 (a={a.value})")
        return _post(replace(cfg, s=S.RELEASED), "105", A.RELEASED_105)

    if event is E.RESOLVE_RETURN:
        if s is not S.HELD:
            return Rejected("ILLEGAL", f"RESOLVE_RETURN requires HELD, got {s.value}")
        if a is not A.BLOCKED_103:
            return Rejected("NO_BLOCKED_GR", f"RESOLVE_RETURN without prior 103 (a={a.value})")
        return _post(replace(cfg, s=S.RETURNED), "124", A.RETURNED_124)

    if event is E.DEPART:
        if d is D.DEPARTED:
            return Rejected("ILLEGAL", "carrier truck already departed")
        if s not in {S.HELD, S.CLEARED, S.RELEASED, S.RETURNED}:
            return Rejected(
                "ILLEGAL",
                f"DEPART requires completed unloading (HELD/CLEARED/RELEASED/RETURNED), got {s.value}",
            )
        return replace(cfg, d=D.DEPARTED)

    return Rejected("UNKNOWN_EVENT", f"unrecognized event: {event!r}")


def invariant_lot_never_free_without_count(cfg: Config) -> bool:
    if cfg.a is A.RELEASED_105:
        return cfg.s in {S.CLEARED, S.RELEASED}
    return True


def invariant_no_gr_from_void(cfg: Config) -> bool:
    if "103" in cfg.bwart:
        return cfg.s is not S.ANNOUNCED and cfg.s is not S.GATE_ARRIVED
    return True


def invariant_no_departure_without_gr(cfg: Config) -> bool:
    if cfg.d is D.DEPARTED:
        return "103" in cfg.bwart and cfg.s in {S.HELD, S.CLEARED, S.RELEASED, S.RETURNED}
    return True


INVARIANTS: dict[str, Callable[[Config], bool]] = {
    "LOT_NEVER_FREE_WITHOUT_COUNT": invariant_lot_never_free_without_count,
    "NO_GR_FROM_VOID": invariant_no_gr_from_void,
    "NO_DEPARTURE_WITHOUT_GR": invariant_no_departure_without_gr,
}


def check_all(cfg: Config) -> list[str]:
    return [name for name, fn in INVARIANTS.items() if not fn(cfg)]


def initial_state() -> Config:
    return Config(s=S.ANNOUNCED, a=A.NONE, d=D.DOCKED)


def reachable_states() -> frozenset[Config]:
    """BFS closure of delta from initial_state: yields exactly 12 of 64 (s, a, d) tuples."""
    start = initial_state()
    seen: set[Config] = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for cfg in frontier:
            for event in E:
                out = delta(cfg, event)
                if isinstance(out, Rejected):
                    continue
                if out not in seen:
                    seen.add(out)
                    nxt.append(out)
        frontier = nxt
    return frozenset(seen)


REACHABLE_STATES = reachable_states()


@dataclass
class QuarantineBuffer:
    capacity: int
    occupants: list[str]
    overflow_events: list[dict]

    def __post_init__(self) -> None:
        if self.capacity < 0:
            raise ValueError("capacity cannot be negative")
        if len(self.occupants) > self.capacity:
            raise ValueError("initial occupants exceed capacity")

    @property
    def load(self) -> int:
        return len(self.occupants)

    def admit(self, delivery_id: str, cost_center: str, clock_h: float) -> dict:
        if delivery_id in self.occupants:
            raise ValueError(f"{delivery_id} is already in quarantine")
        overflow = self.load + 1 > self.capacity
        self.occupants.append(delivery_id)
        event = {
            "delivery_id": delivery_id,
            "kind": "OVERFLOW_IMPUTED" if overflow else "ADMITTED",
            "cost_center": cost_center,
            "clock_h": clock_h,
            "load_after": self.load,
            "capacity": self.capacity,
            "excess": max(0, self.load - self.capacity),
        }
        if overflow:
            self.overflow_events.append(event)
        return event

    def release(self, delivery_id: str) -> None:
        if delivery_id not in self.occupants:
            raise ValueError(f"{delivery_id} is not in quarantine")
        self.occupants.remove(delivery_id)
