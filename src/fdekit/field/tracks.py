"""Detecciones crudas -> pistas en metros, con cobertura.

Frontera del toolkit: de aca para abajo no hay camara, no hay cv2 y no hay
video — hay una lista de tuplas. Un CSV de detecciones grabado una vez permite
desarrollar y testear el 100% de la logica sin hardware.

Contrato de metadatos con `vision.py` (la unica pieza que toca cv2):
`vision.write_detections` graba el total de cuadros del video en la primera
linea del CSV, comentada, con el formato exacto `# frames_total=<int>`, antes
de la cabecera `marker_id,frame,x_px,y_px`. `parse_detections` y
`load_detections` saltean esa linea si esta presente y devuelven su valor
junto con las detecciones, como `tuple[list[Detection], int | None]`.

Si la linea no esta, `frames_total` es `None` -- y eso no se rellena con una
suposicion. Derivarlo de las detecciones (p.ej. el frame maximo visto) daria
siempre una cobertura mentirosa: el tramo sin detecciones desapareceria del
calculo en vez de contar como cuadros sin ver. Un CSV sin esa linea es un CSV
del que no se puede afirmar cobertura (regla 3): quien llame a `build_tracks`
con esos datos tiene que proveer `frames_total` por su cuenta o fallar.
"""

from __future__ import annotations

import csv
import dataclasses
import itertools
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


_PREFIJO_METADATA = "# frames_total="


def _parse_frames_total_metadata(linea: str) -> int:
    """Interpreta la linea de metadatos `# frames_total=<int>`.

    Mismo estandar de mensaje que el resto del modulo (BOM, fila corta, fila
    larga, frame negativo): nombra la causa y dice que revisar, en vez de
    dejar pasar el `ValueError` crudo de `int()`.
    """
    valor = linea[len(_PREFIJO_METADATA) :].strip()
    try:
        frames_total = int(valor)
    except ValueError as e:
        raise ValueError(
            "la primera linea del CSV de detecciones declara el total de "
            f"cuadros del video con '{_PREFIJO_METADATA}<int>', pero el "
            f"valor encontrado no es un entero: {valor!r}; revisar como se "
            "genero esa linea (deberia venir de vision.write_detections)"
        ) from e
    if frames_total < 0:
        raise ValueError(
            "la primera linea del CSV de detecciones declara "
            f"frames_total={frames_total}, y un total de cuadros no puede "
            "ser negativo; revisar el valor que le paso a write_detections"
        )
    return frames_total


