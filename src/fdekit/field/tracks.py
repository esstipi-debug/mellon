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

import pandas as pd

from ..layout import Layout
from ..processmining.log import EventLog
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
    fieldnames = reader.fieldnames or []

    # Chequear BOM antes que "falta la columna": si un fieldname arranca con
    # ﻿, la columna SI esta en el CSV, solo que con un caracter invisible
    # pegado adelante. "no en fieldnames" no distingue eso de "no esta", y
    # decir "falta la columna" manda a revisar el archivo en vez del encoding
    # -- que es el defecto real, no donde estaba el open().
    con_bom = [f for f in fieldnames if f.startswith("﻿")]
    if con_bom:
        raise ValueError(
            "el CSV de detecciones tiene marca de orden de bytes (BOM) pegada "
            f"a la cabecera {con_bom!r}; abrir el archivo con "
            "encoding='utf-8-sig' en vez de 'utf-8' para leerlo bien"
        )

    faltan = [c for c in _COLUMNAS if c not in fieldnames]
    if faltan:
        raise ValueError(f"al CSV de detecciones le falta(n) la(s) columna(s): {faltan}")

    detecciones = []
    # Arranca en 2: la fila 1 es la cabecera, la primera fila de datos es la 2.
    for numero_fila, r in enumerate(reader, start=2):
        sobrantes = r.get(None)
        if sobrantes:
            raise ValueError(
                f"fila {numero_fila} del CSV de detecciones tiene "
                f"{len(sobrantes)} valor(es) de mas respecto de la cabecera; "
                "causa probable: un campo con una coma sin comillas que corrio "
                "las columnas siguientes, revisar esa fila en el archivo original"
            )
        faltantes = [c for c in _COLUMNAS if r.get(c) is None]
        if faltantes:
            raise ValueError(
                f"fila {numero_fila} del CSV de detecciones: "
                f"falta(n) valor(es) en columna(s) {faltantes}, revisar que "
                "la fila tenga las mismas columnas que la cabecera"
            )
        frame = int(r["frame"])
        if frame < 0:
            raise ValueError(
                f"fila {numero_fila} del CSV de detecciones: frame negativo "
                f"({frame}), un numero de cuadro no puede ser negativo, "
                "revisar el detector que genero el CSV"
            )
        detecciones.append(
            Detection(r["marker_id"], frame, float(r["x_px"]), float(r["y_px"]))
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


def nearest_location(layout: Layout, x_m: float, y_m: float, level: int = 1) -> str:
    """Ubicacion del layout mas cercana a un punto del piso.

    El nivel se fija en 1 porque una camara cenital no ve altura: la pista dice
    en que modulo estuvo el carro, no a que altura estiro el brazo el operador.
    """
    mejor, mejor_d = None, float("inf")
    for a in range(1, layout.aisles + 1):
        for b in range(1, layout.bays + 1):
            code = layout.location_code(a, b, level)
            lx, ly = layout.xy(code)
            d = (lx - x_m) ** 2 + (ly - y_m) ** 2
            if d < mejor_d:
                mejor, mejor_d = code, d
    return mejor


def dwell_events(
    points: list[TrackPoint],
    layout: Layout,
    min_dwell_s: float = 4.0,
    radius_m: float = 1.5,
) -> list[tuple[float, str]]:
    """Paradas reales, no lugares por los que se paso.

    Un picker cruza medio CD sin tocar nada. Contar cada ubicacion por la que
    pasa como una visita infla el conteo, y ese conteo despues infla el caso
    economico. El umbral de permanencia (`min_dwell_s`) es lo que separa
    "estuvo ahi" de "paso por ahi".
    """
    if not points:
        return []

    paradas: list[tuple[float, str]] = []
    ancla = points[0]
    inicio = points[0].t_s
    for p in points[1:]:
        if math.dist((p.x_m, p.y_m), (ancla.x_m, ancla.y_m)) <= radius_m:
            continue
        if p.t_s - inicio >= min_dwell_s:
            paradas.append((inicio, nearest_location(layout, ancla.x_m, ancla.y_m)))
        ancla, inicio = p, p.t_s

    if points[-1].t_s - inicio >= min_dwell_s:
        paradas.append((inicio, nearest_location(layout, ancla.x_m, ancla.y_m)))
    return paradas


def tracks_to_eventlog(
    tracks: dict[str, list[TrackPoint]],
    layout: Layout,
    t0: pd.Timestamp,
    min_dwell_s: float = 4.0,
) -> EventLog:
    """Pistas medidas -> el contrato de datos que el kit entero ya sabe leer.

    `t0` es argumento y no `pd.Timestamp.now()` (regla 4): una funcion que lee
    el reloj no se puede testear, y hay un test que verifica que dos llamadas
    con el mismo `t0` dan exactamente lo mismo.

    Simplificacion consciente de la etapa 1: una pista = un caso. Segmentar
    viajes por cercania al DOCK necesita un CD real con dock; sobre la mesa el
    carro hace un solo viaje. Eso queda para la etapa 3, no esta implementado
    aca.
    """
    filas = []
    for subject, puntos in tracks.items():
        for t_s, loc in dwell_events(puntos, layout, min_dwell_s=min_dwell_s):
            filas.append(
                {
                    "case_id": subject,
                    "activity": "PICK",
                    "timestamp": t0 + pd.Timedelta(seconds=float(t_s)),
                    "resource": subject,
                    "location": loc,
                }
            )
    return EventLog(
        pd.DataFrame(filas, columns=["case_id", "activity", "timestamp", "resource", "location"])
    )
