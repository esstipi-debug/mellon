"""Modelo vs medicion: el residual, con su cobertura al lado.

El kit dibuja el espagueti con aritmetica sobre el layout, asumiendo que el
picker va directo entre ubicaciones por la transversal optima. Este modulo mide
cuanto se equivoca ese supuesto.

El entregable no es un grafico mas lindo: es una frase del tipo "el modelo dice
8 km/dia, la medicion dice 11,3 — el 41% son viajes que el WMS no registra".
Sin este modulo el proyecto es infalsable (hueco H1).

Por que el residual esperado es positivo, no cero (dato de otra sesion, no del
spec original -- ver PROMPT-INVENTARIO-MEDICIONES.md, seccion 3.2, fuera de
este repo): `_pick_paths` (en `timestudy/spaghetti.py`) calcula un PISO, no una
estimacion central. No ve retrocesos del operador, no ve el tramo de la
excepcion (el generador emite el evento con la ubicacion DECLARADA, nunca con
la real), y no ve congestion entre pickers. Los tres solo pueden alargar el
camino real, nunca acortarlo. Por eso un residual cercano a cero NO significa
"el modelo es perfecto" -- significa que algo anda mal en la medicion (pistas
cortadas, cobertura baja, homografia mal calibrada). El numero que parece
bueno ahi es justo el que hay que desconfiar.
"""

from __future__ import annotations

from datetime import date

from .field.coverage import MeasurementCoverage
from .field.tracks import TrackPoint, track_distance_m
from .layout import Layout
from .processmining.log import EventLog
from .timestudy.spaghetti import travel_report


def compare_travel(
    modeled: EventLog,
    measured_tracks: dict[str, list[TrackPoint]],
    layout: Layout,
    coverage: MeasurementCoverage,
    today: date,
) -> dict:
    """Compara el recorrido calculado contra el medido en la misma ventana.

    `today` es argumento, no `date.today()` (regla 4). Todo en la ventana
    observada, sin ningun campo anual (regla 8): si esto alimenta el caso
    economico, la anualizacion ocurre en value/levers.py::_annualize, y en
    ningun otro lado.

    `coverage` viaja siempre en la salida, incluso cuando el residual es
    saludable (regla 3): un residual sin decir cuanto vio la camara no se
    publica. Si la camara vio el 40% de los viajes, el numero sigue siendo
    util, pero solo con ese 40% al lado.

    Recibe las pistas crudas y no un `EventLog` medido porque la distancia
    MEDIDA no se puede recuperar de un `EventLog`: el log solo guarda las
    paradas, no el camino entre ellas -- y ese camino es justamente lo que el
    modelo no sabe. `track_distance_m` mide la distancia real entre muestras
    consecutivas de la camara, sin rutear por el layout; `travel_report` mide
    la distancia que el modelo calcula rutenado sobre el layout. La resta de
    esos dos numeros es el hallazgo.
    """
    t = travel_report(modeled, layout)
    modelado_m = float(t["distance_m"].sum())
    medido_m = float(sum(track_distance_m(p) for p in measured_tracks.values()))

    residual = None
    if modelado_m > 0 and measured_tracks:
        residual = round((medido_m / modelado_m - 1) * 100, 1)

    return {
        "modeled_m_in_window": round(modelado_m, 1),
        "measured_m_in_window": round(medido_m, 1),
        "residual_pct": residual,
        "orders_modeled": int(len(t)),
        "orders_measured": int(len(measured_tracks)),
        # Regla 3: la cobertura viaja pegada al numero, no en otro archivo.
        "coverage_note": coverage.note(),
        "today": today.isoformat(),
    }
