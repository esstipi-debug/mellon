"""Herramienta 4 — auditoria de datos maestros (MSA aplicado a datos).

La herramienta que mas despliegues salva y que casi ningun vendor tiene
sistematizada. Antes de prometer un numero: muestrear SKUs, medirlos fisicamente
y comparar contra el maestro. En CDs reales un error de dimensionamiento en el
10-30% del catalogo es normal, y hace fallar a cualquier motor de slotting,
cubicaje, ruteo o robotica de picking.
"""

from .master_audit import (
    sampling_plan,
    stratified_sample,
    audit_master,
    audit_summary,
    link_defects_to_rework,
)

__all__ = [
    "sampling_plan",
    "stratified_sample",
    "audit_master",
    "audit_summary",
    "link_defects_to_rework",
]
