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
bueno ahi es justo el que hay que desconfiar -- y `residual_flag` existe para
que esa desconfianza no dependa de que alguien lea este docstring en
produccion.

Ronda de arreglo 1 (revision del coordinador) encontro dos bugs de la misma
familia que el bug de anualizacion, con otra ropa:

1. Comparar TOTALES cuando `orders_modeled` y `orders_measured` difieren suma
   ventanas con distinto denominador -- 100 pedidos modelados contra 40
   medidos, con el MISMO recorrido por pedido, daba un residual de -60% en vez
   de 0%. El residual se calcula sobre TASAS por pedido (metros / pedidos),
   nunca sobre los totales crudos. Los totales siguen expuestos porque son
   utiles para otras cuentas (p.ej. metros/dia), pero `totals_note` advierte
   explicitamente que no son comparables entre si cuando los conteos difieren.

2. `Layout.route_distance` arma toda ruta modelada como
   `[DOCK, *paradas, DOCK]`: los dos tramos al muelle siempre estan en el
   total. Una camara que cubre solo la zona de estanterias -- lo normal, mira
   un area, no toda la planta -- no los ve, y el residual termina midiendo
   cobertura geometrica de la camara ademas de error del modelo. No se puede
   segmentar la pista por cercania al DOCK sin trabajo de etapa 3, asi que en
   vez de resolverlo esta version lo hace VISIBLE: `dock_legs_m_in_window` y
   `dock_legs_pct_of_modeled` dicen cuanto de lo modelado es tramo al muelle,
   para que quien lea el residual pueda decidir si mide error de modelo o
   ceguera de camara.
