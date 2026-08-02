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
import dataclasses
import math
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterable, NamedTuple

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


def nearest_location(
    layout: Layout,
    x_m: float,
    y_m: float,
    level: int = 1,
    max_distance_m: float | None = None,
) -> str | None:
    """Ubicacion del layout mas cercana a un punto del piso.

    El nivel se fija en 1 porque una camara cenital no ve altura: la pista dice
    en que modulo estuvo el carro, no a que altura estiro el brazo el operador.

    `max_distance_m` es el limite de confianza (ronda de arreglo 1, hallazgo 3
    de la tarea 6): sin el, un punto a 500 m del layout -- lo tipico de una
    homografia mal calibrada -- se mapea en silencio a la ubicacion de borde
    mas cercana, y el mapa de espagueti sale plausible y falso. Con el limite
    puesto, ese punto devuelve `None` en vez de inventar una ubicacion, y quien
    llama puede contar cuantos puntos cayeron afuera en vez de no enterarse
    nunca.
    """
    mejor, mejor_d2 = None, float("inf")
    for a in range(1, layout.aisles + 1):
        for b in range(1, layout.bays + 1):
            code = layout.location_code(a, b, level)
            lx, ly = layout.xy(code)
            d2 = (lx - x_m) ** 2 + (ly - y_m) ** 2
            if d2 < mejor_d2:
                mejor, mejor_d2 = code, d2
    if mejor is None:
        return None
    if max_distance_m is not None and math.sqrt(mejor_d2) > max_distance_m:
        return None
    return mejor


class DwellEvents(NamedTuple):
    """Resultado de `dwell_events`.

    `discarded_out_of_bounds` va separado de `stops` porque son dos preguntas
    distintas: cuantas paradas reales hubo, y cuantos puntos de la pista no se
    pudieron ubicar en el layout (`nearest_location` devolvio `None` por
    `max_distance_m`). Fusionarlas en un solo numero esconde la segunda
    pregunta -- la que importa cuando la homografia esta mal calibrada
    (ronda de arreglo 1, hallazgo 3 de la tarea 6).
    """

    stops: list[tuple[float, str]]
    discarded_out_of_bounds: int


def _tramos_consecutivos(
    points: list[TrackPoint], asignaciones: list[str | None]
) -> list[tuple[str | None, float, float]]:
    """Agrupa puntos consecutivos con la misma ubicacion asignada.

    Cada tramo es (ubicacion, t_inicio, t_fin) -- una corrida maximal de
    puntos seguidos con la misma asignacion, incluida la asignacion `None`
    (puntos que `nearest_location` no pudo ubicar). Es el insumo crudo de
    `dwell_events`: todavia no distingue ruido de parada real, solo junta lo
    que ya vino junto en el tiempo.
    """
    tramos: list[tuple[str | None, float, float]] = []
    loc_actual = asignaciones[0]
    t_ini = t_fin = points[0].t_s
    for p, loc in zip(points[1:], asignaciones[1:]):
        if loc == loc_actual:
            t_fin = p.t_s
            continue
        tramos.append((loc_actual, t_ini, t_fin))
        loc_actual, t_ini, t_fin = loc, p.t_s, p.t_s
    tramos.append((loc_actual, t_ini, t_fin))
    return tramos


