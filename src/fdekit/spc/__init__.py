"""Herramienta 9 — control estadistico de proceso para el sostenimiento.

No monitorees uptime: monitorea la metrica operativa. Un sistema al 100% de
disponibilidad que dejo de mover la aguja esta muerto y nadie se entero.
"""

from .xmr import compute_limits, degradation_alarm, nelson_rules, plot_xmr, xmr_chart

# `compute_limits` faltaba, y es el que congela los limites sobre la linea base
# — o sea el punto de entrada de toda la doctrina del modulo. Tres consumidores
# (cli, demo, decide/metrics) lo importaban del submodulo porque el paquete no
# lo ofrecia.
__all__ = [
    "compute_limits",
    "xmr_chart",
    "nelson_rules",
    "degradation_alarm",
    "plot_xmr",
]
