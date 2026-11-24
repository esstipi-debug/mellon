"""fdekit.ithildin: Passive telemetry, cryptographic guardrails, and conditional triggers.

The Ithildin pattern models tactical passive automation solutions:
operating invisibly in the dark under nominal conditions and revealing themselves
only upon qualified external stimuli, contract violations, or operational risks.
"""

from __future__ import annotations

from .envelope_bridge import (
    decision_to_event,
    seal_credential,
    seal_stream,
    verdict_to_event,
    write_jsonl,
)
from .guards import IthildinGuard, RiskLevel, StagingAction, StagingVerdict
from .probes import PassiveEventProbe, ProbeReport, STANDARD_5_COLUMNS
from .triggers import ConditionalTrigger, IthildinTriggerRegistry, TriggerResult

__all__ = [
    "ConditionalTrigger",
    "IthildinGuard",
    "IthildinTriggerRegistry",
    "PassiveEventProbe",
    "ProbeReport",
    "RiskLevel",
    "STANDARD_5_COLUMNS",
    "StagingAction",
    "StagingVerdict",
    "TriggerResult",
    "decision_to_event",
    "seal_credential",
    "seal_stream",
    "verdict_to_event",
    "write_jsonl",
]
