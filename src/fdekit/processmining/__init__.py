"""Herramienta 3 — mineria de procesos sobre el log real del cliente.

El VSM que dibujaste en el gemba es el flujo *declarado*. Esto es el flujo
*real*. La distancia entre los dos es el diagnostico.
"""

from .log import EventLog
from .dfg import directly_follows, bottlenecks
from .variants import variants, rework_summary, conformance

__all__ = [
    "EventLog",
    "directly_follows",
    "bottlenecks",
    "variants",
    "rework_summary",
    "conformance",
]
