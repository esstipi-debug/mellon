"""Hygiene tests for field-toolkit artifacts (Non-Surveillance & portability)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM_PATH = ROOT / "field-toolkit" / "07_forensic_process_conformance_simulator.py"


def _load_simulator():
    spec = importlib.util.spec_from_file_location("forensic_sim_07", SIM_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    return mod


def test_simulator_07_no_individual_surveillance_markers():
    text = SIM_PATH.read_text(encoding="utf-8")
    for forbidden in ("BREAKROOM", "MAC_OP_", "operator_mac", "operator_id"):
        assert forbidden not in text, f"Surveillance marker remains: {forbidden}"
    assert "Non-Surveillance Covenant" in text
    assert "shift_cohort" in text


def test_simulator_07_runs_cleanly_on_synthetic_cohort():
    mod = _load_simulator()
    wms, wifi, fork = mod.generate_forensic_test_scenarios()
    auditor = mod.ForensicOperationalAuditor(wms, wifi, fork)
    inv = auditor.verify_physical_invariants()
    assert inv["wifi_rf_audit"]["connected_ap_zone"] == "STAGING_DESK"
    assert inv["wifi_rf_audit"]["terminal_pool_id"] == "RF_POOL_02"
    assert all(e.shift_cohort.startswith("SHIFT_") for e in wms)
