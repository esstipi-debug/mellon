"""Herramienta 1 — captura de gemba estructurada.

Sin esto, la observacion del terreno vive en la libreta de alguien y muere ahi.
Convertirla en log estructurado es lo que la vuelve argumento.
"""

from .schema import Observation, WASTE_TYPES, FIVE_WHYS_PROMPTS
from .capture import GembaSession
from .transcribe import (
    Draft,
    Transcript,
    classify_waste,
    draft_observations,
    parse_duration_s,
    parse_frequency_per_shift,
    review_queue,
    transcribe,
    transcribe_to_session,
)

__all__ = [
    "Observation",
    "WASTE_TYPES",
    "FIVE_WHYS_PROMPTS",
    "GembaSession",
    "Draft",
    "Transcript",
    "classify_waste",
    "draft_observations",
    "parse_duration_s",
    "parse_frequency_per_shift",
    "review_queue",
    "transcribe",
    "transcribe_to_session",
]
