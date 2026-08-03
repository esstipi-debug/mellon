"""La orquestacion de la cosecha.

Es la mitad del harness que ACTUA, y por eso corre a pedido y en worktree
aislado: el arbol de trabajo no se toca nunca, asi que las sesiones
concurrentes -- que en este repo ya revirtieron ediciones dos veces en una
tarde -- dejan de importar.

`destilar` se inyecta porque es el UNICO punto agentico de todo el modulo.
Aislarlo detras de un callable es lo que permite testear la orquestacion entera
sin gastar un token, y es tambien lo que deja la decision en codigo: el agente
propone un guardia, el oraculo y las fronteras deciden si entra.

La cosecha puede devolver CERO guardias y eso es un resultado bueno. Una
cosecha que siempre produce algo esta produciendo ruido para justificarse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from fdekit.guard import CoberturaGuardia

from .episodio import Episodio
from .oraculo import veredicto
from .roles import viola_frontera

Destilador = Callable[[Episodio], "tuple[str, str, str, list[str]] | None"]
"""Devuelve (nombre_del_guardia, familia, test_id, archivos_tocados) o None.

La familia va separada del nombre porque son cosas distintas: el nombre
identifica un guardia, la familia agrupa la clase de error. CoberturaGuardia
publica familias, y un campo que dice una cosa y contiene otra es la clase de
bug que este repo tiene documentada 17 veces."""


@dataclass(frozen=True)
class Resultado:
    guardias: tuple[str, ...]
    descartados: tuple[tuple[str, str], ...]
    cobertura: CoberturaGuardia


def _id(ep: Episodio) -> str:
    return f"{ep.commit_antes[:7]}..{ep.commit_despues[:7]}"


def cosechar(
    episodios: Iterable[Episodio],
    destilar: Destilador,
    correr: Callable[[str], set[str]],
    today: str,
) -> Resultado:
    """Procesa los episodios y devuelve los guardias que sobrevivieron.

    `today` es argumento: regla 4 del repo.
    """
    guardias: list[str] = []
    descartados: list[tuple[str, str]] = []
    familias: list[str] = []

    for ep in episodios:
        if ep.estado != "abierto":
            descartados.append((_id(ep), f"estado {ep.estado}: no se procesa"))
            continue

        try:
            propuesta = destilar(ep)
        except Exception as exc:  # destilar es el punto agentico: no determinista
            descartados.append((_id(ep), f"destilar exploto: {exc!r}"))
            continue

        if propuesta is None:
            descartados.append((_id(ep), "sin leccion: el episodio no generaliza a ninguna regla"))
            continue

        try:
            nombre, familia, test_id, tocados = propuesta
        except (TypeError, ValueError) as exc:
            descartados.append((_id(ep), f"destilar devolvio una forma invalida: {propuesta!r} ({exc})"))
            continue

        invadidos = viola_frontera("testigo", tocados)
        if invadidos:
            descartados.append((_id(ep), f"frontera violada por el testigo: {', '.join(invadidos)}"))
            continue

        v = veredicto(test_id, correr, ep.commit_antes, ep.commit_despues)
        if not v.acepta:
            descartados.append((_id(ep), v.motivo))
            continue

        guardias.append(nombre)
        if familia not in familias:
            familias.append(familia)

    return Resultado(
        guardias=tuple(guardias),
        descartados=tuple(descartados),
        cobertura=CoberturaGuardia(familias_vigiladas=tuple(familias)),
    )
