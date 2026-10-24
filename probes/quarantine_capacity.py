"""
quarantine_capacity.py
======================
Receiving dock vs. physical quarantine bay saturation frontier (Little's Law).

Two distinct constraints govern inbound receiving under conditional blocked GR (103):
  1. Dock doors (c servers, rate mu): queue diverges hyperbolically as rho = lam / (c * mu) -> 1.
  2. Quarantine floor bay (V pallet/lot positions): load grows linearly in arrival rate,
     L_quarantine = lam * r * R  (Little's Law, where r = retention_rate, R = resolution_h).

The binding throughput ceiling is min(dock_saturation, floor_saturation), crossing at
critical retention rate r* = V / (R * c * mu * u).
"""

from __future__ import annotations

import math


def _erlang_c_wait(lam: float, mu: float, c: int, ca2: float = 1.0, cs2: float = 1.0) -> dict:
    if c < 1:
        raise ValueError("c must be >= 1")
    if mu <= 0:
        raise ValueError("mu must be > 0")
    rho = lam / (c * mu)
    if rho >= 1.0:
        return {"rho": rho, "stable": False, "wq_h": math.inf, "lq": math.inf}

    a = lam / mu
    s = sum(a**k / math.factorial(k) for k in range(c))
    last = a**c / (math.factorial(c) * (1.0 - rho))
    p0 = 1.0 / (s + last)
    p_wait = last * p0
    wq_mmc = p_wait / (c * mu - lam)
    wq = wq_mmc * (ca2 + cs2) / 2.0
    return {"rho": rho, "stable": True, "p_wait": p_wait, "wq_h": wq, "lq": lam * wq}


def quarantine_load(lam: float, retention_rate: float, resolution_h: float) -> float:
    """Steady-state quarantined load on the floor: L = lam * r * R."""
    if not 0.0 <= retention_rate <= 1.0:
        raise ValueError("retention_rate must be in [0, 1]")
    if resolution_h < 0:
        raise ValueError("resolution_h cannot be negative")
    return lam * retention_rate * resolution_h


def dock_saturation(docks: int, service_rate_per_h: float, utilization_target: float = 0.85) -> float:
    """Maximum arrival rate within target dock utilization u in (0, 1)."""
    if not 0.0 < utilization_target < 1.0:
        raise ValueError("utilization_target must be in (0, 1)")
    return docks * service_rate_per_h * utilization_target


def floor_saturation(buffer_positions: float, retention_rate: float, resolution_h: float) -> float:
    """Maximum arrival rate absorbed by V quarantine positions without overflow: V / (r * R)."""
    if not 0.0 <= retention_rate <= 1.0:
        raise ValueError("retention_rate must be in [0, 1]")
    if resolution_h <= 0:
        raise ValueError("resolution_h must be > 0 to invert Little's Law")
    denom = retention_rate * resolution_h
    if denom == 0.0:
        return math.inf  # zero retention or IEEE-754 subnormal underflow guard
    return buffer_positions / denom


def saturation_frontier(
    docks: int,
    service_rate_per_h: float,
    buffer_positions: float,
    resolution_h: float,
    retention_rate: float,
    utilization_target: float = 0.85,
) -> dict:
    """Compute dock ceiling, quarantine bay ceiling, binding constraint, and crossover r*."""
    lam_dock = dock_saturation(docks, service_rate_per_h, utilization_target)
    lam_floor = floor_saturation(buffer_positions, retention_rate, resolution_h)
    governing = "DOCK" if lam_dock <= lam_floor else "FLOOR"
    denom = resolution_h * docks * service_rate_per_h * utilization_target
    r_star = buffer_positions / denom if denom > 0 else math.nan
    if math.isfinite(r_star) and 0.0 < r_star < 1.0:
        interp = f"Below r* = {r_star:.4f} DOCK governs; above r* FLOOR governs."
    elif math.isfinite(r_star) and r_star >= 1.0:
        interp = "No crossover in [0, 1] (r* >= 1): DOCK governs across the entire domain."
    else:
        interp = "Single constraint governs across the domain."
    return {
        "lambda_dock_max": lam_dock,
        "lambda_floor_max": lam_floor,
        "lambda_governing": min(lam_dock, lam_floor),
        "binding_constraint": governing,
        "retention_critical": r_star,
        "interpretation": interp,
    }


def classify(
    lam: float,
    docks: int,
    service_rate_per_h: float,
    buffer_positions: float,
    resolution_h: float,
    retention_rate: float,
    utilization_target: float = 0.85,
) -> dict:
    """Deterministic classification of yard/dock/quarantine regime for observed lambda."""
    q = _erlang_c_wait(lam, service_rate_per_h, docks)
    load = quarantine_load(lam, retention_rate, resolution_h)
    f = saturation_frontier(
        docks, service_rate_per_h, buffer_positions, resolution_h, retention_rate, utilization_target
    )
    violations = []
    if not q["stable"]:
        violations.append("RHO_GTE_1")
    if load > buffer_positions:
        violations.append("FLOOR_OVER_CAPACITY")
    if lam > f["lambda_governing"]:
        violations.append("ABOVE_FRONTIER")

    if not q["stable"]:
        state = "DOCK_COLLAPSE"
    elif load > buffer_positions:
        state = "FLOOR_OVERFLOW"
    elif lam > f["lambda_governing"]:
        state = "FRONTIER_STRESS"
    else:
        state = "OPERATIONAL"
    return {
        "state": state,
        "violations": violations,
        "lambda": lam,
        "rho": round(q["rho"], 4),
        "wq_h": None if not q["stable"] else round(q["wq_h"], 4),
        "yard_queue_trucks": None if not q["stable"] else round(q["lq"], 3),
        "quarantine_load_positions": round(load, 3),
        "buffer_positions": buffer_positions,
        "headroom_positions": round(buffer_positions - load, 3),
        "binding_constraint": f["binding_constraint"],
    }
