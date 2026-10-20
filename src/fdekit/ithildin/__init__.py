"""fdekit.ithildin: Capa de telemetria pasiva, guardarrailes criptograficos y triggers condicionales.

El patron Ithildin modela soluciones tacticas de automatizacion pasiva:
operan invisibles en la sombra bajo condiciones nominales y solo se revelan
ante estimulos externos calificados, violaciones de contrato o riesgos operacionales.
"""

from __future__ import annotations

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
]
