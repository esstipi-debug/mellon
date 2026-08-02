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

    def __post_init__(self) -> None:
        """`k` tiene que ser al menos 1: con 0 la compuerta deja de existir.

        `allows(n)` es `n >= self.k`. Con `k=0` da verdadero para TODO n,
        incluido n=0, asi que la compuerta se vuelve un no-op silencioso: la
        salida sale igual que sin compuerta y nada en el resultado registra
        que se desactivo. `n_subjects` si se validaba (`gate_output` rechaza
        negativos), y `k` -- el unico de los dos que viene del usuario, por
        `--k` -- no; la asimetria protegia el argumento que nadie toca.

        Bajar a `k=1` es una decision legitima y explicita: significa "asumo
        que este agregado puede ser una sola persona y lo emito igual", que es
        lo que hace falta en la maqueta de mesa, donde hay un solo carro.
        Ponerlo en 0 no es bajar el umbral, es apagar la compuerta, y para eso
        no hay caso de uso honesto: si se quiere emitir sin umbral, `k=1` ya
        lo hace y ademas queda registrado en `anonymity_k`.
        """
        if self.k < 1:
            raise ValueError(
                f"el umbral de anonimato k tiene que ser >= 1 (llego {self.k}). "
                "k=1 es el minimo y significa 'emito el agregado aunque cubra "
                "una sola persona, asumiendo que ahi el agregado ES un "
                "individuo'; k=0 no baja el umbral, apaga la compuerta y no "
                "deja rastro. Usar k=1 si esa es la intencion (queda registrado "
                "en anonymity_k), o subirlo hasta la cantidad minima de sujetos "
                "que se acepte publicar."
            )

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


def _is_namedtuple(obj: object) -> bool:
    """Una tupla con `_fields` no es una tupla plana: es un registro."""
    return (
        isinstance(obj, tuple)
        and isinstance(getattr(obj, "_fields", None), tuple)
        and all(isinstance(campo, str) for campo in obj._fields)
    )


