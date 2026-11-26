"""fdekit.ithildin: Passive telemetry, cryptographic guardrails, and conditional triggers.

The Ithildin pattern models tactical passive automation solutions:
operating invisibly in the dark under nominal conditions and revealing themselves
only upon qualified external stimuli, contract violations, or operational risks.
"""

from __future__ import annotations

from .boundary import (
    FORBIDDEN_CONTROL_KEYS,
    BoundaryViolation,
    ColumnSemanticsProbe,
    DataTaint,
    ExecutionMode,
    IterativeSplitProbe,
    NumericDriftReport,
    ScopedIthildinGuard,
    SemanticsClass,
    SemanticsReport,
    SplitAlert,
    UntrustedPayloadFence,
    verify_numeric_conservation,
)
from .envelope_bridge import (
    boundary_rejection_to_event,
    decision_to_event,
    seal_credential,
    seal_stream,
    verdict_to_event,
    write_jsonl,
)
from .guards import IthildinGuard, RiskLevel, StagingAction, StagingVerdict
from .probes import STANDARD_5_COLUMNS, PassiveEventProbe, ProbeReport
from .triggers import ConditionalTrigger, IthildinTriggerRegistry, TriggerResult

__all__ = [
    "BoundaryViolation",
    "ColumnSemanticsProbe",
    "ConditionalTrigger",
    "DataTaint",
    "ExecutionMode",
    "FORBIDDEN_CONTROL_KEYS",
    "IterativeSplitProbe",
    "IthildinGuard",
    "IthildinTriggerRegistry",
    "NumericDriftReport",
    "PassiveEventProbe",
    "ProbeReport",
    "RiskLevel",
    "STANDARD_5_COLUMNS",
    "ScopedIthildinGuard",
    "SemanticsClass",
    "SemanticsReport",
    "SplitAlert",
    "StagingAction",
    "StagingVerdict",
    "TriggerResult",
    "UntrustedPayloadFence",
    "boundary_rejection_to_event",
    "decision_to_event",
    "seal_credential",
    "seal_stream",
    "verdict_to_event",
    "verify_numeric_conservation",
    "write_jsonl",
]
