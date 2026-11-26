"""Catalogo base de guardias de integridad de datos operativos.

Cada guardia viaja con sus dos fabricas de prueba: el objeto sano y el mismo
objeto con el defecto que el guardia tiene que atrapar. `medir_catalogo` corre
la sonda de dos corridas sobre cada uno y publica el resultado en
`CoberturaGuardia`: un guardia del catalogo que no detecta su propia mutacion
aparece en la nota con su veredicto.

Las filas son `Sequence[Mapping]`, la forma en que llega un extracto CSV leido
con `csv.DictReader`. Stdlib pura (regla 2): sin pandas.

Un valor ausente, vacio, NaN o que no es numero hace REVENTAR al predicado, y
`evaluar` lo reporta como guardia roto con su motivo. Leerlo como sano seria la
mentira que la regla 3 prohibe: "no pude mirar" no es "mire y estaba bien".
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from .cobertura import CoberturaGuardia
from .guardia import Guardia
from .hallazgo import Hallazgo, Procedencia
from .sonda import Veredicto, sonda_guardia

Filas = Sequence[Mapping[str, object]]

_DUENO = "stipi"
# audit_assertions_sap.sql tal como estaba en daf8ccb, con los defectos que tres
# de estos guardias generalizan (A3 y A5).
_SQL = Procedencia(commit="daf8ccb", fecha=date(2026, 10, 24), dueno=_DUENO)
# "fix: anualizar una sola vez, en value/levers" (regla 8).
_ANUALIZACION = Procedencia(commit="b2267bd", fecha=date(2026, 8, 2), dueno=_DUENO)

_TOLERANCIA = 1e-9


def _numero(fila: Mapping[str, object], columna: str) -> float:
    """El valor como numero finito, o revienta. `nan < 0` es falso e `inf >= 0`
    es verdadero: sin este cuidado los dos pasarian como sanos, y un infinito
    suele salir de una division por cero aguas arriba."""
    valor = fila[columna]
    if isinstance(valor, bool):
        raise ValueError(f"{columna}={valor!r} es un booleano, no una cantidad")
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{columna}={valor!r} no es un numero") from None
    if not math.isfinite(numero):
        raise ValueError(f"{columna}={valor!r} no es un numero finito")
    return numero


def _codigo(valor: object) -> str:
    """Un codigo de movimiento como texto: 103, 103.0 y ' 103' son '103'. Desde
    pandas, una columna de codigos llega como entero (o como float si tiene
    vacios). Vacio, None o NaN revientan: sin codigo la fila no se puede ubicar."""
    if isinstance(valor, float):
        if math.isnan(valor):
            raise ValueError("tipo de movimiento NaN")
        if valor.is_integer():
            valor = int(valor)
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        raise ValueError(f"tipo de movimiento vacio: {valor!r}")
    return texto


def _codigos(codigos: Iterable[object], nombre: str) -> frozenset[str]:
    """Los codigos declarados. Un texto suelto ('103') se leeria letra por letra
    como los codigos '1', '0' y '3': un guardia que aprueba todo."""
    if isinstance(codigos, (str, bytes)):
        raise TypeError(f"{nombre} tiene que ser una lista de codigos, no el texto {codigos!r}")
    return frozenset(_codigo(c) for c in codigos)


def _lista(clave: Sequence[str]) -> str:
    return ", ".join(clave)


def sin_fanout(clave: Sequence[str]) -> Guardia:
    """La clave no se repite: ningun cruce 1:N multiplico las filas."""
    clave = tuple(clave)

    def predicado(filas: Filas) -> bool:
        if not filas:
            raise ValueError("sin_fanout recibio 0 filas: no hubo nada que medir")
        tuplas = []
        for f in filas:
            valores_clave = []
            for c in clave:
                valor = f[c]
                if valor is None or (isinstance(valor, str) and not valor.strip()):
                    raise ValueError(f"campo de clave {c!r} vacio o nulo")
                valores_clave.append(valor)
            tuplas.append(tuple(valores_clave))
        conteo = Counter(tuplas)
        return all(n == 1 for n in conteo.values())

    return Guardia(
        nombre=f"sin_fanout({_lista(clave)})",
        motivo=(
            "EKPO cruzado con EKET sin agregar repetia la linea de OC una vez por "
            "reparto: tres repartos, tres filas y la caja destruida sumada tres veces "
            "(asercion 3 de audit_assertions_sap.sql)"
        ),
        hallazgo=Hallazgo(
            regla=f"una fila por ({_lista(clave)})",
            evidencia="la clave se repite: un cruce 1:N multiplico las filas",
            procedencia=_SQL,
            familia="fanout",
        ),
        predicado=predicado,
    )


def conservacion_de_masa(
    clave: Sequence[str],
    cantidad: str,
    movimiento: str,
    entradas: Iterable[str],
    salidas: Iterable[str],
) -> Guardia:
    """Por clave, lo que sale no supera lo que entro.

    Los movimientos que no estan en `entradas` ni en `salidas` no son de esta
    cadena y no cuentan. Un tipo en las dos listas es ambiguo y no se construye.
    Los codigos se comparan como texto normalizado (ver `_codigo`). Revienta,
    en vez de dar sano, si una fila no trae codigo o si hay filas pero ninguna
    es de la cadena: en los dos casos el guardia no vio lo que tenia que vigilar.
    """
    clave = tuple(clave)
    entran, salen = _codigos(entradas, "entradas"), _codigos(salidas, "salidas")
    if entran & salen:
        raise ValueError(f"movimientos en entradas y salidas a la vez: {sorted(entran & salen)}")
    cadena = f"{', '.join(sorted(entran))} -> {', '.join(sorted(salen))}"

    def predicado(filas: Filas) -> bool:
        saldo: dict[tuple, float] = defaultdict(float)
        for f in filas:
            tipo = _codigo(f[movimiento])
            if tipo in entran:
                qty = _numero(f, cantidad)
                if qty < 0:
                    raise ValueError(f"{cantidad}={qty} es negativo en cadena {cadena}")
                saldo[tuple(f[c] for c in clave)] += qty
            elif tipo in salen:
                qty = _numero(f, cantidad)
                if qty < 0:
                    raise ValueError(f"{cantidad}={qty} es negativo en cadena {cadena}")
                saldo[tuple(f[c] for c in clave)] -= qty
        if len(filas) and not saldo:
            raise ValueError(f"ninguna fila es de la cadena {cadena}: no hubo nada que medir")
        return all(s >= -_TOLERANCIA for s in saldo.values())

    return Guardia(
        nombre=f"conservacion_de_masa({_lista(clave)})",
        motivo=(
            "por linea de OC, lo liberado (105) y lo devuelto (124) no puede superar lo "
            "recibido (103): la conservacion de masa de la asercion 5 de "
            "audit_assertions_sap.sql, mirada por clave y no por ventana de fechas"
        ),
        hallazgo=Hallazgo(
            regla=(f"por ({_lista(clave)}): salidas ({', '.join(sorted(salen))}) <= "
                   f"entradas ({', '.join(sorted(entran))})"),
            evidencia="en al menos una clave sale mas de lo que entro",
            procedencia=_SQL,
            familia="conservacion_de_masa",
        ),
        predicado=predicado,
    )


def no_negativo(columnas: Sequence[str]) -> Guardia:
    """Ningun valor de estas columnas es negativo; uno ilegible hace reventar."""
    columnas = tuple(columnas)

    def predicado(filas: Filas) -> bool:
        return all(_numero(f, c) >= 0 for f in filas for c in columnas)

    return Guardia(
        nombre=f"no_negativo({_lista(columnas)})",
        motivo=(
            "la asercion 3 divide la cantidad por la tasa de consumo: una tasa negativa "
            "da cobertura negativa, nunca supera los 90 dias y la OC pasa como sana. Un "
            "stock o un lead time negativo es el mismo error de signo"
        ),
        hallazgo=Hallazgo(
            regla=f"{_lista(columnas)} >= 0",
            evidencia="hay un valor negativo",
            procedencia=_SQL,
            familia="no_negatividad",
        ),
        predicado=predicado,
    )


def _claves(obj: object) -> Iterator[str]:
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            yield str(k)
            yield from _claves(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _claves(v)


def una_sola_anualizacion() -> Guardia:
    """Ningun hallazgo llega anualizado: la unica anualizacion es la de value/levers."""
    tokens = ("annual", "anual", "per_year", "por_ano")
    return Guardia(
        nombre="una_sola_anualizacion",
        motivo=(
            "el kit emitia claves ya anualizadas, con un 250 hardcodeado, y value/levers "
            "las volvia a escalar por los dias de operacion: la anualizacion se aplicaba "
            "dos veces, en silencio (regla 8)"
        ),
        hallazgo=Hallazgo(
            regla="ningun hallazgo trae una clave anualizada antes de value/levers",
            evidencia="una clave anualizada llego antes de value/levers",
            procedencia=_ANUALIZACION,
            familia="anualizacion",
        ),
        predicado=lambda hallazgos: not any(
            any(tok in k.lower() for tok in tokens) for k in _claves(hallazgos)
        ),
    )


@dataclass(frozen=True)
class Entrada:
    """Un guardia del catalogo con las dos fabricas de su sonda."""

    guardia: Guardia
    fabrica_sano: Callable[[], object]
    fabrica_mutado: Callable[[], object]


def _oc(lineas: dict[str, int]) -> list[dict[str, object]]:
    """Filas de EKPO cruzado con EKET: una por reparto de cada linea de OC."""
    return [
        {"mandt": "100", "ebeln": "4500000001", "ebelp": ebelp, "etenr": f"{i:04d}"}
        for ebelp, repartos in lineas.items()
        for i in range(1, repartos + 1)
    ]


def _recepcion(liberado: float) -> list[dict[str, object]]:
    linea = {"mandt": "100", "ebeln": "4500000002", "ebelp": "00010"}
    return [
        {**linea, "bwart": "103", "menge": 50.0},
        {**linea, "bwart": "105", "menge": liberado},
        {**linea, "bwart": "124", "menge": 20.0},
    ]


def _inventario(stock_b: float) -> list[dict[str, object]]:
    return [
        {"matnr": "MAT-A", "stock": 120.0, "lead_time_dias": 30.0},
        {"matnr": "MAT-B", "stock": stock_b, "lead_time_dias": 12.0},
    ]


def _hallazgos(clave_viaje: str) -> dict[str, object]:
    return {
        "travel": [{clave_viaje: 12.5}],
        "rework": [{"hours_lost_in_window": 3.0}],
    }


_LINEA_DE_OC = ("mandt", "ebeln", "ebelp")

CATALOGO: tuple[Entrada, ...] = (
    Entrada(
        sin_fanout(_LINEA_DE_OC),
        lambda: _oc({"00010": 1, "00020": 1}),
        lambda: _oc({"00010": 3, "00020": 1}),
    ),
    Entrada(
        conservacion_de_masa(_LINEA_DE_OC, "menge", "bwart", entradas=("103",),
                             salidas=("105", "124")),
        lambda: _recepcion(liberado=30.0),
        lambda: _recepcion(liberado=40.0),
    ),
    Entrada(
        no_negativo(("stock", "lead_time_dias")),
        lambda: _inventario(stock_b=0.0),
        lambda: _inventario(stock_b=-5.0),
    ),
    Entrada(
        una_sola_anualizacion(),
        lambda: _hallazgos("walking_hours_in_window"),
        lambda: _hallazgos("walking_hours_annual"),
    ),
)


def medir_catalogo(catalogo: Iterable[Entrada] = CATALOGO) -> CoberturaGuardia:
    """Corre la sonda sobre cada guardia y lo publica en una CoberturaGuardia.

    Solo las familias de los guardias que DETECTAN cuentan como vigiladas.
    `bugs_atrapados` queda sin medir: detectar la mutacion propia no es atrapar
    uno de los bugs historicos.
    """
    sondas = tuple(sonda_guardia(e.guardia, e.fabrica_sano, e.fabrica_mutado) for e in catalogo)
    familias: list[str] = []
    for r in sondas:
        if r.veredicto is Veredicto.DETECTA and r.familia and r.familia not in familias:
            familias.append(r.familia)
    return CoberturaGuardia(familias_vigiladas=tuple(familias), sondas=sondas)