_NAMEDTUPLE_MSG = (
    "un namedtuple ({tipo}) es un registro con nombres de campo, no una tupla "
    "plana: recorrerlo como tupla mira los valores pero nunca los nombres, y "
    "un campo que identifica pasaria sin verse. Convertir con `._asdict()` a "
    "un dict antes de emitir."
)


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

    Una etiqueta REPETIDA (en `Series.index` o en las columnas del `DataFrame`
    ya con el indice reseteado) tambien se rechaza, por la misma familia de
    razones: el dict resultante se queda con un solo valor por clave, asi que
    de `["ARUCO-CRUDO-7", "sub-0123456789ab"]` bajo la etiqueta `resource`
    sobrevive uno solo -- y si el que sobrevive es el limpio, el crudo
    desaparece ANTES de que la verificacion lo vea y la salida se certifica
    limpia. Deduplicar en silencio seria borrar la evidencia; se falla en su
    lugar, nombrando la etiqueta repetida.
    """
    pd = _try_import_pandas()
    np = _try_import_numpy()
    return _canonicalize_impl(obj, pd, np)


_DUPLICADAS_MSG = (
    "{que} tiene la etiqueta {etiqueta!r} repetida, y convertir a dict dejaria "
    "un solo valor por etiqueta: el otro DESAPARECERIA antes de que "
    "assert_no_identity pudiera verlo, y la salida se certificaria limpia sin "
    "que nadie haya mirado el valor borrado. Una compuerta de privacidad que "
    "borra la evidencia es peor que una que falla abierto, asi que esto se "
    "rechaza en vez de deduplicarse en silencio. Causa tipica: un merge sin "
    "sufijos, o un CSV con encabezados repetidos. Renombrar las etiquetas "
    "repetidas antes de emitir."
)


def _rechazar_etiquetas_duplicadas(etiquetas, que: str) -> None:
    """Falla si hay una etiqueta repetida, nombrando cual.

    pandas mismo tolera indices y columnas con etiquetas repetidas; el que no
    puede tolerarlas es `canonicalize`, porque su salida es un dict y un dict
    se queda con el ultimo valor de cada clave.
    """
    vistas = set()
    for etiqueta in etiquetas:
        try:
            if etiqueta in vistas:
                raise AnonymityError(_DUPLICADAS_MSG.format(que=que, etiqueta=etiqueta))
            vistas.add(etiqueta)
        except TypeError:
            # Etiqueta no hasheable: no puede ser clave de dict de todas formas,
            # y `_is_field_name` la rechaza mas adelante con su propio mensaje.
            continue


def _canonicalize_impl(obj: object, pd, np) -> object:
    if pd is not None and isinstance(obj, pd.DataFrame):
        con_indice = obj.reset_index()
        _rechazar_etiquetas_duplicadas(list(con_indice.columns), "el DataFrame")
        registros = con_indice.to_dict("records")
        return [_canonicalize_impl(reg, pd, np) for reg in registros]

    if pd is not None and isinstance(obj, pd.Series):
        return _canonicalize_series(obj, pd, np)

    if isinstance(obj, dict):
        return {clave: _canonicalize_impl(valor, pd, np) for clave, valor in obj.items()}

    if _is_namedtuple(obj):
        # Convertirlo a lista aca perderia los nombres de campo, que es el
        # mismo defecto que hace rechazar la Series posicional. `._asdict()`
        # es una linea del lado de quien lo tiene y conserva los nombres.
        raise AnonymityError(_NAMEDTUPLE_MSG.format(tipo=type(obj).__name__))

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
    _rechazar_etiquetas_duplicadas(etiquetas, "la Series")
    if not all(_is_field_name(etiqueta) for etiqueta in etiquetas):
        raise AnonymityError(
            "una pandas.Series posicional (indice sin nombres de campo) no se "
            "puede certificar: sin el nombre del campo no hay forma de saber si "
            "un valor es un identificador. Pasar un DataFrame, o un dict con "
            "nombres de campo explicitos."
        )

    return {etiqueta: _canonicalize_impl(valor, pd, np) for etiqueta, valor in serie.items()}


def _normalizar_nombre_campo(label: object) -> object:
    """Normaliza un nombre de campo antes de compararlo contra los conjuntos.

    `casefold()` + `strip()` porque las cabeceras de un export de WMS vienen
    en mayusculas la mitad de las veces, y con espacios pegados la otra mitad.
    Comparando por igualdad exacta, `marker_id` se atrapaba pero `Marker_ID`,
    `MARKER_ID` y `marker_id ` pasaban limpios; y en PSEUDONYM_FIELDS el bypass
    era total, porque una clave `Resource` desactivaba tambien la validacion de
    forma del seudonimo -- o sea que `{"Resource": "Juan Perez"}` se certificaba
    limpio.

    Lo que esta funcion NO hace, a proposito: unificar separadores. `MarkerID`
    en camelCase sigue pasando. Eso es un paso aparte, con su propia matriz de
    ataque (¿que pasa con `MarkerId` vs `Marker_Id` vs `marker-id`?), y
    mezclarlo aca traeria falsos positivos que esta normalizacion no tiene.
    """
    if isinstance(label, str):
        return label.strip().casefold()
    return label


def _pista(valor: object) -> str:
    """Prefijo corto de un valor, para un mensaje de error que no lo revele.

    La compuerta existe para que la identidad no cruce el borde. Un mensaje que
    dice `(valor: 'Juan Perez RUT 12.345.678-9')` la escribe en una excepcion
    que termina en stdout, en el log y en el ticket -- o sea que la compuerta
    filtra exactamente lo que vino a contener. Tres caracteres alcanzan para
    reconocer cual de las filas es, y no para identificar a nadie.
    """
    texto = str(valor)
    return f"{texto[:3]}..." if len(texto) > 3 else "..."


def _check_key_for_identity(key: object) -> None:
    """Revisa un nombre de campo (o una tupla de MultiIndex) contra IDENTITY_FIELDS.

    Si `key` es una tupla —el caso de una clave que quedo compuesta al aplanar
    un MultiIndex via `canonicalize`, tipo ("meta", "marker_id")— se verifica
    CADA ELEMENTO por separado. Comparar la tupla entera contra IDENTITY_FIELDS
    nunca matchea, porque el conjunto contiene strings sueltos: ese fue el
    agujero de la ronda 2.

    La comparacion es sobre el nombre normalizado (ver
    `_normalizar_nombre_campo`). El mensaje nombra el campo, que es un nombre
    de columna y no un dato de la persona; el VALOR nunca entra al mensaje.
    """
    if key is None:
        return
    candidatos = key if isinstance(key, tuple) else (key,)
    for candidato in candidatos:
        if _normalizar_nombre_campo(candidato) in IDENTITY_FIELDS:
            raise AnonymityError(
                f"el campo '{candidato}' identifica y no puede cruzar el borde "
                "(regla 9). Pseudonimizar con privacy.pseudonymize antes de emitir."
            )


def _key_matches_pseudonym(key: object) -> bool:
    if key is None:
        return False
    candidatos = key if isinstance(key, tuple) else (key,)
    return any(_normalizar_nombre_campo(c) in PSEUDONYM_FIELDS for c in candidatos)


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

    `items` es un iterable de pares (clave, valor). Primero se exige que la
    clave sea un nombre de campo (str, o tupla de str para el MultiIndex
    aplanado): un dict con claves enteras es un mapeo posicional, y un valor
    sin nombre de campo al lado no se puede verificar contra nada — el mismo
    punto ciego que la Series posicional que rechaza `canonicalize`. Despues
    la clave se revisa contra IDENTITY_FIELDS; si cae en PSEUDONYM_FIELDS se
    valida la forma del valor en vez de recorrerlo; si no, se recursa.
    """
    for clave, valor in items:
        if not _is_field_name(clave):
            raise AnonymityError(
                f"una clave de tipo {type(clave).__name__} (empieza con "
                f"{_pista(clave)!r}) no es un nombre "
                "de campo: assert_no_identity solo certifica estructuras "
                "JSON-simples, donde las claves son strings (o tuplas de strings "
                "para columnas MultiIndex aplanadas). Sin nombre de campo no hay "
                "contra que verificar el valor. Rearmar el dict con nombres de "
                "campo explicitos antes de emitir."
            )
        _check_key_for_identity(clave)
        if _key_matches_pseudonym(clave):
            if not _is_valid_pseudonym_value(valor, pd):
                raise AnonymityError(
                    f"el campo '{clave}' contiene un valor de tipo "
                    f"{type(valor).__name__} que no tiene forma de seudonimo "
                    f"(esperado 'sub-<12 hex>'; el valor empieza con "
                    f"{_pista(valor)!r} y no se transcribe entero a proposito: "
                    "un mensaje de error va a stdout y al log, y escribir ahi la "
                    "identidad seria filtrar justo lo que esta compuerta "
                    "contiene). Pseudonimizar con privacy.pseudonymize antes de "
                    "emitir."
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

    Dos limites que la coherencia con fallar cerrado exige (ronda 5):

    - **Las claves de dict tienen que ser `str`, o tupla de `str`.** En una
      estructura JSON-simple las claves de objeto son siempre strings; un dict
      con claves enteras es un mapeo posicional, y un valor sin nombre de
      campo al lado no se puede verificar contra nada. Es el mismo punto ciego
      que hace rechazar la `Series` posicional en `canonicalize`. La tupla
      sigue permitida porque es lo que produce `canonicalize` para columnas
      MultiIndex, y se verifica elemento por elemento: `("meta", "marker_id")`
      identifica igual que `"marker_id"`.
    - **Un `namedtuple` se rechaza aunque sea una `tuple`.** Recorrerlo por la
      rama de tupla mira los valores pero nunca los nombres de campo, asi que
      `Ev(operator="OP-001", x=1)` pasaria limpio. Si no se pueden verificar
      los nombres, no se certifica: hay que convertirlo con `._asdict()`.

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

    if _is_namedtuple(payload):
        raise AnonymityError(_NAMEDTUPLE_MSG.format(tipo=type(payload).__name__))

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


CAMPO_AGREGADO = "locations"
CAMPO_MOTIVO = "locations_withheld_reason"
# El umbral con el que se emitio ESTE resultado. Va en la salida porque un
# resultado emitido con k=1 y uno emitido con k=3 no son el mismo resultado, y
# sin el campo no hay forma de saber cual se esta leyendo un mes despues.
CAMPO_UMBRAL = "anonymity_k"

_MOTIVO_BAJO_UMBRAL = (
    "'{campo}' no se emite: el agregado cubre {n} sujeto(s) y el umbral de "
    "anonimato es k={k}. La lista de ubicaciones de un solo sujeto no es un "
    "agregado, es el itinerario completo de una persona identificable (spec "
    "seccion 6). El conteo de sujetos sale de la cantidad de pistas reconstruidas: "
    "una pista, un sujeto. Para verlo: ampliar la ventana hasta tener al menos "
    "k sujetos, o bajar el umbral a proposito con --k asumiendo lo que eso "
    "significa."
)


def gate_output(payload: dict, n_subjects: int, gate: AnonymityGate | None = None) -> dict:
    """El borde unico: toda salida a disco o a consola pasa por aca (spec seccion 6).

    Antes de esta funcion, la regla 9 se cumplia POR CONSTRUCCION —
    `build_tracks` seudonimiza, asi que nunca llegaba un identificador crudo a
    la salida— y la regla 10 no se aplicaba en ningun lado: `AnonymityGate`
    estaba definida, testeada y exportada, y ni una linea de codigo de
    produccion la invocaba. Una compuerta que hay que acordarse de invocar es
    una compuerta que no existe; el spec promete un borde, y un borde es un
    lugar por el que se pasa siempre, no una funcion disponible.

    Hace tres cosas, en este orden:

    1. `assert_no_identity` sobre el diccionario COMPLETO. No sobre los campos
       que uno sospecha: sobre todo, porque el campo que se escapa es siempre
       el que nadie penso en revisar.
    2. `AnonymityGate` sobre `locations`. Si el agregado no llega a k sujetos,
       la lista NO se emite y en su lugar va el motivo en
       `locations_withheld_reason` -- un `None` explicito con su razon al lado,
       no la ausencia silenciosa del campo, que se lee como "no habia
       ubicaciones" en vez de "no se pueden mostrar".
    3. Echa el umbral usado en `anonymity_k`. Un resultado emitido con k=1 y
       uno emitido con k=3 no son el mismo resultado -- el primero asume que
       el agregado puede ser una sola persona. Sin el campo, quien lee el JSON
       un mes despues no tiene como saber cual de los dos tiene en la mano, y
       la decision de bajar el umbral se vuelve invisible.

    `n_subjects` es el conteo de sujetos distintos que cubre el agregado. En
    `run_field` sale de la cantidad de PISTAS RECONSTRUIDAS: una pista es un
    marcador, y un marcador es un carro que lleva una persona. No sale del
    numero de detecciones ni de paradas, que son muchas por sujeto.

    Devuelve un dict NUEVO; no muta el que recibio.
    """
    if not isinstance(payload, dict):
        raise AnonymityError(
            f"el borde de salida recibe un dict de resultados, no un "
            f"{type(payload).__name__}: armar el dict con nombres de campo "
            "explicitos antes de emitir."
        )
    if n_subjects < 0:
        raise AnonymityError(
            f"n_subjects no puede ser negativo (llego {n_subjects}); tiene que "
            "ser la cantidad de sujetos distintos que cubre el agregado."
        )

    assert_no_identity(payload)

    gate = gate if gate is not None else AnonymityGate()
    salida = dict(payload)
    salida[CAMPO_UMBRAL] = gate.k
    if CAMPO_AGREGADO in salida and not gate.allows(n_subjects):
        salida[CAMPO_AGREGADO] = None
        salida[CAMPO_MOTIVO] = _MOTIVO_BAJO_UMBRAL.format(
            campo=CAMPO_AGREGADO, n=n_subjects, k=gate.k
        )
    return salida


def _ya_visitado(payload: object, visited_ids: set, keep_alive: list) -> bool:
    obj_id = id(payload)
    if obj_id in visited_ids:
        return True
    visited_ids.add(obj_id)
    keep_alive.append(payload)
    return False
