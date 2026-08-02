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
    # Puntos de una pista que `nearest_location` no pudo ubicar en el layout
    # (mas alla de `max_distance_m`). Vive aca, junto al resto de lo que no se
    # pudo medir, en vez de en un contador aparte -- ver `dwell_events` y
    # `tracks_to_eventlog` en `tracks.py` (ronda de arreglo 2 de la tarea 6).
    discarded_out_of_bounds: int = 0

    def __post_init__(self) -> None:
        """Valida coherencia de los contadores.

        Levanta ValueError si hay incoherencias que indican error en quien
        construye el objeto, es mas barato detectarlo en construccion que
        verlo aguas abajo.
        """
        # Validar no-negatividad
        if self.frames_total < 0:
            raise ValueError(
                f"frames_total no puede ser negativo: {self.frames_total}"
            )
        if self.frames_with_marker < 0:
            raise ValueError(
                f"frames_with_marker no puede ser negativo: {self.frames_with_marker}"
            )
        if self.tracks_seen < 0:
            raise ValueError(
                f"tracks_seen no puede ser negativo: {self.tracks_seen}"
            )
        if self.discarded_low_confidence < 0:
            raise ValueError(
                f"discarded_low_confidence no puede ser negativo: {self.discarded_low_confidence}"
            )
        if self.discarded_out_of_bounds < 0:
            raise ValueError(
                f"discarded_out_of_bounds no puede ser negativo: {self.discarded_out_of_bounds}"
            )
        if self.tracks_expected is not None and self.tracks_expected < 0:
            raise ValueError(
                f"tracks_expected no puede ser negativo: {self.tracks_expected}"
            )

        # Validar coherencia: frames_with_marker <= frames_total
        if self.frames_with_marker > self.frames_total:
            raise ValueError(
                f"frames_with_marker ({self.frames_with_marker}) no puede ser mayor que "
                f"frames_total ({self.frames_total}): revisar el calculo de marcador"
            )

        # Validar coherencia: si tracks_expected == 0, entonces tracks_seen debe ser 0
        if self.tracks_expected == 0 and self.tracks_seen > 0:
            raise ValueError(
                f"tracks_expected es 0 pero se reconstruyeron {self.tracks_seen} viajes: "
                "incoherencia, revisar WMS y reconstruccion"
            )

    @property
    def frame_pct(self) -> float:
        if self.frames_total <= 0:
            return 0.0
        return round(self.frames_with_marker / self.frames_total * 100, 1)

    @property
    def track_pct(self) -> float | None:
        # Distinguir: None significa "no se sabe", 0/0 tambien da None pero es
        # un caso coherente donde ambos son cero.
        if self.tracks_expected is None:
            return None
        if self.tracks_expected == 0:
            # Si esperamos 0 y vimos 0, es coherente pero indefinido (0/0).
            # Devolver None pero la nota lo menciona explicitamente.
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
        # Si tracks_expected esta definido (incluso si es 0), mencionar el porcentaje.
        # El caso tracks_expected == 0 es especial: se declararon 0 viajes esperados,
        # y si se reconstruyeron 0 es coherente (0/0 indefinido, pero lo mencionamos).
        if self.tracks_expected is not None:
            if self.tracks_expected == 0:
                # Caso especial 0/0: indefinido pero lo mencionamos como 0.0%
                partes.append("0.0% de los viajes esperados")
            else:
                if self.track_pct is not None:
                    partes.append(f"{self.track_pct}% de los viajes esperados")
        if self.discarded_low_confidence:
            partes.append(f"{self.discarded_low_confidence} tramos descartados por baja confianza")
        if self.discarded_out_of_bounds:
            # Un punto fuera de planta no es una visita al borde: es senal de
            # que la homografia esta mal calibrada. Se nombra la causa, no
            # solo el numero, porque el numero solo no dice a quien avisar.
            partes.append(
                f"{self.discarded_out_of_bounds} puntos descartados por caer fuera "
                "de planta (posible homografia mal calibrada)"
            )
        return (
            ", ".join(partes)
            + ". No tratar esta medicion como exhaustiva: lo que el marcador no "
            "mostro no esta en el numero."
        )
