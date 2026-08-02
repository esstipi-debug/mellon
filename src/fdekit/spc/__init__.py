"""Herramienta 9 — control estadistico de proceso para el sostenimiento.

No monitorees uptime: monitorea la metrica operativa. Un sistema al 100% de
disponibilidad que dejo de mover la aguja esta muerto y nadie se entero.
"""

from .xmr import xmr_chart, nelson_rules, degradation_alarm, plot_xmr

__all__ = ["xmr_chart", "nelson_rules", "degradation_alarm", "plot_xmr"]