def parse_detections(handle: IO[str]) -> tuple[list[Detection], int | None]:
    """Lee detecciones de un handle de texto CSV.

    Antes de la cabecera puede haber una linea de metadatos comentada,
    `# frames_total=<int>` -- ver el contrato de metadatos en el docstring
    del modulo. Si esta, se saltea y su valor se devuelve junto con las
    detecciones; si no esta, se devuelve `None` en su lugar, sin adivinar.

    Esa linea tiene que ser la PRIMERA y UNICA del archivo: repetida, o
    corrida a despues de la cabecera, es un error explicito aca -- no un
    "falta la columna" o "falta el valor" indirecto que manda a revisar el
    lugar equivocado (el mismo defecto que ya se arreglo para el BOM).
    """
    primera_linea = handle.readline()
    if primera_linea.startswith(_PREFIJO_METADATA):
        frames_total = _parse_frames_total_metadata(primera_linea)
        segunda_linea = handle.readline()
        if segunda_linea.startswith(_PREFIJO_METADATA):
            raise ValueError(
                "el CSV de detecciones tiene la linea de metadatos "
                f"'{_PREFIJO_METADATA}<int>' repetida; tiene que aparecer una "
                "sola vez, como la primera linea del archivo, antes de la "
                "cabecera 'marker_id,frame,x_px,y_px'"
            )
        fuente = itertools.chain([segunda_linea], handle)
        primera_fila_de_datos = 3
    else:
        frames_total = None
        fuente = itertools.chain([primera_linea], handle)
        primera_fila_de_datos = 2

    reader = csv.DictReader(fuente)
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
    # primera_fila_de_datos ya contempla si hubo linea de metadatos antes de
    # la cabecera (fila 3) o no (fila 2, el caso de siempre: la fila 1 es la
    # cabecera).
    for numero_fila, r in enumerate(reader, start=primera_fila_de_datos):
        sobrantes = r.get(None)
        if sobrantes:
            raise ValueError(
                f"fila {numero_fila} del CSV de detecciones tiene "
                f"{len(sobrantes)} valor(es) de mas respecto de la cabecera; "
                "causa probable: un campo con una coma sin comillas que corrio "
                "las columnas siguientes, revisar esa fila en el archivo original"
            )
        primer_campo = r.get(_COLUMNAS[0])
        if isinstance(primer_campo, str) and primer_campo.startswith(_PREFIJO_METADATA):
            raise ValueError(
                f"fila {numero_fila} del CSV de detecciones parece la linea "
                f"de metadatos '{_PREFIJO_METADATA}<int>' fuera de lugar; "
                "tiene que ir como la primera linea del archivo, antes de la "
                "cabecera 'marker_id,frame,x_px,y_px', no despues"
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
    return detecciones, frames_total


def load_detections(path: str | Path) -> tuple[list[Detection], int | None]:
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
    points: list[TrackPoint], asignaciones: list[str | None], max_gap_s: float
) -> list[tuple[str | None, float, float, bool]]:
    """Agrupa puntos consecutivos con la misma ubicacion asignada.

    Cada tramo es (ubicacion, t_inicio, t_fin, hueco_antes) -- una corrida
    maximal de puntos seguidos con la misma asignacion, incluida la
    asignacion `None` (puntos que `nearest_location` no pudo ubicar). Es el
    insumo crudo de `dwell_events`: todavia no distingue ruido de parada
    real, solo junta lo que ya vino junto en el tiempo.

    Corta el tramo aunque la ubicacion sea la misma si el hueco entre dos
    puntos CONSECUTIVOS DEL TRACK supera `max_gap_s` -- sin importar a que
    ubicacion cayo cada uno. `hueco_antes` marca si el tramo empieza justo
    despues de uno de esos huecos (a diferencia de un simple cambio de
    ubicacion con el marcador visto todo el tiempo). Es la pregunta "¿el
    marcador dejo de verse?", medida sobre el TRACK completo -- ver el
    docstring de `dwell_events` para la distincion con "¿el carro se fue a
    otro lado?", que se mide distinto (ronda de arreglo 4 de la tarea 6).

    Sin este corte, dos puntos de la MISMA ubicacion separados por un hueco de
    deteccion de cien segundos formarian un solo tramo de cien segundos de
    "duracion": un marcador que desaparecio cien segundos y reaparecio no es
    un marcador que estuvo quieto cien segundos, es data que no se vio.
    """
    tramos: list[tuple[str | None, float, float, bool]] = []
    loc_actual = asignaciones[0]
    t_ini = t_fin = points[0].t_s
    hueco_antes = False  # el primer tramo no tiene "antes"
    for p, loc in zip(points[1:], asignaciones[1:]):
        gap = p.t_s - t_fin
        if loc == loc_actual and gap <= max_gap_s:
            t_fin = p.t_s
            continue
        tramos.append((loc_actual, t_ini, t_fin, hueco_antes))
        hueco_antes = gap > max_gap_s
        loc_actual, t_ini, t_fin = loc, p.t_s, p.t_s
    tramos.append((loc_actual, t_ini, t_fin, hueco_antes))
    return tramos


def _distancia_ubicaciones(layout: Layout, a: str, b: str) -> float:
    """Distancia en metros entre dos ubicaciones del layout, via `Layout.xy`.

    Es la distancia entre las COORDENADAS de las ubicaciones, no entre
    puntos crudos del track: dos puntos crudos asignados a la misma
    ubicacion tienen distancia 0 aca, aunque el marcador haya saltado unos
    centimetros entre cuadros.
    """
    (ax, ay), (bx, by) = layout.xy(a), layout.xy(b)
    return math.dist((ax, ay), (bx, by))