"""

from __future__ import annotations

from datetime import date

from .field.coverage import MeasurementCoverage
from .field.tracks import TrackPoint, track_distance_m
from .layout import DOCK, Layout
from .processmining.log import EventLog
from .timestudy.spaghetti import _pick_paths, travel_report

# "Cercano a cero" (docstring del modulo): un residual dentro de este margen,
# incluido el lado negativo, se marca sospechoso en vez de esperado. El modelo
# es un piso -- solo puede subestimar -- asi que un residual chico no es un
# empate limpio, es la zona donde ruido de medicion (pistas cortadas,
# homografia corrida un par de puntos) y error real del modelo se vuelven
# indistinguibles. El numero es una eleccion conservadora, no una medicion:
# baja el margen y vas a marcar "esperado" residuales que en realidad son
# ruido de medicion; subilo mucho y vas a marcar "sospechoso" hallazgos reales
# pero chicos.
MARGEN_SOSPECHOSO_PCT = 5.0

FLAG_ESPERADO = "esperado"
FLAG_SOSPECHOSO = "sospechoso"
FLAG_SIN_MEDICION = "sin_medicion"
FLAG_MODELO_NO_VIO_NADA = "modelo_no_vio_nada"

_MOTIVO_POR_FLAG = {
    FLAG_ESPERADO: (
        "el residual es positivo, coherente con que el modelo es un piso: no "
        "ve retrocesos, ni el tramo de la excepcion, ni congestion entre "
        "pickers, asi que subestimar el recorrido real es lo normal"
    ),
    FLAG_SOSPECHOSO: (
        "el residual es negativo o esta cerca de cero; como el modelo solo "
        "puede subestimar, esto NO dice que el modelo es preciso -- apunta a "
        "un problema de medicion (pistas cortadas, cobertura baja, "
        "homografia mal calibrada). Revisar coverage_note y "
        "dock_legs_pct_of_modeled antes de confiar en este numero"
    ),
    FLAG_SIN_MEDICION: "no hay pistas medidas en la ventana, no se puede calcular un residual",
    FLAG_MODELO_NO_VIO_NADA: (
        "el modelo predice cero metros pero la camara midio recorrido: es el "
        "hallazgo mas fuerte que este modulo puede producir -- recorrido "
        "100% invisible al WMS, no un error de redondeo"
    ),
}


def _dock_legs_m(modeled: EventLog, layout: Layout) -> float:
    """Metros modelados de los tramos DOCK<->primera parada y ultima<->DOCK.

    `Layout.route_distance` arma toda ruta como `[DOCK, *paradas, DOCK]`: esos
    dos tramos estan SIEMPRE en el total modelado, sin importar si la camara
    los vio. Separarlos es lo que permite distinguir "el modelo se equivoca"
    de "la camara no cubre el muelle" -- ver el punto 2 del docstring del
    modulo.
    """
    paths = _pick_paths(modeled)
    total = 0.0
    for stops in paths.values():
        if not stops:
            continue
        total += layout.distance(DOCK, stops[0]) + layout.distance(stops[-1], DOCK)
    return total


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
    ningun otro lado -- ni siquiera en `modeled_m_per_order`, que es un
    promedio de la ventana observada, no una tasa anualizada.

    `coverage` viaja siempre en la salida, incluso cuando el residual es
    saludable (regla 3): un residual sin decir cuanto vio la camara no se
    publica. Si la camara vio el 40% de los viajes, el numero sigue siendo
    util, pero solo con ese 40% al lado.

    Recibe las pistas crudas y no un `EventLog` medido porque la distancia
    MEDIDA no se puede recuperar de un `EventLog`: el log solo guarda las
    paradas, no el camino entre ellas -- y ese camino es justamente lo que el
    modelo no sabe. `track_distance_m` mide la distancia real entre muestras
    consecutivas de la camara, sin rutear por el layout; `travel_report` mide
    la distancia que el modelo calcula ruteando sobre el layout. La resta de
    esos dos numeros es el hallazgo -- pero la resta correcta es entre TASAS
    por pedido, no entre totales (ver el punto 1 del docstring del modulo):
    `orders_modeled` y `orders_measured` casi nunca coinciden (la camara no
    ve todos los viajes, regla 3), y sumar metros de ventanas con distinto
    numero de pedidos y despues restar los totales compara cosas de tamano
    distinto -- exactamente el bug de anualizacion, con otra ropa.

    `residual_flag` existe porque el numero desnudo invita a leerlo al reves:
    el modelo es un piso (ver docstring del modulo), asi que un residual
    negativo o chico no es un modelo preciso, es una medicion sospechosa. El
    caso `modelo_no_vio_nada` (modelo predice cero, camara midio algo) es
    distinto de `sin_medicion` (no hay pistas): el primero es el hallazgo mas
    fuerte posible -- recorrido invisible al WMS -- y antes de este arreglo
    se descartaba en silencio junto con el segundo.
    """
    t = travel_report(modeled, layout)
    modelado_m = float(t["distance_m"].sum())
    orders_modeled = int(len(t))
    orders_measured = int(len(measured_tracks))
    medido_m = float(sum(track_distance_m(p) for p in measured_tracks.values()))

    modelado_por_pedido = modelado_m / orders_modeled if orders_modeled else None
    medido_por_pedido = medido_m / orders_measured if orders_measured else None

    residual = None
    if not measured_tracks:
        flag = FLAG_SIN_MEDICION
    elif not modelado_por_pedido:
        # orders_modeled == 0 (no hay pedidos modelados en la ventana) o el
        # modelo calculo distancia cero: en cualquiera de los dos casos no
        # hay denominador valido para una tasa, pero SI hay medicion -- el
        # hallazgo mas fuerte posible, no un residual indefinido cualquiera.
        flag = FLAG_MODELO_NO_VIO_NADA
    else:
        residual = round((medido_por_pedido / modelado_por_pedido - 1) * 100, 1)
        flag = FLAG_ESPERADO if residual > MARGEN_SOSPECHOSO_PCT else FLAG_SOSPECHOSO

    dock_legs_m = _dock_legs_m(modeled, layout)
    dock_legs_pct = round(dock_legs_m / modelado_m * 100, 1) if modelado_m > 0 else None

    return {
        "modeled_m_in_window": round(modelado_m, 1),
        "measured_m_in_window": round(medido_m, 1),
        "modeled_m_per_order": (
            round(modelado_por_pedido, 1) if modelado_por_pedido is not None else None
        ),
        "measured_m_per_order": (
            round(medido_por_pedido, 1) if medido_por_pedido is not None else None
        ),
        "totals_note": (
            "modeled_m_in_window y measured_m_in_window NO son comparables "
            "entre si en forma directa cuando orders_modeled y "
            "orders_measured difieren: son sumas sobre distinta cantidad de "
            "pedidos. Comparar siempre modeled_m_per_order contra "
            "measured_m_per_order -- de ahi sale residual_pct"
        ),
        "residual_pct": residual,
        "residual_flag": flag,
        "residual_flag_reason": _MOTIVO_POR_FLAG[flag],
        "orders_modeled": orders_modeled,
        "orders_measured": orders_measured,
        "dock_legs_m_in_window": round(dock_legs_m, 1),
        "dock_legs_pct_of_modeled": dock_legs_pct,
        # Regla 3: la cobertura viaja pegada al numero, no en otro archivo.
        "coverage_note": coverage.note(),
        "today": today.isoformat(),
    }
