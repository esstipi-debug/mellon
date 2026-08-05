"""La suite declara cuanto de si misma NO corrio.

`pytest -q` termina en "1135 passed, 4 deselected". El 1135 se lee como
cobertura y no lo es: los cuatro deselectados los excluye `addopts`
(`-m 'not vision and not audio'`), asi que el verde no dice absolutamente nada
sobre ellos. Y "deselected" es una palabra que no alarma a nadie.

No es un riesgo hipotetico, es lo que paso. `transcribe_to_session` cambio de
devolver tres valores a cuatro y el test que la desempaqueta —marcado `audio`—
quedo roto. Tres corridas consecutivas dieron verde por encima de una firma
rota: 1116, 1129 y 1135. El commit salio pusheado. Se descubrio recien al
versionar `tests/data/audio_muestra.wav` y correr el marcador a mano.

Es exactamente el defecto que el codigo de este repo tiene prohibido: un numero
que se lee como denominador sin serlo. `draft_observations` lo cerro para los
enunciados descartados; `fdekit.value.contract` para las palancas sin datos.
Esto lo cierra para la suite, y devuelve la misma forma a proposito —totales,
`cuadra`, `nota`— porque es el mismo problema y no merece una forma nueva.

Lo que este modulo NO hace: fallar. Un marcador excluido puede ser legitimo
(`vision` pide OpenCV, `audio` baja un modelo). El problema nunca fue excluir:
fue no decirlo. Convertirlo en error rompe a cualquiera sin los extras y termina
en un `--no-cobertura` que nadie vuelve a sacar.
"""

from __future__ import annotations


def cobertura_de_la_suite(
    por_marcador: dict[str, int], ejecutados: int, no_ejecutados: int, recolectados: int
) -> dict:
    """Que corrio, que no, y si la cuenta cierra contra lo que pytest recolecto.

    Los tres numeros son distintos y hay que pasarlos por separado:

      `ejecutados`     los que corrieron
      `no_ejecutados`  TODOS los deseleccionados, venga de donde venga
      `por_marcador`   de esos, cuantos cargan un marcador excluido por defecto

    La primera version derivaba el total como `ejecutados + sum(por_marcador)` y
    eso mentia apenas alguien corria un marcador a mano: `pytest -m vision`
    imprimia "1 de 4 ejecutados" con 1147 tests recolectados, porque los 1146
    deseleccionados por el propio `-m` no cargaban ninguno de los marcadores
    contados. Un denominador inventado, que es el defecto que este modulo
    existe para cerrar. El total ahora lo pone pytest, no la aritmetica de aca.

    Un test con dos marcadores excluidos cuenta en los dos de `por_marcador`,
    asi que esa suma puede superar `no_ejecutados`. Por eso `cuadra` se calcula
    contra `recolectados` y no contra el desglose.
    """
    total = ejecutados + no_ejecutados

    if not no_ejecutados:
        nota = f"{ejecutados} test(s) ejecutados, ninguno excluido."
    else:
        nota = f"{ejecutados} de {total} test(s) ejecutados. **{no_ejecutados} NO EJECUTADOS**"
        if por_marcador:
            detalle = ", ".join(f"{m}: {n}" for m, n in sorted(por_marcador.items()))
            cmd = " / ".join(f"pytest -m {m}" for m in sorted(por_marcador))
            nota += (
                f" - {detalle} por marcador excluido en `addopts`: el verde de arriba "
                f"no dice nada sobre ellos. Correr {cmd}."
            )
        else:
            nota += " por seleccion explicita de esta corrida."

    return {
        "ejecutados": ejecutados,
        "no_ejecutados": no_ejecutados,
        "por_marcador": dict(sorted(por_marcador.items())),
        "total": total,
        "recolectados": recolectados,
        # Si esto es False, hay tests que pytest recolecto y que no aparecen ni
        # como ejecutados ni como deseleccionados: el reporte perdio uno.
        "cuadra": total == recolectados,
        "nota": nota,
    }


def contar_por_marcador(marcadores_por_test) -> dict[str, int]:
    """De [(marcadores de un test), ...] a {marcador: cuantos}.

    Se separa de la extraccion de marcadores de pytest a proposito: aca entran
    tuplas de strings y sale un dict, asi que se puede probar sin levantar una
    corrida de pytest adentro de otra.
    """
    conteo: dict[str, int] = {}
    for marcadores in marcadores_por_test:
        for m in marcadores:
            conteo[m] = conteo.get(m, 0) + 1
    return conteo