def dwell_events(
    points: list[TrackPoint],
    layout: Layout,
    min_dwell_s: float = 4.0,
    max_gap_s: float = 2.0,
    max_distance_m: float | None = None,
) -> DwellEvents:
    """Paradas reales: ni lugares por los que se paso, ni ruido de deteccion.

    Un picker cruza medio CD sin tocar nada. Contar cada ubicacion por la que
    pasa como una visita infla el conteo, y ese conteo despues infla el caso
    economico. El umbral de permanencia (`min_dwell_s`) es lo que separa
    "estuvo ahi" de "paso por ahi".

    Algoritmo, en cuatro pasos (ronda de arreglo 2 de la tarea 6; reemplaza
    por completo el de la ronda 1, que tenia una regresion de la misma
    familia -- ver mas abajo):

    1. Cada punto se asigna a su ubicacion mas cercana (o `None` si cae fuera
       de `max_distance_m`).
    2. Se arman TRAMOS: corridas consecutivas maximales de puntos con la
       misma ubicacion asignada. Cada tramo tiene ubicacion, inicio, fin y
       duracion (`_tramos_consecutivos`).
    3. Un tramo es RUIDO si su duracion es menor que `max_gap_s`. Los tramos
       de una misma ubicacion separados unicamente por tramos de ruido (de
       cualquier otra ubicacion, o sin ubicacion) se fusionan: un tramo
       sustancial (no-ruido) de OTRA ubicacion si corta la fusion.
    4. Se emite una parada por cada grupo fusionado cuya duracion TOTAL
       (la suma de la duracion de sus propios tramos, sin contar el tiempo de
       las interrupciones toleradas) llega a `min_dwell_s`, con el `t_s` del
       primer punto del grupo.

    Por que el criterio de "ruido" es el mismo en los tres casos que importan:

    - 20 s en una ubicacion con excursiones de 1 s cada 2 s: los tramos de
      excursion miden 1 s < `max_gap_s` (2.0) y son ruido -> se toleran, y los
      tramos de la ubicacion principal se fusionan en una sola parada.
    - Dos ubicaciones reales alternando cada 1 s durante 20 s: el tramo de
      CADA visita mide ~1 s < `max_gap_s`, asi que cada uno es ruido PARA LA
      OTRA ubicacion -- pero eso no le impide fusionarse con sus propios
      tramos anteriores. El resultado son dos grupos, uno por ubicacion, cada
      uno acumulando ~10 s -> dos paradas. Este es el caso que la ronda 1
      perdia: ahi, un punto de otra ubicacion tolerado no sumaba nada a su
      propia ubicacion, asi que la segunda ubicacion desaparecia sin dejar
      rastro (ni fusionada, ni corta, ni descartada).
    - Una permanencia real interrumpida por una excursion de 20 s: ese tramo
      mide 20 s >= `max_gap_s`, no es ruido, y corta la fusion. Ademas, si esa
      excursion en si misma dura lo suficiente, genera su propia parada: dos
      paradas en la ubicacion original mas una en la lejana.

    `max_gap_s=2.0` por default es el umbral que separa ruido de parada real:
    mas largo que el ruido de deteccion tipico entre cuadros consecutivos
    (el marcador visto en diagonal salta unos centimetros), y mas corto que
    un desplazamiento real a otra ubicacion. Subirlo mucho fusiona paradas
    vecinas en una sola (dos visitas realmente distintas se cuentan como una);
    bajarlo a cero cualquier interrupcion corta el grupo, y se vuelve al bug
    original del algoritmo de ancla (una permanencia real cortada por ruido
    de deteccion desaparece).

    El algoritmo anterior (ancla que reinicia al alejarse de un radio) fallaba
    en las dos direcciones: una permanencia real cortada por ruido
    desaparecia, y la misma oscilacion contaba dos paradas para la misma
    ubicacion. El de la ronda 1 (agrupar por ubicacion asignada, sin fusion
    entre tramos no adyacentes de la misma ubicacion) arreglaba eso pero
    introducia una regresion nueva de la misma familia: un punto de otra
    ubicacion tolerado como ruido se descartaba entero, asi que una segunda
    ubicacion real intercalada con la primera se perdia sin dejar rastro. La
    fusion por tramos (este algoritmo) es la version que no pierde ninguna de
    las dos: agrupa por ubicacion Y tolera interrupciones sin tirar
    informacion de la ubicacion interrumpida.

    `radius_m` ya no existe (se fue en la ronda 1): era una tolerancia
    espacial continua, la distancia del punto al ultimo visto. La tolerancia
    actual es de otro tipo, y no la reemplaza: en el espacio, la asigna la
    grilla fija de `nearest_location`; en el tiempo, la controla `max_gap_s`.
    Son dos ejes distintos (espacio vs. tiempo), asi que ese grado de libertad
    espacial no se recupera con este cambio.

    El timestamp de la parada es el `t_s` del PRIMER punto del grupo (la
    entrada), no el del ultimo (la salida): usar el de salida sobreestima la
    duracion en un intervalo de muestreo.
    """
    if not points:
        return DwellEvents([], 0)

    descartados = 0
    asignaciones: list[str | None] = []
    for p in points:
        loc = nearest_location(layout, p.x_m, p.y_m, max_distance_m=max_distance_m)
        if loc is None and max_distance_m is not None:
            descartados += 1
        asignaciones.append(loc)

    tramos = _tramos_consecutivos(points, asignaciones)

    paradas: list[tuple[float, str]] = []
    # Un grupo abierto por ubicacion: cuanto lleva acumulado y donde empezo.
    abiertos: dict[str, dict[str, float]] = {}

    def _cerrar(loc: str) -> None:
        grupo = abiertos.pop(loc, None)
        if grupo is not None and grupo["duracion"] >= min_dwell_s:
            paradas.append((grupo["t_primero"], loc))

    for loc, t_ini, t_fin in tramos:
        duracion = t_fin - t_ini
        es_ruido = duracion < max_gap_s

        if loc is not None:
            grupo = abiertos.get(loc)
            if grupo is None:
                abiertos[loc] = {"t_primero": t_ini, "duracion": duracion}
            else:
                grupo["duracion"] += duracion

        if not es_ruido:
            # Interrupcion sustancial: corta la fusion de cualquier OTRA
            # ubicacion que estuviera esperando (la propia, si la hay, sigue
            # abierta y acumulando en la rama de arriba).
            for otra_loc in [l for l in abiertos if l != loc]:
                _cerrar(otra_loc)

    for loc in list(abiertos):
        _cerrar(loc)

    return DwellEvents(paradas, descartados)


