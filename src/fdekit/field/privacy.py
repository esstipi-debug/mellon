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
from dataclasses import dataclass

SALT_BYTES = 16
_PSEUDONYM_HEX = 12

# Nombres de campo que, si aparecen en una salida, significan que algo se
# escapo. La lista es deliberadamente amplia: un falso positivo cuesta un
# renombre, un falso negativo cuesta el despliegue.
IDENTITY_FIELDS = frozenset(
    {"marker_id", "sensor_id", "resource_raw", "operator", "operator_id", "name", "rut"}
)


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
                "Un agregado bajo el umbral identifica; no se emite."
            )


def assert_no_identity(payload: object) -> None:
    """Recorre la salida completa y falla si sobrevivio un identificador.

    Recursivo a proposito: el modo de falla real no es olvidarse de anonimizar
    el campo principal, es dejar el crudo enterrado en una estructura anidada.
    """
    if isinstance(payload, dict):
        for clave, valor in payload.items():
            if clave in IDENTITY_FIELDS:
                raise AnonymityError(
                    f"el campo '{clave}' identifica y no puede cruzar el borde "
                    "(regla 9). Pseudonimizar con privacy.pseudonymize antes de emitir."
                )
            assert_no_identity(valor)
    elif isinstance(payload, (list, tuple, set)):
        for item in payload:
            assert_no_identity(item)
