"""Contrato compartido entre la capa agentica y la capa de terreno.

Stdlib pura a proposito: este subpaquete viaja al notebook prestado de un
centro de distribucion, donde no hay GPU, no hay red y no hay permisos de
instalacion. Cualquier import pesado que entre aca rompe la regla 2 del repo.
"""

from .catalogo import (
    CATALOGO,
    Entrada,
    conservacion_de_masa,
    medir_catalogo,
    no_negativo,
    sin_fanout,
    una_sola_anualizacion,
)
from .cobertura import BUGS_HISTORICOS, CoberturaGuardia
from .guardia import Guardia, evaluar
from .hallazgo import Hallazgo, Procedencia
from .sonda import ResultadoSonda, Veredicto, sonda_guardia

__all__ = [
    "Hallazgo",
    "Procedencia",
    "CoberturaGuardia",
    "BUGS_HISTORICOS",
    "Guardia",
    "evaluar",
    "Veredicto",
    "ResultadoSonda",
    "sonda_guardia",
    "Entrada",
    "CATALOGO",
    "medir_catalogo",
    "sin_fanout",
    "conservacion_de_masa",
    "no_negativo",
    "una_sola_anualizacion",
]
