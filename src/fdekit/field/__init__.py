"""Toolkit de terreno — sensores que miden lo que el WMS infiere.

El corte que gobierna el paquete: `vision` es la unica pieza que toca cv2, y
solo produce detecciones crudas. Todo lo demas es Python puro sobre un CSV, y
por eso se testea sin camara.
"""

from .coverage import MeasurementCoverage
from .homography import FloorHomography
from .privacy import (
    AnonymityError,
    AnonymityGate,
    assert_no_identity,
    canonicalize,
    new_session_salt,
    pseudonymize,
)
from .tracks import (
    Detection,
    TrackPoint,
    build_tracks,
    load_detections,
    track_distance_m,
)

__all__ = [
    "FloorHomography",
    "MeasurementCoverage",
    "AnonymityError",
    "AnonymityGate",
    "assert_no_identity",
    "canonicalize",
    "new_session_salt",
    "pseudonymize",
    "Detection",
    "TrackPoint",
    "build_tracks",
    "load_detections",
    "track_distance_m",
]
