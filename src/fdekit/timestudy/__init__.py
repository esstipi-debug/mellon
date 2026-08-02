"""Herramienta 2 — estudio de tiempos y diagrama de espagueti."""

from .cycles import (
    cycle_time_stats,
    cycle_times,
    operator_variation,
    standard_work_gap,
    takt_analysis,
)
from .spaghetti import (
    location_frequency,
    plot_heatmap,
    plot_spaghetti,
    slotting_opportunity,
    travel_report,
    travel_stats,
)

# Lo que exporta el paquete es lo que consumen `demo.py` y `value/levers.py`:
# `travel_stats`, `standard_work_gap` y `cycle_time_stats` son los tres que
# alimentan el caso economico y los tres estaban fuera de esta lista.
__all__ = [
    "cycle_times",
    "cycle_time_stats",
    "takt_analysis",
    "operator_variation",
    "standard_work_gap",
    "travel_report",
    "travel_stats",
    "location_frequency",
    "slotting_opportunity",
    "plot_spaghetti",
    "plot_heatmap",
]
