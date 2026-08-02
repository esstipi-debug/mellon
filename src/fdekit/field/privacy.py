"""Regla 9: el sensor ve al operador; el archivo que sale del sensor, no.

La agregacion no es una promesa en un documento: es una propiedad del codigo,
verificada por `tests/test_field_privacy.py`. Esa distincion es el argumento
central del toolkit — casi todos los vendors venden vigilancia disfrazada de
productividad; aca la medicion viene con olvido disenado.

Limite conocido: con dos operadores por zona el umbral k no impide deducir
quien es quien. Lo mitiga, no lo elimina. Ver seccion 6 del spec.

Postura de `assert_no_identity` (ronda de arreglo 4): las tres rondas
anteriores agrandaron la funcion —DataFrame, Series, dataclass, namedtuple,
objetos con `__dict__`— y cada review encontro un vecino nuevo sin cubrir
(indice de Series, MultiIndex, indice de DataFrame, `property`, `__getattr__`,
`pd.Categorical`, callables). El diagnostico de esta ronda es que el problema
no era la lista de tipos sino la ambicion: estabamos construyendo un escaner
de proposito general para cualquier objeto Python, y nadie lo necesita. Los
dos unicos consumidores del toolkit le pasan estructuras JSON-simples.

Por eso esta ronda BORRA codigo en vez de agregarlo. `assert_no_identity`
entiende contenedores simples y escalares simples, y rechaza todo lo demas
pidiendo `canonicalize()`. La superficie chica es lo que hace la garantia
demostrable en vez de aspiracional: se puede enumerar en una lista corta todo
lo que la funcion sabe leer, y todo lo que no esta en esa lista no pasa.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import os
import re
from decimal import Decimal

SALT_BYTES = 16
_PSEUDONYM_HEX = 12
_PSEUDONYM_RE = re.compile(r"^sub-[0-9a-f]{12}\Z")

_RECURSION_ERROR_MSG = (
    "la estructura es demasiado profunda para certificarla (se alcanzo el "
    "limite de recursion de Python). Achatar la estructura o convertir con "
    "privacy.canonicalize() antes de reintentar."
)

# Nombres de campo que, si aparecen en una salida, significan que algo se
# escapo. La lista es deliberadamente amplia: un falso positivo cuesta un
# renombre, un falso negativo cuesta el despliegue.
#
# Ronda 4: se saco "name" y se reemplazo por variantes especificas. "name" es
# demasiado generico — el nombre de una zona, de un archivo o de una ubicacion
# no es identidad personal, y tenerlo en la lista hacia fallar cualquier dict
# con una clave "name" inocua. Un falso positivo que dispara siempre entrena a
# la gente a desactivar la verificacion, que es peor que no tenerla.
IDENTITY_FIELDS = frozenset(
    {
        "marker_id",
        "sensor_id",
        "resource_raw",
        "operator",
        "operator_id",
        "operator_name",
        "worker_name",
        "employee_name",
        "full_name",
        "nombre",
        "rut",
    }
)

# Campos que SI pueden aparecer, pero cuyo valor tiene que tener forma de
# seudonimo. Es la mitad que no falla abierto: un id crudo en la ranura del
# seudonimo se detecta aunque nadie haya listado ese nombre de campo.
PSEUDONYM_FIELDS = frozenset({"resource", "subject"})


class AnonymityError(ValueError):
    """Se intento emitir algo que identifica a una persona."""


def new_session_salt() -> bytes:
    """Sal de sesion, en memoria y nunca persistida.

    Que no se guarde es el punto: sin la sal, el mapeo seudonimo -> marcador no
    se puede reconstruir manana. La irreversibilidad es por diseno, no por
    promesa.
    """
    return os.urandom(SALT_BYTES)


def pseudonymize(raw_id: str, salt: bytes) -> str:
    digest = hashlib.blake2b(raw_id.encode("utf-8"), salt=salt, digest_size=8).hexdigest()
    return f"sub-{digest[:_PSEUDONYM_HEX]}"


@dataclasses.dataclass(frozen=True)
class AnonymityGate:
    """Analoga a la compuerta de volumen de la fase 4 de `decide`.

    Bajo k sujetos distintos, un "agregado por zona" es un individuo con otro
    nombre. k=3 es un default sin evidencia — ver D3 en el spec.
    """

    k: int = 3

    def allows(self, n_subjects: int) -> bool:
        return n_subjects >= self.k

    def check(self, n_subjects: int, what: str) -> None:
        if not self.allows(n_subjects):
            raise AnonymityError(
                f"'{what}' cubre {n_subjects} sujeto(s) y el umbral es {self.k}. "
                "Un agregado bajo el umbral identifica. Ampliar la ventana temporal, "
                "combinar multiples zonas, o esperar a tener mas sujetos."
            )


def _try_import_pandas():
    """Import perezoso: el modulo no debe requerir pandas para cargar."""
    try:
        import pandas as pd

        return pd
    except ImportError:
        return None


def _try_import_numpy():
    """Import perezoso: el modulo no debe requerir numpy para cargar."""
    try:
        import numpy as np

        return np
    except ImportError:
        return None


def _is_field_name(label: object) -> bool:
    """Una etiqueta sirve como nombre de campo si es str, o tupla de str.

    La tupla es el caso de un MultiIndex: `("meta", "marker_id")` sigue siendo
    un nombre de campo, solo que compuesto. Un entero no: es una posicion.
    """
    if isinstance(label, str):
        return True
    return isinstance(label, tuple) and bool(label) and all(isinstance(x, str) for x in label)


def canonicalize(obj: object) -> object:
    """Convierte pandas a estructura JSON-simple (dict/lista/escalar).

    Es la contraparte de que `assert_no_identity` haya dejado de entender
    pandas: quien tiene un `DataFrame` o una `Series` lo pasa por aca primero,
    y la verificacion opera despues sobre dicts y listas. La conversion es
    idempotente sobre estructuras que ya son simples, asi que se puede llamar
    sin saber que tipo llega.

    El `DataFrame` resetea el indice ANTES de convertir a records. Eso no es
    cosmetico: `reset_index()` convierte las etiquetas del indice en columnas
    comunes, asi que `df.set_index("marker_id")` —que de otra forma queda
    escondido en el indice— termina siendo una clave "marker_id" que
    `assert_no_identity` si sabe leer, sin codigo especial.

    Una `Series` posicional (indice de enteros, sin nombres de campo) se
    RECHAZA en vez de convertirse. Convertirla producia un dict
    `{0: "MARKER-07", 1: "MARKER-08"}`, sin la asociacion campo -> valor de la
    que depende toda la deteccion, y `assert_no_identity` despues certificaba
    limpio un diccionario con dos identificadores crudos adentro. El flujo que
    producia ese falso negativo era exactamente el que recomienda el mensaje de
    error de `assert_no_identity`, asi que la unica salida segura es no
    convertirla.
    """
    pd = _try_import_pandas()
    np = _try_import_numpy()
    return _canonicalize_impl(obj, pd, np)


def _canonicalize_impl(obj: object, pd, np) -> object:
    if pd is not None and isinstance(obj, pd.DataFrame):
        registros = obj.reset_index().to_dict("records")
        return [_canonicalize_impl(reg, pd, np) for reg in registros]

    if pd is not None and isinstance(obj, pd.Series):
        return _canonicalize_series(obj, pd, np)

    if isinstance(obj, dict):
        return {clave: _canonicalize_impl(valor, pd, np) for clave, valor in obj.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_canonicalize_impl(item, pd, np) for item in obj]

    if _is_understood_scalar(obj, pd, np):
        return obj

    raise AnonymityError(
        f"canonicalize no sabe convertir un {type(obj).__name__}. Solo convierte "
        "pandas.DataFrame y pandas.Series con etiquetas, y deja pasar dicts, "
        "listas, tuplas, conjuntos y escalares simples. Armar un dict con "
        "nombres de campo explicitos antes de emitir."
    )


def _canonicalize_series(serie, pd, np) -> dict:
    """Convierte una `Series` con etiquetas a un dict plano etiqueta -> valor.

    Plano a proposito: envolver en `{"name": ..., "values": ...}` metia una
    clave "name" inventada por la conversion, que despues chocaba con la
    verificacion de campos y hacia fallar toda Series con nombre. El nombre de
    la Series se verifica aca —si identifica, se levanta— y no se propaga al
    resultado.
    """
    _check_key_for_identity(serie.name)

    etiquetas = list(serie.index)
    if not all(_is_field_name(etiqueta) for etiqueta in etiquetas):
        raise AnonymityError(
            "una pandas.Series posicional (indice sin nombres de campo) no se "
            "puede certificar: sin el nombre del campo no hay forma de saber si "
            "un valor es un identificador. Pasar un DataFrame, o un dict con "
            "nombres de campo explicitos."
        )

    return {etiqueta: _canonicalize_impl(valor, pd, np) for etiqueta, valor in serie.items()}


def _check_key_for_identity(key: object) -> None:
    """Revisa un nombre de campo (o una tupla de MultiIndex) contra IDENTITY_FIELDS.

    Si `key` es una tupla —el caso de una clave que quedo compuesta al aplanar
    un MultiIndex via `canonicalize`, tipo ("meta", "marker_id")— se verifica
    CADA ELEMENTO por separado. Comparar la tupla entera contra IDENTITY_FIELDS
    nunca matchea, porque el conjunto contiene strings sueltos: ese fue el
    agujero de la ronda 2.
    """
    if key is None:
        return
    candidatos = key if isinstance(key, tuple) else (key,)
    for candidato in candidatos:
        if candidato in IDENTITY_FIELDS:
            raise AnonymityError(
                f"el campo '{candidato}' identifica y no puede cruzar el borde "
                "(regla 9). Pseudonimizar con privacy.pseudonymize antes de emitir."
            )


def _key_matches_pseudonym(key: object) -> bool:
    if key is None:
        return False
    candidatos = key if isinstance(key, tuple) else (key,)
    return any(candidato in PSEUDONYM_FIELDS for candidato in candidatos)


def _is_valid_pseudonym_value(val: object, pd) -> bool:
    """Valida que un valor sea valido en un campo de PSEUDONYM_FIELDS.

    None y pd.NA/NaT son permitidos a proposito: `EventLog.__init__` rellena
    columnas opcionales ausentes con pd.NA, y prohibir el nulo rompe logs
    perfectamente validos. Un string debe tener forma de seudonimo. Todo lo
    demas (enteros, objetos arbitrarios, strings con basura extra) es
    sospechoso y se rechaza.
    """
    if val is None:
        return True

    if pd is not None:
        try:
            if pd.isna(val):
                return True
        except (TypeError, ValueError):
            pass

    if isinstance(val, str):
        return _PSEUDONYM_RE.match(val) is not None

    return False


def _is_understood_scalar(val: object, pd, np) -> bool:
    """Escalares cuya forma se conoce y no hace falta recorrer mas.

    Incluye numpy.str_ (subclase de str, cubierta por el isinstance de str) y
    pandas.Timestamp (subclase de datetime.datetime, cubierta por ese check).
    """
    if val is None:
        return True

    if isinstance(val, (str, bytes, int, float, bool, complex, Decimal)):
        return True

    if isinstance(val, (dt.datetime, dt.date)):
        return True

    if np is not None and isinstance(val, np.generic):
        return True

    if pd is not None:
        try:
            if pd.isna(val):
                return True
        except (TypeError, ValueError):
            return False

    return False


def _check_mapping_items(items, visited_ids: set, keep_alive: list, pd, np) -> None:
    """Cada clave se revisa; el valor se valida o se recorre.

    `items` es un iterable de pares (clave, valor). Cada clave se revisa
    contra IDENTITY_FIELDS; si cae en PSEUDONYM_FIELDS se valida su forma en
    vez de recorrerla; si no, se recursa.
    """
    for clave, valor in items:
        _check_key_for_identity(clave)
        if _key_matches_pseudonym(clave):
            if not _is_valid_pseudonym_value(valor, pd):
                raise AnonymityError(
                    f"el campo '{clave}' contiene un valor que no es seudonimo "
                    f"valido (valor: {valor!r}). Pseudonimizar con "
                    "privacy.pseudonymize antes de emitir."
                )
        else:
            _assert_no_identity_impl(valor, visited_ids, keep_alive, pd, np)


def assert_no_identity(payload: object) -> None:
    """Recorre la salida completa y falla si sobrevivio un identificador.

    Entiende una lista corta y cerrada de formas, y rechaza todo lo demas:

    1. Contenedores -> se recorren: `dict` y sus subclases (`defaultdict`,
       `OrderedDict`, `Counter`), `list`, `tuple`, `set`, `frozenset`.
    2. Escalares -> se validan y se termina: `str` (incluido `numpy.str_`),
       `int`, `float`, `bool`, `complex`, `bytes`, `None`, NaN/`pd.NA`/`NaT`,
       escalares de numpy, `datetime`/`date`/`pd.Timestamp`, `Decimal`.
    3. Cualquier otra cosa -> `AnonymityError`, nombrando el tipo concreto y
       pidiendo convertirlo con `canonicalize()` antes de emitir. Eso incluye
       `DataFrame`, `Series`, dataclasses, objetos comunes y callables.

    Por que se achico (ronda 4): las rondas 1 a 3 fueron agrandando la funcion
    para entender pandas, dataclasses, namedtuples y objetos con `__dict__`, y
    cada review encontro un vecino nuevo sin cubrir — `property`,
    `__getattr__`, `pd.Categorical`, callables. La rama de `__dict__` en
    particular quedo como cajon de sastre que certificaba limpio cualquier
    objeto cuyos datos no vivieran literalmente en `vars()`. El problema de
    fondo era la ambicion: un escaner de proposito general para cualquier
    objeto Python no se puede terminar, porque el universo de tipos es abierto.
    Los dos unicos consumidores del toolkit pasan estructuras JSON-simples
    (`log.df.to_dict("records")` y un dict de resultados), asi que la funcion
    entiende exactamente eso. Con la superficie chica, la garantia se vuelve
    demostrable: se puede enumerar todo lo que la funcion sabe leer, y todo lo
    que queda afuera se rechaza a proposito, no por descuido.

    Campos en PSEUDONYM_FIELDS: si el valor es string, debe coincidir con la
    forma de seudonimo (sub-<12 hex>). Se permiten explicitamente None y pd.NA
    porque EventLog rellena columnas opcionales ausentes con pd.NA, y prohibir
    el nulo rompe logs perfectamente validos. Todo lo demas levanta.

    Las claves compuestas (tuplas, lo que produce `canonicalize` a partir de
    columnas MultiIndex) se verifican elemento por elemento: `("meta",
    "marker_id")` identifica igual que `"marker_id"`.

    Una estructura demasiado profunda hace que Python levante RecursionError;
    esta funcion lo traduce a AnonymityError en vez de dejarlo propagarse
    crudo, porque el contrato es "devuelve None o levanta AnonymityError", y
    un tercer modo de falla rompe a quien solo captura AnonymityError.
    """
    pd = _try_import_pandas()
    np = _try_import_numpy()
    try:
        _assert_no_identity_impl(payload, set(), [], pd, np)
    except RecursionError as exc:
        raise AnonymityError(_RECURSION_ERROR_MSG) from exc


def _assert_no_identity_impl(payload: object, visited_ids: set, keep_alive: list, pd, np) -> None:
    """Implementacion interna: clasifica, recorre o rechaza.

    `visited_ids` guarda id(objeto) de los contenedores ya visitados para no
    entrar en bucle con estructuras ciclicas. `keep_alive` guarda una
    referencia fuerte a cada uno mientras dura la llamada: sin eso, un
    contenedor efimero podria liberarse durante la recursion y otro objeto
    reusar su id(), saltandose la revision. Es un riesgo teorico, pero el
    arreglo es de una linea y el costo es cero.
    """
    if isinstance(payload, dict):
        if _ya_visitado(payload, visited_ids, keep_alive):
            return
        _check_mapping_items(payload.items(), visited_ids, keep_alive, pd, np)
        return

    if isinstance(payload, (list, tuple, set, frozenset)):
        if _ya_visitado(payload, visited_ids, keep_alive):
            return
        for item in payload:
            _assert_no_identity_impl(item, visited_ids, keep_alive, pd, np)
        return

    if _is_understood_scalar(payload, pd, np):
        return

    raise AnonymityError(
        f"tipo no reconocido ({type(payload).__name__}): assert_no_identity solo "
        "certifica dicts, listas, tuplas, conjuntos y escalares simples, y no "
        "puede garantizar que no hay identidad escondida en este tipo. "
        "Convertir con privacy.canonicalize() a una estructura simple antes de "
        "emitir."
    )


def _ya_visitado(payload: object, visited_ids: set, keep_alive: list) -> bool:
    obj_id = id(payload)
    if obj_id in visited_ids:
        return True
    visited_ids.add(obj_id)
    keep_alive.append(payload)
    return False
