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

import os
from pathlib import Path

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
def findings(tmp_path_factory) -> dict:
    """El `hallazgos.json` real del demo, generado una vez por sesion.

    Determinista por la semilla del generador, y escrito en el temporal de
    pytest — nunca en el repo. Cuesta ~3 s una sola vez.
    """
    return _demo_a_tmp(tmp_path_factory.mktemp("demo"))


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


def pytest_sessionstart(session):
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
        "la suite escribio en el arbol de trabajo — usar tmp_path:" + detalle
    )
