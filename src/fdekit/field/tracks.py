"""Detecciones crudas -> pistas en metros, con cobertura.

Frontera del toolkit: de aca para abajo no hay camara, no hay cv2 y no hay
video — hay una lista de tuplas. Un CSV de detecciones grabado una vez permite
desarrollar y testear el 100% de la logica sin hardware.

Limite conocido: el CSV de detecciones no guarda el total de cuadros del
video, solo los cuadros donde algo se vio. `build_tracks` exige `frames_total`
por afuera; `detect_markers` lo devuelve junto con las detecciones en el mismo
proceso de deteccion. Quien solo tenga un CSV ya grabado (sin ese numero al
lado) no puede reconstruirlo desde el archivo. Resolver esto -- por ejemplo
grabando `frames_total` en el propio CSV o en un archivo companero -- queda
para una tarea futura.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterable

from .coverage import MeasurementCoverage
from .homography import FloorHomography
from .privacy import pseudonymize

_COLUMNAS = ("marker_id", "frame", "x_px", "y_px")


@dataclass(frozen=True)
class Detection:
    marker_id: str
    frame: int
    x_px: float
    y_px: float


@dataclass(frozen=True)
class TrackPoint:
    t_s: float
    x_m: float
    y_m: float


def parse_detections(handle: IO[str]) -> list[Detection]:
    reader = csv.DictReader(handle)
    faltan = [c for c in _COLUMNAS if c not in (reader.fieldnames or [])]
    if faltan:
        raise ValueError(f"al CSV de detecciones le falta(n) la(s) columna(s): {faltan}")

    detecciones = []
    # Arranca en 2: la fila 1 es la cabecera, la primera fila de datos es la 2.
    for numero_fila, r in enumerate(reader, start=2):
        faltantes = [c for c in _COLUMNAS if r.get(c) is None]
        if faltantes:
            raise ValueError(
                f"fila {numero_fila} del CSV de detecciones: "
                f"falta(n) valor(es) en columna(s) {faltantes}, revisar que "
                "la fila tenga las mismas columnas que la cabecera"
            )
        detecciones.append(
            Detection(r["marker_id"], int(r["frame"]), float(r["x_px"]), float(r["y_px"]))
        )
    return detecciones


def load_detections(path: str | Path) -> list[Detection]:
    # utf-8-sig: un CSV guardado como "CSV UTF-8" desde Excel en Windows lleva
    # BOM. Con "utf-8" a secas, DictReader deja el BOM pegado al primer
    # nombre de columna ('﻿marker_id') y el chequeo de columnas de arriba
    # dispara un error que acusa a la columna equivocada. utf-8-sig lo pela
    # sin afectar archivos que ya vienen sin BOM.
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return parse_detections(fh)


def build_tracks(
    detections: Iterable[Detection],
    homography: FloorHomography,
    fps: float,
    salt: bytes,
    frames_total: int,
    min_points: int = 3,
) -> tuple[dict[str, list[TrackPoint]], MeasurementCoverage]:
    """Agrupa detecciones por marcador y las proyecta a metros.

    `frames_total` es el largo del video, y es obligatorio: no tiene default.
    Las detecciones solo contienen los frames donde SE VIO algo, asi que
    derivar `frames_total` de ellas daria siempre 100% de cobertura -- la
    mentira que este modulo existe para evitar. Un default opcional se puede
    omitir sin querer; un parametro obligatorio no.

    De donde sale este numero: `detect_markers` (la pieza que si toca cv2) lo
    devuelve junto con las detecciones, porque es quien recorrio el video
    cuadro a cuadro. Quien solo tenga el CSV de detecciones grabado antes
    tiene que anotar `frames_total` por separado en ese momento: el CSV en si
    no lo guarda (ver limite conocido en el docstring del modulo).
    """
    if fps <= 0:
        raise ValueError(f"fps tiene que ser positivo, llego {fps}")

    dets = sorted(detections, key=lambda d: (d.marker_id, d.frame))
    por_marcador: dict[str, list[Detection]] = {}
    for d in dets:
        por_marcador.setdefault(d.marker_id, []).append(d)

    tracks: dict[str, list[TrackPoint]] = {}
    descartadas = 0
    for marker_id, grupo in por_marcador.items():
        if len(grupo) < min_points:
            descartadas += 1
            continue
        puntos = []
        for d in grupo:
            x_m, y_m = homography.to_meters(d.x_px, d.y_px)
            puntos.append(TrackPoint(t_s=d.frame / fps, x_m=x_m, y_m=y_m))
        tracks[pseudonymize(marker_id, salt)] = puntos

    frames_vistos = len({d.frame for d in dets})
    cobertura = MeasurementCoverage(
        frames_total=frames_total,
        frames_with_marker=frames_vistos,
        tracks_seen=len(tracks),
        discarded_low_confidence=descartadas,
    )
    return tracks, cobertura


def track_distance_m(points: list[TrackPoint]) -> float:
    """Distancia recorrida, en linea entre muestras consecutivas.

    A diferencia de `Layout.route_distance`, aca NO se rutea por el layout: la
    camara ve el camino que el operador efectivamente hizo, incluidos los que
    el modelo no contempla. Esa diferencia es todo el punto del toolkit.
    """
    return float(
        sum(
            math.dist((a.x_m, a.y_m), (b.x_m, b.y_m))
            for a, b in zip(points, points[1:])
        )
    )
