"""Honestidad de una medicion de terreno.

Analogo de `Coverage` en `decide/query.py`, y por la misma razon: una camara
ve lo que ve. Un residual calculado sobre el 40% de los viajes es un numero
util SOLO si va acompanado del 40%. Sin eso es la mentira silenciosa que este
repo persigue.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeasurementCoverage:
    """Que fraccion de la realidad vio efectivamente el sensor.

    tracks_expected es opcional a proposito: sobre la mesa no hay WMS que diga
    cuantos viajes hubo, y fabricar un denominador para poder mostrar un
    porcentaje lindo es exactamente lo que no hacemos.
    """

    frames_total: int
    frames_with_marker: int
    tracks_seen: int
    tracks_expected: int | None = None
    discarded_low_confidence: int = 0

    @property
    def frame_pct(self) -> float:
        if self.frames_total <= 0:
            return 0.0
        return round(self.frames_with_marker / self.frames_total * 100, 1)

    @property
    def track_pct(self) -> float | None:
        if not self.tracks_expected:
            return None
        return round(self.tracks_seen / self.tracks_expected * 100, 1)

    @property
    def is_complete(self) -> bool:
        return False  # nunca, y por eso se muestra

    def note(self) -> str:
        partes = [
            f"{self.frames_with_marker}/{self.frames_total} frames con marcador "
            f"({self.frame_pct}%)",
            f"{self.tracks_seen} viajes reconstruidos",
        ]
        if self.track_pct is not None:
            partes.append(f"{self.track_pct}% de los viajes esperados")
        if self.discarded_low_confidence:
            partes.append(f"{self.discarded_low_confidence} tramos descartados por baja confianza")
        return (
            ", ".join(partes)
            + ". No tratar esta medicion como exhaustiva: lo que el marcador no "
            "mostro no esta en el numero."
        )
