"""Herramienta 1 — captura de gemba estructurada.

Sin esto, la observacion del terreno vive en la libreta de alguien y muere ahi.
Convertirla en log estructurado es lo que la vuelve argumento.
"""

from .capture import GembaSession
from .schema import FIVE_WHYS_PROMPTS, GEMBA_QUESTIONS, WASTE_TYPES, Observation
from .transcribe import (
    WAREHOUSE_VOCAB,
    WORD_NUMBERS,
    Draft,
    Transcript,
    classify_waste,
    draft_observations,
    normalize,
    parse_duration_s,
    parse_frequency_per_shift,
    review_queue,
    waste_candidates,
    strip_accents,
    transcribe,
    transcribe_to_session,
)

# `normalize` y `strip_accents` son la normalizacion canonica de TODO el kit, no
# un detalle de gemba: `decide` las usa para el lexico de marcadores y para el
# indice de alias. Que no estuvieran exportadas es lo que hizo natural escribir
# un segundo `_norm` en `decide/schema.py` — con semantica distinta y el mismo
# nombre, que fue un bug real de validacion.
__all__ = [
    "GembaSession",
    "Observation",
    "WASTE_TYPES",
    "FIVE_WHYS_PROMPTS",
    "GEMBA_QUESTIONS",
    "Draft",
    "Transcript",
    "classify_waste",
    "draft_observations",
    "parse_duration_s",
    "parse_frequency_per_shift",
    "review_queue",
    "waste_candidates",
    "transcribe",
    "transcribe_to_session",
    "normalize",
    "strip_accents",
    "WORD_NUMBERS",
    "WAREHOUSE_VOCAB",
]
