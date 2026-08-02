"""Regla 9: el sensor ve al operador; el archivo que sale del sensor, no.

La agregacion no es una promesa en un documento: es una propiedad del codigo,
verificada por `tests/test_field_privacy.py`. Esa distincion es el argumento
central del toolkit — casi todos los vendors venden vigilancia disfrazada de
productividad; aca la medicion viene con olvido disenado.

Limite conocido: con dos operadores por zona el umbral k no impide deducir
quien es quien. Lo mitiga, no lo elimina. Ver seccion 6 del spec.

Postura de `assert_no_identity` (ronda de arreglo 3): tres rondas de review
encontraron, cada una, un vecino sin cubrir de la anterior (DataFrame, luego
indice de Series, luego MultiIndex e indice de DataFrame). El problema no era
un tipo puntual: era que la funcion recorria una lista negra de tipos
conocidos y, ante cualquier tipo que no reconociera, no hacia nada y volvia
limpio. Una lista negra sobre un universo abierto de tipos siempre deja un
vecino afuera. Por eso la funcion ahora falla cerrado: todo valor cae en
exactamente una de tres categorias (contenedor entendido que se recorre,
escalar entendido que se valida, o "no lo entiendo" que levanta
`AnonymityError`). Lo no reconocido se rechaza a proposito, no por descuido.
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

# Profundidad maxima "declarada": no se aplica activamente (no hay contador),
# es solo la documentacion de que el limite real es el de recursion de Python
# y que se traduce a AnonymityError en vez de propagarse crudo. Ver
# `assert_no_identity`.
_RECURSION_ERROR_MSG = (
    "la estructura es demasiado profunda para certificarla (se alcanzo el "
    "limite de recursion de Python). Achatar la estructura o convertir con "
    "privacy.canonicalize() antes de reintentar."
)

# Nombres de campo que, si aparecen en una salida, significan que algo se
# escapo. La lista es deliberadamente amplia: un falso positivo cuesta un
# renombre, un falso negativo cuesta el despliegue.
IDENTITY_FIELDS = frozenset(
    {"marker_id", "sensor_id", "resource_raw", "operator", "operator_id", "name", "rut"}
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


def canonicalize(obj: object) -> object:
    """Convierte un objeto arbitrario a estructura JSON-simple (dict/lista/escalar).

    Para quien tiene un tipo que `assert_no_identity` no reconoce y por eso
    rechaza: convertir con esta funcion antes de emitir, para que la
    verificacion opere sobre dicts, listas y escalares que si entiende.

    El DataFrame se resetea el indice ANTES de convertir a records. Eso no es
    cosmetico: `reset_index()` convierte las etiquetas del indice en columnas
    comunes, asi que `df.set_index("marker_id")` —que de otra forma queda
    escondido en el indice— termina siendo una columna "marker_id" que
    `assert_no_identity` si sabe leer, sin codigo especial.
    """
    pd = _try_import_pandas()
    return _canonicalize_impl(obj, pd)


def _canonicalize_impl(obj: object, pd) -> object:
    if pd is not None and isinstance(obj, pd.DataFrame):
        registros = obj.reset_index().to_dict("records")
        return [_canonicalize_impl(reg, pd) for reg in registros]

    if pd is not None and isinstance(obj, pd.Series):
        valores = {}
        for etiqueta, valor in obj.items():
            clave = etiqueta if not isinstance(etiqueta, tuple) else "/".join(str(x) for x in etiqueta)
            valores[clave] = _canonicalize_impl(valor, pd)
        if obj.name is not None:
            return {"name": obj.name, "values": valores}
        return valores

    if _is_namedtuple(obj):
        return {campo: _canonicalize_impl(getattr(obj, campo), pd) for campo in obj._fields}

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            campo.name: _canonicalize_impl(getattr(obj, campo.name), pd)
            for campo in dataclasses.fields(obj)
        }

    if isinstance(obj, dict):
        return {clave: _canonicalize_impl(valor, pd) for clave, valor in obj.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_canonicalize_impl(item, pd) for item in obj]

    # Escalar (o algo que ni canonicalize reconoce): se deja tal cual. Si
    # despues assert_no_identity tampoco lo reconoce, va a levantar y ese es
    # el punto: nadie certifica lo que no entiende.
    return obj


def _is_namedtuple(obj: object) -> bool:
    return (
        isinstance(obj, tuple)
        and hasattr(obj, "_fields")
        and isinstance(getattr(obj, "_fields", None), tuple)
    )


def _check_key_for_identity(key: object) -> None:
    """Revisa un nombre de campo (o una tupla de MultiIndex) contra IDENTITY_FIELDS.

    Si `key` es una tupla —el caso de una etiqueta de columna MultiIndex tipo
    ("meta", "marker_id")— se verifica CADA ELEMENTO por separado. Comparar la
    tupla entera contra IDENTITY_FIELDS nunca matchea, porque el conjunto
    contiene strings sueltos: ese fue el agujero de la ronda 2.
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
    """Logica compartida por dict, namedtuple, dataclass y objetos con __dict__.

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


def _check_axis_names(index, pd) -> None:
    """Revisa el/los nombre(s) de un Index/MultiIndex de pandas.

    Para un MultiIndex, cada nombre de nivel se revisa por separado (son las
    etiquetas de fila/columna, no valores de datos). Para un Index simple,
    `.name` es el unico nombre relevante — es lo que expone
    `df.set_index("marker_id")` o `Series(...).rename_axis("marker_id")`,
    donde el valor de cada fila es un dato (p.ej. "MARKER-07") pero el NOMBRE
    del eje es el campo prohibido.
    """
    if pd is not None and isinstance(index, pd.MultiIndex):
        for nombre_nivel in index.names:
            _check_key_for_identity(nombre_nivel)
    else:
        _check_key_for_identity(index.name)


def _check_dataframe(df, visited_ids: set, keep_alive: list, pd, np) -> None:
    """Revisa columnas (incluido MultiIndex), sus valores, y el indice de fila."""
    _check_axis_names(df.columns, pd)

    for col in df.columns:
        _check_key_for_identity(col)
        if _key_matches_pseudonym(col):
            for val in df[col]:
                if not _is_valid_pseudonym_value(val, pd):
                    raise AnonymityError(
                        f"la columna '{col}' contiene un valor que no es "
                        f"seudonimo valido (valor: {val!r}). Pseudonimizar con "
                        "privacy.pseudonymize antes de emitir."
                    )
        else:
            for val in df[col]:
                _assert_no_identity_impl(val, visited_ids, keep_alive, pd, np)

    # El indice de fila: solo el/los nombre(s) importan (ver _check_axis_names).
    # Cubre tanto `df.set_index("marker_id")` como `df.index.name = "marker_id"`.
    _check_axis_names(df.index, pd)


def _check_series(s, visited_ids: set, keep_alive: list, pd, np) -> None:
    """Revisa el indice (nombres y etiquetas), el .name, y los valores."""
    _check_axis_names(s.index, pd)

    for etiqueta in s.index:
        _check_key_for_identity(etiqueta)

    if s.name is not None:
        _check_key_for_identity(s.name)

    pseudonym_por_name = s.name is not None and _key_matches_pseudonym(s.name)

    for etiqueta, valor in s.items():
        if pseudonym_por_name or _key_matches_pseudonym(etiqueta):
            if not _is_valid_pseudonym_value(valor, pd):
                raise AnonymityError(
                    f"la serie contiene un valor que no es seudonimo valido en "
                    f"'{etiqueta}' (valor: {valor!r}). Pseudonimizar con "
                    "privacy.pseudonymize antes de emitir."
                )
        else:
            _assert_no_identity_impl(valor, visited_ids, keep_alive, pd, np)


def assert_no_identity(payload: object) -> None:
    """Recorre la salida completa y falla si sobrevivio un identificador.

    Cada valor cae en exactamente una de tres categorias:

    1. Contenedor entendido -> se recorre: dict, list, tuple, set, frozenset,
       namedtuple, dataclass, objetos con __dict__, pandas.DataFrame,
       pandas.Series.
    2. Escalar entendido -> se valida y se termina: str (incluido
       numpy.str_), int, float, bool, complex, bytes, None, NaN/pd.NA/NaT,
       escalares de numpy, datetime/date/pd.Timestamp, Decimal.
    3. Cualquier otra cosa -> AnonymityError. Un objeto con __slots__ y sin
       __dict__, o cualquier tipo que esta funcion no sepa leer, NO pasa en
       silencio: se rechaza, y el mensaje dice que convertirlo con
       `canonicalize()` antes de emitir.

    Esa tercera categoria es la que cambio en esta ronda. Antes, un tipo no
    reconocido caia al fondo de la funcion sin matchear ningun `isinstance` y
    volvia sin error — "no encontre nada malo" en vez de "revise todo lo que
    salio". Tres rondas de review mostraron que esa forma de garantia
    siempre deja un vecino sin cubrir. Fallar cerrado es el cambio de fondo.

    Campos en PSEUDONYM_FIELDS: si el valor es string, debe coincidir con la
    forma de seudonimo (sub-<12 hex>). Se permiten explicitamente None y pd.NA
    porque EventLog rellena columnas opcionales ausentes con pd.NA, y prohibir
    el nulo rompe logs perfectamente validos. Todo lo demas levanta.

    Los indices de pandas.Series se revisan etiqueta por etiqueta (son los
    nombres de campo cuando la Series viene de un dict o de una fila de
    DataFrame). Los indices de pandas.DataFrame se revisan solo por su(s)
    nombre(s) de eje, MultiIndex incluido, con cada elemento de las tuplas de
    columna MultiIndex verificado por separado.

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

    `visited_ids` guarda id(objeto) para no entrar en bucle con estructuras
    ciclicas. `keep_alive` guarda una referencia fuerte a cada objeto
    visitado mientras dura la llamada: sin eso, un objeto efimero podria
    liberarse durante la recursion y otro objeto reusar su id(), saltandose
    la revision. Es un riesgo teorico, pero el arreglo es de una linea y el
    costo es cero.
    """
    obj_id = id(payload)
    if obj_id in visited_ids:
        return
    visited_ids.add(obj_id)
    keep_alive.append(payload)

    if isinstance(payload, dict):
        _check_mapping_items(payload.items(), visited_ids, keep_alive, pd, np)
        return

    if pd is not None and isinstance(payload, pd.DataFrame):
        _check_dataframe(payload, visited_ids, keep_alive, pd, np)
        return

    if pd is not None and isinstance(payload, pd.Series):
        _check_series(payload, visited_ids, keep_alive, pd, np)
        return

    if _is_namedtuple(payload):
        _check_mapping_items(
            ((campo, getattr(payload, campo)) for campo in payload._fields),
            visited_ids,
            keep_alive,
            pd,
            np,
        )
        return

    if dataclasses.is_dataclass(payload) and not isinstance(payload, type):
        _check_mapping_items(
            ((campo.name, getattr(payload, campo.name)) for campo in dataclasses.fields(payload)),
            visited_ids,
            keep_alive,
            pd,
            np,
        )
        return

    if isinstance(payload, (list, tuple, set, frozenset)):
        for item in payload:
            _assert_no_identity_impl(item, visited_ids, keep_alive, pd, np)
        return

    if _is_understood_scalar(payload, pd, np):
        return

    if hasattr(payload, "__dict__"):
        _check_mapping_items(vars(payload).items(), visited_ids, keep_alive, pd, np)
        return

    raise AnonymityError(
        f"tipo no reconocido ({type(payload).__name__}): assert_no_identity no "
        "sabe leer este tipo, y por eso no puede certificar que no hay "
        "identidad escondida adentro. Convertir con privacy.canonicalize() a "
        "una estructura simple (dict/lista/escalar) antes de emitir."
    )
