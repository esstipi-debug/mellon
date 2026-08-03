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
propone un guardia, el oraculo y las fronteras deciden si entra.

DOS DIFFS, NO UNO. `Episodio.archivos_tocados` es el diff del commit de arreglo
historico y toca `src/` por construccion; nunca se pasa por la frontera del
testigo. Lo que la frontera vigila es lo que el testigo escribio en ESTA
cosecha, y eso llega por `diff_del_testigo` cuando hay un diff real, o por la
declaracion de `destilar` cuando todavia no lo hay. Hoy no lo hay: el runner de
dos arboles con worktree esta pendiente. Por eso el `Resultado` dice sobre cual
de las dos fuentes se verifico -- una verificacion contra autodeclaracion
presentada como verificacion contra diff es exactamente el bug que este
proyecto persigue.

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

DiffDelTestigo = Callable[[Episodio], "list[str] | None"]
"""Los archivos que el testigo ESCRIBIO de verdad durante esta cosecha.

Devuelve None cuando para ese episodio no hay diff real, y entonces la frontera
cae a la autodeclaracion de `destilar` -- diciendolo. No confundir con
`Episodio.archivos_tocados`, que es el diff del commit de arreglo historico.

Nadie lo provee todavia: materializar el arbol del testigo y diffearlo es parte
del runner de dos arboles con worktree, declarado pendiente en el plan."""


@dataclass(frozen=True)
class Resultado:
    guardias: tuple[str, ...]
    descartados: tuple[tuple[str, str], ...]
    cobertura: CoberturaGuardia
    marcas: tuple[tuple[int, str], ...] = ()
    """(indice del episodio en la iteracion, estado nuevo) para que el llamador
    llame a `episodio.marcar`. Ver la nota sobre el marcado en `cosechar`."""
    guardias_sin_diff: tuple[str, ...] = ()
    """Los guardias aceptados cuya frontera se verifico contra la AUTODECLARACION
    del agente porque no habia diff real del testigo. Es un subconjunto de
    `guardias`, no una lista aparte de descartes: entraron igual, pero con una
    contencion mas debil, y quien lee el resultado tiene que poder distinguirlos
    sin leer el codigo. `cobertura.nota()` publica el conteo."""


def _id(ep: Episodio) -> str:
    return f"{ep.commit_antes[:7]}..{ep.commit_despues[:7]}"


def _motivo_frontera(invadidos: list[str], hay_diff: bool, declarados: Iterable[str]) -> str:
    """Arma el motivo del descarte diciendo sobre que fuente se verifico.

    Con diff real la distincion que importa es otra: que el diff muestre un
    archivo que el agente NO declaro no es la misma falla que declararlo. La
    primera es una declaracion incompleta -- el agente no sabe o no dice lo que
    toco -- y hace inservible todo lo demas que declare.

    Sin diff real el motivo tiene que decir que se verifico contra la
    autodeclaracion, para que nadie lo lea como una contencion que no fue.
    """
    if not hay_diff:
        return (
            "frontera violada por el testigo: destilar declara "
            f"{', '.join(invadidos)} (verificado contra la autodeclaracion del "
            "agente: no hay diff real del testigo)"
        )
    declarados_set = set(declarados)
    omitidos = [a for a in invadidos if a not in declarados_set]
    detalle = f"el diff del testigo muestra {', '.join(invadidos)}"
    if omitidos:
        detalle += (
            f", y destilar omitio de su declaracion {', '.join(omitidos)}: "
            "una declaracion incompleta es mas grave que una violacion declarada"
        )
    return "frontera violada por el testigo: " + detalle


def cosechar(
    episodios: Iterable[Episodio],
    destilar: Destilador,
    correr: Callable[[str], set[str]],
    today: str,
    bugs_atrapados: int | None = None,
    diff_del_testigo: DiffDelTestigo | None = None,
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

    `diff_del_testigo` es opcional y por defecto None porque el diff real del
    testigo no existe todavia (ver `DiffDelTestigo`). Sin el, la frontera se
    verifica sobre la declaracion de `destilar` y los guardias que entraron asi
    quedan listados en `Resultado.guardias_sin_diff` y contados en la nota de
    cobertura. Con el, la frontera se verifica sobre el diff y la declaracion
    deja de decidir: un agente que declara solo `tests/` pero escribio `src/` se
    descarta igual.
    """
    guardias: list[str] = []
    descartados: list[tuple[str, str]] = []
    familias: list[str] = []
    marcas: list[tuple[int, str]] = []
    sin_diff: list[str] = []

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

        # La frontera vigila lo que el TESTIGO escribio en esta cosecha. El diff
        # real manda cuando existe; si no, la declaracion -- y se registra que
        # fue asi. `ep.archivos_tocados` no entra aca: es el otro diff.
        real = diff_del_testigo(ep) if diff_del_testigo is not None else None
        hay_diff = real is not None
        invadidos = viola_frontera("testigo", real if hay_diff else tocados)
        if invadidos:
            descartados.append((_id(ep), _motivo_frontera(invadidos, hay_diff, tocados)))
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
        if not hay_diff:
            sin_diff.append(nombre)
        marcas.append((indice, "destilado"))
        if familia not in familias:
            familias.append(familia)

    return Resultado(
        guardias=tuple(guardias),
        descartados=tuple(descartados),
        cobertura=CoberturaGuardia(
            familias_vigiladas=tuple(familias),
            bugs_atrapados=bugs_atrapados,
            guardias_sin_diff_del_testigo=len(sin_diff),
        ),
        marcas=tuple(marcas),
        guardias_sin_diff=tuple(sin_diff),
    )
