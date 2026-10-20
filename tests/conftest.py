"""Fixtures compartidas y el guardia de higiene de la suite.

El `findings` de `test_value.py` leia `Path("out/hallazgos.json")` — ruta
relativa al cwd, y `out/` esta en `.gitignore`. Cuatro problemas encadenados:

  1. dependia del directorio desde donde se corriera pytest;
  2. dependia de un artefacto NO versionado, asi que "tests verdes" significaba
     cosas distintas en esta maquina y en un clon limpio;
  3. si el artefacto faltaba, corria el demo completo y **escribia dentro del
     arbol de trabajo** — un test con efecto de lado sobre el repo;
  4. y por lo tanto tenia dos comportamientos distintos segun el estado previo,
     que es la definicion de un test no hermetico.

La solucion no es congelar un JSON en `tests/fixtures/`: eso testearia contra
una foto y no contra lo que el demo produce hoy, y la cadena demo -> value es
justamente lo que hay que cubrir. Se genera una vez por sesion, en el temporal
de pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `tools/` no es un paquete instalado a proposito: no viaja al notebook del CD.
# Los tests lo importan desde la raiz del repo.
_RAIZ = Path(__file__).resolve().parents[1]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import os

import pytest

REPO = Path(__file__).resolve().parent.parent

# Lo que cambia solo y no cuenta como suciedad.
_IGNORAR = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_IGNORAR_SUFIJOS = {".pyc", ".pyo"}
_IGNORAR_NOMBRES = {".coverage"}


def _demo_a_tmp(tmp: Path) -> dict:
    from fdekit.demo import run_full_diagnosis

    return run_full_diagnosis(tmp, seed=7, quiet=True)


@pytest.fixture(scope="session")
def _demo_run(tmp_path_factory) -> tuple[Path, dict]:
    tmp = tmp_path_factory.mktemp("demo")
    return tmp, _demo_a_tmp(tmp)


@pytest.fixture(scope="session")
def findings(_demo_run) -> dict:
    """El `hallazgos.json` real del demo, generado una vez por sesion.

    Determinista por la semilla del generador, y escrito en el temporal de
    pytest — nunca en el repo. Cuesta ~3 s una sola vez.
    """
    return _demo_run[1]


@pytest.fixture(scope="session")
def demo_out(_demo_run) -> Path:
    """Directorio con los CSV del demo (event_log, auditoria_maestros,
    dimensionamiento, panel_experimento). Misma corrida que `findings`."""
    return _demo_run[0]


# ----------------------------------------------- guardia de higiene


# Que se vigila. Acotado a proposito: el guardia tiene que atrapar al test que
# ensucia, no al proceso ajeno que deja un volcado en la raiz mientras la suite
# corre. Un guardia que salta por ruido se desactiva a la semana.
_VIGILADOS = ("src", "tests", "docs")


def _snapshot() -> tuple[dict[str, float], set[str]]:
    """(archivos vigilados -> mtime, entradas de primer nivel).

    Dos alcances distintos y a proposito:

      - dentro de `src/`, `tests/` y `docs/` se mira el mtime: un test que
        reescriba codigo o documentacion tiene que saltar;
      - en la raiz solo se miran las entradas NUEVAS. El bug original era
        `run_full_diagnosis("out")` creando `out/` en el cwd, que aparece como
        entrada nueva. Vigilar el mtime de lo que ya estaba en la raiz haria
        que la suite fallara porque otra herramienta escribio un log al lado.
    """
    files: dict[str, float] = {}
    for base in _VIGILADOS:
        for root, dirs, names in os.walk(REPO / base):
            dirs[:] = [d for d in dirs if d not in _IGNORAR]
            for f in names:
                if f in _IGNORAR_NOMBRES or Path(f).suffix in _IGNORAR_SUFIJOS:
                    continue
                p = Path(root) / f
                try:
                    files[str(p.relative_to(REPO))] = p.stat().st_mtime
                except OSError:
                    pass
    raiz = {e.name for e in REPO.iterdir() if e.name not in _IGNORAR}
    return files, raiz


# ------------------------------------------- cobertura de la propia suite


# Los marcadores que `addopts` excluye por defecto. Se listan aca y no se
# derivan de la expresion `-m` porque derivarla obligaria a parsearla, y un
# parser de expresiones booleanas para reportar un numero es peor que la lista.
# Si se agrega un marcador a `addopts` y no aca, `test_cobertura_suite.py` falla.
MARCADORES_EXCLUIDOS = ("vision", "audio")


def pytest_deselected(items):
    """Guarda lo que quedo fuera. Sin esto el dato no existe al final."""
    _DESELECCIONADOS.extend(items)


_DESELECCIONADOS: list = []


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Imprime cuanto de la suite NO corrio. Ver `_cobertura_suite`.

    "1135 passed, 4 deselected" se lee como cobertura y no lo es. Esta linea
    existe porque una firma rota sobrevivio tres corridas verdes escondida
    detras del marcador `audio`.
    """
    from _cobertura_suite import cobertura_de_la_suite, contar_por_marcador

    ejecutados = sum(
        len(terminalreporter.stats.get(k, [])) for k in ("passed", "failed", "error")
    )
    por_marcador = contar_por_marcador(
        tuple(m.name for m in it.iter_markers() if m.name in MARCADORES_EXCLUIDOS)
        for it in _DESELECCIONADOS
    )
    # El total lo pone pytest. Derivarlo de `ejecutados + por_marcador` daba un
    # denominador inventado en cuanto alguien corria `-m <marcador>` a mano.
    cob = cobertura_de_la_suite(
        por_marcador,
        ejecutados,
        no_ejecutados=len(_DESELECCIONADOS),
        recolectados=getattr(terminalreporter._session, "testscollected", 0),
    )
    if cob["no_ejecutados"]:
        terminalreporter.write_sep("-", "cobertura de la suite")
        terminalreporter.write_line(cob["nota"])