def tracks_to_eventlog(
    tracks: dict[str, list[TrackPoint]],
    layout: Layout,
    t0: pd.Timestamp,
    coverage: MeasurementCoverage | None = None,
    min_dwell_s: float = 4.0,
    max_gap_s: float = 2.0,
    max_distance_m: float | None = None,
) -> tuple[EventLog, MeasurementCoverage]:
    """Pistas medidas -> el contrato de datos que el kit entero ya sabe leer.

    `t0` es argumento y no `pd.Timestamp.now()` (regla 4): una funcion que lee
    el reloj no se puede testear, y hay un test que verifica que dos llamadas
    con el mismo `t0` dan exactamente lo mismo.

    Simplificacion consciente de la etapa 1: una pista = un caso. Segmentar
    viajes por cercania al DOCK necesita un CD real con dock; sobre la mesa el
    carro hace un solo viaje. Eso queda para la etapa 3, no esta implementado
    aca.

    `coverage` es la que devolvio `build_tracks` para esta misma pista (ronda
    de arreglo 2, hallazgo 2 de la tarea 6). El repo ya tiene un lugar para
    "cuanto no se pudo medir" -- `MeasurementCoverage` -- y repartir esa
    contabilidad entre ese objeto y un contador aparte es como se termina
    reportando uno y olvidando el otro. Por eso esta funcion no descarta el
    `discarded_out_of_bounds` de `dwell_events`: lo suma a la cobertura
    recibida (con `dataclasses.replace`, porque `MeasurementCoverage` es
    frozen) y devuelve la cobertura actualizada junto con el log. Si no se
    pasa `coverage` (por ejemplo, en un test que arma pistas a mano sin pasar
    por `build_tracks`), se construye una minima con lo unico que se sabe en
    esta funcion: cuantas pistas hay.
    """
    if coverage is None:
        coverage = MeasurementCoverage(
            frames_total=0, frames_with_marker=0, tracks_seen=len(tracks)
        )

    filas = []
    total_descartados = 0
    for subject, puntos in tracks.items():
        resultado = dwell_events(
            puntos,
            layout,
            min_dwell_s=min_dwell_s,
            max_gap_s=max_gap_s,
            max_distance_m=max_distance_m,
        )
        total_descartados += resultado.discarded_out_of_bounds
        for t_s, loc in resultado.stops:
            filas.append(
                {
                    "case_id": subject,
                    "activity": "PICK",
                    "timestamp": t0 + pd.Timedelta(seconds=float(t_s)),
                    "resource": subject,
                    "location": loc,
                }
            )

    log = EventLog(
        pd.DataFrame(filas, columns=["case_id", "activity", "timestamp", "resource", "location"])
    )
    cobertura_final = dataclasses.replace(
        coverage,
        discarded_out_of_bounds=coverage.discarded_out_of_bounds + total_descartados,
    )
    return log, cobertura_final
