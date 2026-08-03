"""La orquestacion de la cosecha.

Es la mitad del harness que ACTUA, y por eso corre a pedido. El aislamiento por
worktree que pide el diseno TODAVIA NO EXISTE: no hay una sola linea de
worktree en `tools/`, asi que hoy es responsabilidad del llamador correr esto
donde no moleste. Mientras eso no se construya, dos sesiones concurrentes sobre
el mismo arbol siguen pudiendo pisarse -- en este repo ya revirtieron ediciones
dos veces en una tarde.

`destilar` se inyecta porque es el UNICO punto agentico de todo el modulo.
Aislarlo detras de un callable es lo que permite testear la orquestacion entera
sin gastar un token, y es tambien lo que deja la decision en codigo: el agente
propone un guardia, el oraculo y las fronteras deciden si entra. Por lo mismo
su declaracion de archivos tocados no se le cree sola: la frontera se evalua
sobre la union de lo que declara y lo que el episodio trae del diff de git.

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
    marcas: tuple[tuple[int, str], ...] = ()
    """(indice del episodio en la iteracion, estado nuevo) para que el llamador
    llame a `episodio.marcar`. Ver la nota sobre el marcado en `cosechar`."""


def _id(ep: Episodio) -> str:
    return f"{ep.commit_antes[:7]}..{ep.commit_despues[:7]}"


def _motivo_frontera(declarados: list[str], del_diff: list[str], tocados: Iterable[str]) -> str:
    """Arma el motivo del descarte distinguiendo de que fuente salio.

    La distincion importa: que el agente omita de su declaracion un archivo que
    el diff SI muestra no es la misma falla que declararlo. La primera es una
    declaracion incompleta -- el agente no sabe o no dice lo que toco -- y hace
    inservible todo lo demas que declare. Quien lee el descarte tiene que poder
    ver cual de las dos paso.
    """
    partes: list[str] = []
    if del_diff:
        declarados_set = set(tocados)
        omitidos = [a for a in del_diff if a not in declarados_set]
        detalle = f"el diff del episodio muestra {', '.join(del_diff)}"
        if omitidos:
            detalle += (
                f", y destilar omitio de su declaracion {', '.join(omitidos)}: "
                "una declaracion incompleta es mas grave que una violacion declarada"
            )
        partes.append(detalle)
    if declarados:
        partes.append(f"destilar declara {', '.join(declarados)}")
    return "frontera violada por el testigo: " + "; ".join(partes)


def cosechar(
    episodios: Iterable[Episodio],
    destilar: Destilador,
    correr: Callable[[str], set[str]],
    today: str,
    bugs_atrapados: int | None = None,
) -> Resultado:
    """Procesa los episodios y devuelve los guardias que sobrevivieron.

    `today` es argumento: regla 4 del repo.

    `bugs_atrapados` tambien es argumento, y por defecto es None (Hallazgo 4 de
    la revision final). El sistema NO puede calcularlo: nada mapea un episodio a
    uno de los 17 bugs de HANDOFF.md, y un cero por defecto se lee como "medimos
    y no atrapamos ninguno" cuando en realidad es "nadie midio". Se puebla solo
    si el llamador lo provee, y hasta entonces `nota()` dice que esta sin medir.
    Lo unico que la cosecha sabe de verdad -- cuantos guardias acepto -- ya esta
    en `Resultado.guardias`, y no es lo mismo que atrapar un bug historico.

    El marcado del log NO se hace aca (Hallazgo 5). `cosechar` recibe un
    iterable de episodios y no sabe de que archivo salieron ni si sus indices
    corresponden a los renglones del log; abrir el log adentro la convertiria en
    una funcion con efecto de lado sobre un path que no controla. En cambio
    devuelve `Resultado.marcas`: el llamador que leyo el log con `episodio.leer`
    itera esos pares y llama a `episodio.marcar(log, indice, estado)`.
    """
    guardias: list[str] = []
    descartados: list[tuple[str, str]] = []
    familias: list[str] = []
    marcas: list[tuple[int, str]] = []

    for indice, ep in enumerate(episodios):
        if ep.estado != "abierto":
            descartados.append((_id(ep), f"estado {ep.estado}: no se procesa"))
            continue

        try:
            propuesta = destilar(ep)
        except Exception as exc:  # destilar es el punto agentico: no determinista
            descartados.append((_id(ep), f"destilar exploto: {exc!r}"))
            marcas.append((indice, "descartado"))
            continue

        if propuesta is None:
            descartados.append((_id(ep), "sin leccion: el episodio no generaliza a ninguna regla"))
            marcas.append((indice, "descartado"))
            continue

        try:
            nombre, familia, test_id, tocados = propuesta
        except (TypeError, ValueError) as exc:
            descartados.append((_id(ep), f"destilar devolvio una forma invalida: {propuesta!r} ({exc})"))
            marcas.append((indice, "descartado"))
            continue

        # Las dos fuentes, no una: `tocados` es lo que el agente declara y
        # `ep.archivos_tocados` es lo que git muestra. Alcanza con que UNA salga
        # de tests/ para descartar.
        invadidos_declarados = viola_frontera("testigo", tocados)
        invadidos_del_diff = viola_frontera("testigo", ep.archivos_tocados)
        if invadidos_declarados or invadidos_del_diff:
            descartados.append((_id(ep), _motivo_frontera(invadidos_declarados, invadidos_del_diff, tocados)))
            marcas.append((indice, "descartado"))
            continue

        try:
            v = veredicto(test_id, correr, ep.commit_antes, ep.commit_despues)
        except Exception as exc:
            # `correr` shellea a git y a pytest: reventar es su modo de falla
            # normal, no excepcional. Un episodio no puede llevarse puestos los
            # que ya se acumularon en esta corrida.
            descartados.append((_id(ep), f"el oraculo exploto corriendo la suite: {exc!r}"))
            marcas.append((indice, "descartado"))
            continue

        if not v.acepta:
            descartados.append((_id(ep), v.motivo))
            marcas.append((indice, "descartado"))
            continue

        guardias.append(nombre)
        marcas.append((indice, "destilado"))
        if familia not in familias:
            familias.append(familia)

    return Resultado(
        guardias=tuple(guardias),
        descartados=tuple(descartados),
        cobertura=CoberturaGuardia(
            familias_vigiladas=tuple(familias),
            bugs_atrapados=bugs_atrapados,
        ),
        marcas=tuple(marcas),
    )
