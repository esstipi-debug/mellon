"""Herramienta 3 — mineria de procesos sobre el log real del cliente.

El VSM que dibujaste en el gemba es el flujo *declarado*. Esto es el flujo
*real*. La distancia entre los dos es el diagnostico.
"""

from .log import EventLog
from .dfg import activity_durations, bottlenecks, directly_follows, to_mermaid
from .variants import conformance, pareto_coverage, rework_summary, variants

__all__ = [
    "EventLog",
    "directly_follows",
    "bottlenecks",
    "variants",
    "rework_summary",
    "conformance",
    "activity_durations",
    "pareto_coverage",
    "to_mermaid",
]