def pytest_sessionstart(session):
    _DESELECCIONADOS.clear()
    session.config._fdekit_antes = _snapshot()



def pytest_sessionfinish(session, exitstatus):
    """Ningun test escribe en el arbol de trabajo.

    Es el guardia de la clase de error, no del caso: cualquier test que genere
    artefactos dentro del repo hace que la suite dependa de su propio historial
    y que "verde" signifique cosas distintas segun quien la corra.

    Si esto salta, la respuesta es `tmp_path` / `tmp_path_factory`, no agregar el
    archivo a `.gitignore`: ignorarlo esconde el efecto de lado, no lo elimina.
    """
    antes = getattr(session.config, "_fdekit_antes", None)
    if antes is None or exitstatus not in (0, 1):
        return

    (f_antes, r_antes), (f_despues, r_despues) = antes, _snapshot()
    nuevos = sorted(set(f_despues) - set(f_antes))
    tocados = sorted(k for k in set(f_antes) & set(f_despues) if f_antes[k] != f_despues[k])
    en_raiz = sorted(r_despues - r_antes)
    if not (nuevos or tocados or en_raiz):
        return

    detalle = "".join(f"\n    nuevo en raiz: {p}" for p in en_raiz[:20])
    detalle += "".join(f"\n    nuevo:         {p}" for p in nuevos[:20])
    detalle += "".join(f"\n    modificado:    {p}" for p in tocados[:20])
    raise pytest.UsageError(
        "el arbol de trabajo cambio durante la corrida:" + detalle + "\n\n"
        "  Si lo escribio un test: usar `tmp_path` / `tmp_path_factory`. NO agregar el "
        "archivo a .gitignore — eso esconde el efecto de lado en vez de eliminarlo, y es "
        "exactamente como nacio el fixture que dependia del cwd.\n"
        "  Si el archivo lo estaba editando otra cosa (un editor abierto, otra sesion de "
        "agente sobre el mismo repo), es un falso positivo: volver a correr con el arbol "
        "quieto. El guardia no puede distinguir las dos causas, y afinarlo para que "
        "tolere escrituras ajenas lo volveria inutil para la que importa."
    )