def dwell_events(
    points: list[TrackPoint],
    layout: Layout,
    min_dwell_s: float = 4.0,
    max_gap_s: float = 2.0,
    max_distance_m: float | None = None,
    noise_radius_m: float = 0.75,
) -> DwellEvents:
    """Paradas reales: ni lugares por los que se paso, ni ruido de deteccion.

    Un picker cruza medio CD sin tocar nada. Contar cada ubicacion por la que
    pasa como una visita infla el conteo, y ese conteo despues infla el caso
    economico. El umbral de permanencia (`min_dwell_s`) es lo que separa
    "estuvo ahi" de "paso por ahi".

    Algoritmo, en cuatro pasos (ronda de arreglo 4 de la tarea 6; la fusion
    por tramos y la duracion por span son las de la ronda 2 y 3, pero el
    corte por hueco de deteccion se separo en DOS preguntas distintas -- ver
    mas abajo):

    1. Cada punto se asigna a su ubicacion mas cercana (o `None` si cae fuera
       de `max_distance_m`).
    2. Se arman TRAMOS: corridas consecutivas maximales de puntos con la
       misma ubicacion asignada (`_tramos_consecutivos`). Ademas, cada tramo
       queda marcado con `hueco_antes`: si el hueco entre este tramo y el
       anterior, medido sobre el TRACK completo (dos muestras consecutivas,
       sin importar la ubicacion de cada una), supera `max_gap_s`.
    3. Dos preguntas distintas deciden si la fusion se corta, y NO son la
       misma comprobacion:
       - *¿El marcador dejo de verse?* -- `hueco_antes`, del punto 2. Si es
         cierto, TODOS los grupos abiertos se cierran (sin importar su
         ubicacion): el track se quedo sin muestras por mas de `max_gap_s`, y
         ningun grupo puede asumir que la ubicacion se mantuvo durante ese
         tiempo no observado.
       - *¿El carro se fue a otro lado?* -- un tramo de OTRA ubicacion se
         absorbe (no corta nada) si su duracion PROPIA es `< max_gap_s` (una
         interrupcion corta, sea ruido de deteccion o una parada real breve)
         **o** si esa ubicacion esta a menos de `noise_radius_m` de la
         ubicacion del grupo (ronda de arreglo 5 de la tarea 6 -- la
         distancia se mide entre las COORDENADAS de las dos ubicaciones via
         `Layout.xy`, `_distancia_ubicaciones`, no entre los puntos crudos).
         Si NINGUNA de las dos se cumple (lejos Y dura mas que el umbral), es
         un desplazamiento real, y corta la fusion de cualquier OTRA
         ubicacion que estuviera esperando (la propia ubicacion del tramo
         sigue abierta y acumulando).
    4. Se emite una parada por cada grupo fusionado cuya duracion llega a
       `min_dwell_s`, con el `t_s` del primer punto del grupo.

    La duracion de un grupo fusionado es el SPAN: `t_s` del ULTIMO punto del
    grupo menos `t_s` del PRIMERO, incluyendo el tiempo de los tramos de ruido
    que quedaron adentro (ronda 3; la ronda 2 sumaba la duracion propia de
    cada tramo del grupo, ignorando el tiempo tolerado). La ronda 2 asumia sin
    decirlo que "duracion total" queria decir "suma de tramos propios", y esa
    definicion falla justo en el caso realista: cuando el carro alterna entre
    dos ubicaciones a una frecuencia parecida a la de la camara, CADA tramo
    tiene una sola muestra -- duracion propia cero. Sumar ceros da cero, y una
    permanencia real de veinte segundos (o dos ubicaciones reales alternando)
    no generaba ninguna parada. El span es lo correcto conceptualmente: si el
    carro estuvo dieciocho segundos en una zona, aunque el marcador saltara a
    otra ubicacion por instantes, estuvo dieciocho segundos ahi.

    Por que el criterio es el mismo en los cuatro casos que importan:

    - Una ubicacion visitada repetidamente con una excursion de una sola
      muestra en el medio, cada 3 s (p.ej. A en t=0,3,6 con B en t=2,5): el
      track nunca pierde al marcador (2 s maximo entre muestras, nunca supera
      `max_gap_s`), asi que `hueco_antes` nunca corta nada; y los tramos de B
      duran 0 s cada uno, ruido para A -> A se fusiona en una sola parada. El
      span PROPIO de B (de su primera a su ultima muestra) tambien crece con
      cada repeticion, igual que el de A: en una pista larga, si B se repite
      lo suficiente, su propio span termina cruzando `min_dwell_s` tambien, y
      deja de distinguirse de una segunda ubicacion real (el caso de abajo).
      Este algoritmo no resuelve esa ambiguedad de fondo con datos puramente
      temporales -- ver la nota de longitud en el test que cubre este caso.
    - Dos ubicaciones reales alternando cada 1 s durante 20 s: el tramo de
      CADA visita mide ~0 s, asi que cada uno es ruido PARA LA OTRA ubicacion
      -- pero eso no le impide fusionarse con sus propios tramos anteriores.
      El span de cada ubicacion (de su primera a su ultima muestra) llega a
      ~18-19 s -> DOS paradas, una por ubicacion. Este es el caso que la
      ronda 1 perdia por completo y la ronda 2 perdia por el criterio de suma:
      con suma, cada tramo de 0 s no aporta nada aunque el span sea enorme.
    - Una permanencia real interrumpida por una excursion de 20 s: ese tramo
      mide 20 s >= `max_gap_s`, no es ruido, y corta la fusion. Ademas, si esa
      excursion en si misma dura lo suficiente, genera su propia parada: dos
      paradas en la ubicacion original mas una en la lejana.
    - La misma ubicacion antes y despues de un hueco de deteccion largo (el
      marcador desaparece y reaparece en el mismo lugar, sin ningun tramo de
      otra ubicacion en el medio): `hueco_antes` es cierto para el tramo que
      sigue al hueco, y cierra TODOS los grupos abiertos en ese instante --
      sin el corte, el span abarcaria todo el hueco no observado y contaria
      como una sola parada larga que nadie vio. Con el corte, son dos tramos
      separados de la misma ubicacion, y el span de cada uno se mide por
      separado -> DOS paradas (si cada lado alcanza `min_dwell_s` por si
      solo). Un marcador que no se vio no es un marcador que se quedo quieto
      -- es justamente lo que la cobertura existe para declarar.
    - Estanteria densa (`bay_pitch` chico, p.ej. 0.4 m): un operario parado
      cerca del borde entre dos ubicaciones vecinas, inclinandose y
      enderezandose para alcanzar un nivel de arriba, alterna entre las dos
      asignaciones sin moverse. Cada tramo dura menos que `max_gap_s`, es
      ruido temporal -- pero antes de la ronda 5, ninguna de las dos
      ubicaciones llegaba sola a `min_dwell_s`, y la parada desaparecia
      entera sin dejar rastro. Con `noise_radius_m` (ronda 5), las dos
      ubicaciones vecinas estan a menos de `noise_radius_m` de distancia, asi
      que se absorben una a la otra sin importar cuanto dure cada tramo ->
      UNA parada.

    `max_gap_s=2.0` por default es el umbral TEMPORAL que separa una
    interrupcion corta de un desplazamiento real: dentro de un tramo, mas
    largo que el ruido de deteccion tipico entre cuadros consecutivos y mas
    corto que un desplazamiento real a otra ubicacion; entre tramos de la
    misma ubicacion, mas largo que un hueco de deteccion normal (el marcador
    se pierde un instante) y mas corto que un hueco que amerita desconfiar de
    la permanencia. Subirlo mucho fusiona paradas vecinas en una sola, o
    inventa permanencia sobre huecos de deteccion largos; bajarlo a cero
    corta cualquier interrupcion (incluido el ruido normal), y se vuelve al
    bug original del algoritmo de ancla.

    `noise_radius_m=0.75` por default es el umbral ESPACIAL, el eje que
    faltaba desde la ronda 2 (ronda de arreglo 5): mas grande que el jitter
    de deteccion de un marcador ArUco (centimetros) y que el paso de una
    estanteria densa (`bay_pitch` chico, p.ej. 0.4 m en e-commerce o farma),
    y mas chico que la distancia entre bahias de un CD de pitch normal
    (metros). Con estanteria densa, el criterio TEMPORAL solo no alcanza: el
    periodo critico (el tiempo entre dos "vueltas" de una postura repetitiva,
    como inclinarse para alcanzar un nivel de arriba) se cruza en segundos,
    no en minutos, y ninguna de las dos ubicaciones vecinas llega a
    `min_dwell_s` por si sola -- la parada real desaparece entera. El eje
    espacial resuelve eso sin tocar el temporal: una ubicacion vecina cerca
    se absorbe SIEMPRE, sin importar cuanto dure el tramo; una ubicacion
    lejos solo se absorbe si dura menos que `max_gap_s`, como antes. Subirlo
    mucho fusiona dos paradas vecinas legitimas (dos bahias distintas que el
    operario realmente visito una despues de la otra); bajarlo a cero vuelve
    al bug de arriba (la parada de estanteria densa desaparece otra vez).

    El algoritmo anterior (ancla que reinicia al alejarse de un radio) fallaba
    en las dos direcciones: una permanencia real cortada por ruido
    desaparecia, y la misma oscilacion contaba dos paradas para la misma
    ubicacion. El de la ronda 1 (agrupar por ubicacion asignada, sin fusion
    entre tramos no adyacentes) arreglaba eso pero perdia una segunda
    ubicacion real alternada sin dejar rastro. El de la ronda 2 (fusion por
    tramos con duracion sumada) arreglaba esa perdida, pero solo en el caso de
    tramos de varios puntos: con tramos de una sola muestra, la suma daba cero
    y el problema volvia disfrazado. El de la ronda 3 (fusion con duracion de
    span, mas un corte por hueco medido ENTRE LOS PUNTOS DEL GRUPO -- es decir,
    entre dos muestras consecutivas de la MISMA ubicacion, ignorando lo que
    hubiera pasado en el medio) arreglaba el span pero colapsaba dos preguntas
    distintas en una sola comprobacion: "¿el marcador dejo de verse?" y "¿el
    carro se fue a otro lado?" quedaban medidas con el mismo numero (el hueco
    entre puntos del grupo), y una ubicacion visitada cada `> max_gap_s`
    segundos con OTRA deteccion real en el medio se leia como ausencia del
    marcador, exactamente el bug original con otra puerta. El de la ronda 4
    separa las dos preguntas: `hueco_antes` mide ausencia sobre el TRACK
    completo, la duracion propia del tramo mide desplazamiento real -- pero
    solo con el eje TEMPORAL, y el revisor de la ronda 5 encontro el caso
    realista que ese eje solo no cubre: con estanteria densa, dos ubicaciones
    vecinas separadas por centimetros pueden tardar mas que `max_gap_s` en
    alternar (una postura repetitiva, no ruido de camara), y sin un criterio
    de distancia, cada una se lee como una interrupcion sustancial de la
    otra -- ninguna llega a `min_dwell_s`, y la parada real desaparece
    entera. `noise_radius_m` (ronda 5) agrega el eje ESPACIAL que faltaba
    desde la ronda 2.

    `radius_m` (el de antes de la ronda 1) no es lo mismo que
    `noise_radius_m`, aunque los dos sean distancias: `radius_m` era una
    tolerancia CONTINUA sobre la distancia de un punto al ultimo punto
    visto (por eso desaparecio cuando el algoritmo dejo de rastrear un
    "ultimo punto"). `noise_radius_m` es una distancia FIJA entre las
    COORDENADAS DE DOS UBICACIONES del layout (`Layout.xy`), no entre
    puntos crudos del track -- un eje distinto, reintroducido para una
    pregunta distinta.

    El caso de "una sola interrupcion corta dentro de una permanencia larga"
    (un test de la ronda 1, borrado en la ronda 2) no tiene test propio en
    esta version: bajo el criterio de tramo-ruido, una interrupcion corta es
    exactamente un tramo con duracion propia menor que `max_gap_s`, y ese
    comportamiento ya lo cubre el primer caso de la lista de arriba (las
    excursiones toleradas). Un test aparte para el mismo criterio con otro
    numero de interrupciones no agregaria cobertura nueva.

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

    tramos = _tramos_consecutivos(points, asignaciones, max_gap_s)

    paradas: list[tuple[float, str]] = []
    # Un grupo abierto por ubicacion: primer y ultimo punto visto ahi. La
    # duracion es el span (t_ultimo - t_primero), no una suma -- ver docstring.
    abiertos: dict[str, dict[str, float]] = {}

    def _cerrar(loc: str) -> None:
        grupo = abiertos.pop(loc, None)
        if grupo is not None and (grupo["t_ultimo"] - grupo["t_primero"]) >= min_dwell_s:
            paradas.append((grupo["t_primero"], loc))

    for loc, t_ini, t_fin, hueco_antes in tramos:
        duracion_tramo = t_fin - t_ini
        es_ruido_temporal = duracion_tramo < max_gap_s

        if hueco_antes:
            # Pregunta 1: ¿el marcador dejo de verse? Medida sobre el TRACK
            # completo en `_tramos_consecutivos`, no sobre este grupo. Si es
            # cierto, ningun grupo abierto -- de ninguna ubicacion -- puede
            # asumir que se mantuvo durante el tiempo no observado.
            for l in list(abiertos):
                _cerrar(l)

        loc_efectiva = loc
        if loc is not None:
            grupo = abiertos.get(loc)
            if grupo is not None:
                grupo["t_ultimo"] = t_fin
            else:
                # No hay grupo propio abierto todavia. Si hay un grupo
                # abierto de OTRA ubicacion a menos de `noise_radius_m`
                # (ronda 5), este tramo se fusiona ADENTRO de ese grupo en
                # vez de abrir uno competidor -- si no, dos ubicaciones
                # vecinas (p.ej. estanteria densa) terminan cada una con su
                # propio span y su propia parada, en vez de una sola.
                vecino = next(
                    (
                        l
                        for l in abiertos
                        if _distancia_ubicaciones(layout, loc, l) < noise_radius_m
                    ),
                    None,
                )
                if vecino is not None:
                    abiertos[vecino]["t_ultimo"] = t_fin
                    loc_efectiva = vecino
                else:
                    abiertos[loc] = {"t_primero": t_ini, "t_ultimo": t_fin}

        # Pregunta 2: ¿el carro se fue a otro lado? Un tramo de OTRA ubicacion
        # se absorbe (no la corta) si es corto (`es_ruido_temporal`) O si esa
        # otra ubicacion esta a menos de `noise_radius_m` DE LA UBICACION DEL
        # TRAMO (ronda 5) -- estanteria densa hace que dos ubicaciones vecinas
        # alternen mas lento que `max_gap_s` sin que el carro se haya movido
        # de verdad. Solo si NINGUNA de las dos se cumple es un desplazamiento
        # real que corta la fusion. Se compara contra `loc_efectiva`, no
        # `loc`: si este tramo ya se fusiono en un grupo vecino, ese grupo no
        # se corta a si mismo.
        for otra_loc in [l for l in abiertos if l != loc_efectiva]:
            cerca_espacialmente = (
                loc is not None
                and _distancia_ubicaciones(layout, loc, otra_loc) < noise_radius_m
            )
            if not es_ruido_temporal and not cerca_espacialmente:
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
    noise_radius_m: float = 0.75,
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
            noise_radius_m=noise_radius_m,
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
