"""Contrato compartido entre la capa agentica y la capa de terreno.

Stdlib pura a proposito: este subpaquete viaja al notebook prestado de un
centro de distribucion, donde no hay GPU, no hay red y no hay permisos de
instalacion. Cualquier import pesado que entre aca rompe la regla 2 del repo.
"""

from .cobertura import BUGS_HISTORICOS, CoberturaGuardia
from .hallazgo import Hallazgo, Procedencia

__all__ = [
    "Hallazgo",
    "Procedencia",
    "CoberturaGuardia",
    "BUGS_HISTORICOS",
]
