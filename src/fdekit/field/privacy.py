"""Regla 9: el sensor ve al operador; el archivo que sale del sensor, no.

La agregacion no es una promesa en un documento: es una propiedad del codigo,
verificada por `tests/test_field_privacy.py`. Esa distincion es el argumento
central del toolkit — casi todos los vendors venden vigilancia disfrazada de
productividad; aca la medicion viene con olvido disenado.

Limite conocido: con dos operadores por zona el umbral k no impide deducir
quien es quien. Lo mitiga, no lo elimina. Ver seccion 6 del spec.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

SALT_BYTES = 16
_PSEUDONYM_HEX = 12
_PSEUDONYM_RE = re.compile(r"^sub-[0-9a-f]{12}$")

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


@dataclass(frozen=True)
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


def assert_no_identity(payload: object) -> None:
    """Recorre la salida completa y falla si sobrevivio un identificador.

    Recursivo a proposito: el modo de falla real no es olvidarse de anonimizar
    el campo principal, es dejar el crudo enterrado en una estructura anidada.

    Tipos recorridos: dict, list, tuple, set, frozenset, pandas.DataFrame,
    pandas.Series, dataclass, namedtuple, objeto con __dict__.

    Tipos NO recorridos: str, int, float, bool, None, y otros tipos primitivos.
    """
    _assert_no_identity_impl(payload, set())


def _assert_no_identity_impl(payload: object, visited: set) -> None:
    """Implementacion interna con proteccion contra ciclos.

    El conjunto 'visited' mantiene los id() de objetos ya revisados para evitar
    bucles infinitos en grafos ciclicos.
    """
    # Proteccion contra ciclos en estructuras complejas
    obj_id = id(payload)
    if obj_id in visited:
        return
    visited.add(obj_id)

    # Verificar pandas.DataFrame (importacion perezosa)
    try:
        import pandas as pd
        if isinstance(payload, pd.DataFrame):
            # Revisar nombres de columna contra IDENTITY_FIELDS
            for col in payload.columns:
                if col in IDENTITY_FIELDS:
                    raise AnonymityError(
                        f"la columna '{col}' identifica y no puede cruzar el borde "
                        "(regla 9). Renombrar o remover antes de emitir."
                    )
                # Revisar valores de columnas en PSEUDONYM_FIELDS
                if col in PSEUDONYM_FIELDS:
                    for val in payload[col]:
                        if isinstance(val, str) and not _PSEUDONYM_RE.match(val):
                            raise AnonymityError(
                                f"la columna '{col}' contiene valores que no son seudonimos "
                                f"(valor: '{val}'). Pseudonimizar con privacy.pseudonymize "
                                "antes de emitir."
                            )
            return
        # Revisar pandas.Series
        if isinstance(payload, pd.Series):
            if payload.name and payload.name in IDENTITY_FIELDS:
                raise AnonymityError(
                    f"la serie con nombre '{payload.name}' identifica y no puede cruzar el borde "
                    "(regla 9). Renombrar o remover antes de emitir."
                )
            # Revisar valores si el nombre esta en PSEUDONYM_FIELDS
            if payload.name and payload.name in PSEUDONYM_FIELDS:
                for val in payload:
                    if isinstance(val, str) and not _PSEUDONYM_RE.match(val):
                        raise AnonymityError(
                            f"la serie '{payload.name}' contiene valores que no son seudonimos "
                            f"(valor: '{val}'). Pseudonimizar con privacy.pseudonymize antes de emitir."
                        )
            else:
                # Recorrer elementos de la serie
                for item in payload:
                    _assert_no_identity_impl(item, visited)
            return
    except ImportError:
        pass

    # Manejar namedtuples (detectar por _fields)
    if hasattr(payload, "_fields") and isinstance(getattr(payload, "_fields", None), tuple):
        for field_name in payload._fields:
            if field_name in IDENTITY_FIELDS:
                raise AnonymityError(
                    f"el campo '{field_name}' identifica y no puede cruzar el borde "
                    "(regla 9). Pseudonimizar con privacy.pseudonymize antes de emitir."
                )
            field_val = getattr(payload, field_name)
            if field_name in PSEUDONYM_FIELDS:
                if isinstance(field_val, str) and not _PSEUDONYM_RE.match(field_val):
                    raise AnonymityError(
                        f"el campo '{field_name}' contiene un valor que no es seudonimo "
                        f"(valor: '{field_val}'). Pseudonimizar con privacy.pseudonymize "
                        "antes de emitir."
                    )
            else:
                _assert_no_identity_impl(field_val, visited)
        return

    # Manejar dataclasses y objetos con __dict__
    if hasattr(payload, "__dict__"):
        obj_dict = vars(payload)
        for clave, valor in obj_dict.items():
            if clave in IDENTITY_FIELDS:
                raise AnonymityError(
                    f"el campo '{clave}' identifica y no puede cruzar el borde "
                    "(regla 9). Pseudonimizar con privacy.pseudonymize antes de emitir."
                )
            if clave in PSEUDONYM_FIELDS:
                if isinstance(valor, str) and not _PSEUDONYM_RE.match(valor):
                    raise AnonymityError(
                        f"el campo '{clave}' contiene un valor que no es seudonimo "
                        f"(valor: '{valor}'). Pseudonimizar con privacy.pseudonymize "
                        "antes de emitir."
                    )
            else:
                _assert_no_identity_impl(valor, visited)
        return

    # Manejar diccionarios normales
    if isinstance(payload, dict):
        for clave, valor in payload.items():
            if clave in IDENTITY_FIELDS:
                raise AnonymityError(
                    f"el campo '{clave}' identifica y no puede cruzar el borde "
                    "(regla 9). Pseudonimizar con privacy.pseudonymize antes de emitir."
                )
            if clave in PSEUDONYM_FIELDS:
                if isinstance(valor, str) and not _PSEUDONYM_RE.match(valor):
                    raise AnonymityError(
                        f"el campo '{clave}' contiene un valor que no es seudonimo "
                        f"(valor: '{valor}'). Pseudonimizar con privacy.pseudonymize "
                        "antes de emitir."
                    )
            else:
                _assert_no_identity_impl(valor, visited)
        return

    # Manejar listas, tuplas, sets, frozensets
    if isinstance(payload, (list, tuple, set, frozenset)):
        for item in payload:
            _assert_no_identity_impl(item, visited)
        return
