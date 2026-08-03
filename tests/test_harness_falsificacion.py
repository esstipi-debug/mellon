"""El test que hace falsable al harness.

Un harness que genera tests es infalsable por defecto: puede producir guardias
para siempre sin que nadie sepa si sirven. Es exactamente el hallazgo que
reordeno este proyecto, asi que aplicarlo al harness no es opcional.

La parte de parseo es hermetica y corre siempre. La parte que toca git de
verdad esta marcada `historia` y sale del corrido por defecto, igual que
`vision`: necesita la historia completa del repo.
"""

import subprocess

import pytest

from tools.harness.historia import episodios_de_git

_SALIDA = """C aaa1111 2026-08-02 fix: anualizar una sola vez
src/fdekit/value/levers.py
tests/test_value.py

C bbb2222 2026-08-01 docs: nada de codigo
docs/x.md

C ccc3333 2026-08-01 feat: algo sin tests
src/fdekit/x.py
"""


def test_solo_los_commits_con_src_y_tests_son_episodios():
    """Sin un test en el commit no hay nada que correr contra el arbol viejo."""
    eps = episodios_de_git(_SALIDA)
    assert len(eps) == 1
    assert eps[0].commit_despues == "aaa1111"


def test_el_commit_anterior_es_el_arbol_de_antes():
    eps = episodios_de_git(_SALIDA)
    assert eps[0].commit_antes == "aaa1111~1"


def test_los_archivos_tocados_llegan_al_episodio():
    eps = episodios_de_git(_SALIDA)
    assert "src/fdekit/value/levers.py" in eps[0].archivos_tocados


def test_una_salida_vacia_no_revienta():
    assert episodios_de_git("") == []


@pytest.mark.historia
def test_la_historia_del_repo_tiene_episodios_reconstruibles():
    """El conjunto de validacion existe y hay que verlo antes de creerle al
    harness. Al 2-ago-2026 eran 61; el numero puede subir y no puede ser cero:
    si es cero, el harness no tiene contra que medirse."""
    salida = subprocess.run(
        ["git", "log", "--format=C %H %ad %s", "--date=short", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    eps = episodios_de_git(salida)

    assert len(eps) >= 40, f"solo {len(eps)} episodios reconstruibles: el conjunto de validacion se encogio"
    assert all(e.commit_antes.endswith("~1") for e in eps)
