"""El test que hace falsable al harness.

Un harness que genera tests es infalsable por defecto: puede producir guardias
para siempre sin que nadie sepa si sirven. Es exactamente el hallazgo que
reordeno este proyecto, asi que aplicarlo al harness no es opcional.

La parte de parseo es hermetica y corre siempre. La parte que toca git de
verdad esta marcada `historia` y sale del corrido por defecto, igual que
`vision`: necesita la historia completa del repo. Cuando esa historia no
esta disponible (clone shallow, tarball sin .git) el test saltea con motivo
en vez de reventar la suite entera: este kit tiene que correr en el notebook
prestado de un centro de distribucion, sin permisos y a veces sin historia.
"""

import subprocess
from pathlib import Path

import pytest

from tools.harness.historia import episodios_de_git

_RAIZ = Path(__file__).resolve().parents[1]
"""Raiz del repo, derivada de la ubicacion de este archivo -- no del cwd del
proceso que invoca pytest, para que el comando de git no dependa de desde
donde se corre."""

_MINIMO_COMMITS_PARA_HISTORIA = 40
"""Si el repo tiene menos commits que esto, ni siquiera puede llegar al
umbral del test: es indicio de un clone shallow, no de una historia real."""

_HASH_A = "aaaa1111" * 5
_HASH_B = "bbbb2222" * 5
_HASH_C = "cccc3333" * 5
"""Hashes de 40 hex, como los que produce `%H` de verdad. No se usan hashes
cortos de relleno porque el sentinel del parser ahora exige el largo real."""

_SALIDA = f"""C {_HASH_A} 2026-08-02 fix: anualizar una sola vez
src/fdekit/value/levers.py
tests/test_value.py

C {_HASH_B} 2026-08-01 docs: nada de codigo
docs/x.md

C {_HASH_C} 2026-08-01 feat: algo sin tests
src/fdekit/x.py
"""

_SALIDA_CON_ARCHIVO_QUE_PARECE_ENCABEZADO = f"""C {_HASH_A} 2026-08-02 fix: uno real
src/fdekit/x.py
C notas.md
tests/test_x.py
"""
"""Un archivo versionado llamado literalmente `C notas.md` empieza igual que
un encabezado de commit. Si el parser solo mira el prefijo `C `, lo confunde
con un commit nuevo y parte el episodio real en dos -- en silencio."""


def test_solo_los_commits_con_src_y_tests_son_episodios():
    """Sin un test en el commit no hay nada que correr contra el arbol viejo."""
    eps = episodios_de_git(_SALIDA)
    assert len(eps) == 1
    assert eps[0].commit_despues == _HASH_A


def test_el_commit_anterior_es_el_arbol_de_antes():
    eps = episodios_de_git(_SALIDA)
    assert eps[0].commit_antes == f"{_HASH_A}~1"


def test_los_archivos_tocados_llegan_al_episodio():
    eps = episodios_de_git(_SALIDA)
    assert "src/fdekit/value/levers.py" in eps[0].archivos_tocados


def test_una_salida_vacia_no_revienta():
    assert episodios_de_git("") == []


def test_un_archivo_llamado_c_algo_no_se_confunde_con_encabezado():
    """Guardia contra la mutacion de volver a `startswith("C ")`: sin exigir
    que el segundo token sea un hash hexadecimal, este archivo parte el
    episodio real en dos y el conteo se rompe en silencio."""
    eps = episodios_de_git(_SALIDA_CON_ARCHIVO_QUE_PARECE_ENCABEZADO)
    assert len(eps) == 1
    assert eps[0].commit_despues == _HASH_A
    assert "C notas.md" in eps[0].archivos_tocados


def _motivo_si_no_hay_historia_usable() -> str | None:
    """Devuelve por que no se puede correr el test de historia real, o None
    si la historia esta disponible y tiene profundidad suficiente."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=_RAIZ,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        return f"no hay repo git usable en {_RAIZ}: {exc}"

    resultado = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=_RAIZ,
        capture_output=True,
        text=True,
        check=True,
    )
    conteo_texto = resultado.stdout.strip()
    if not conteo_texto.isdigit() or int(conteo_texto) < _MINIMO_COMMITS_PARA_HISTORIA:
        return (
            f"historia demasiado corta ({conteo_texto!r} commits, se necesitan "
            f">= {_MINIMO_COMMITS_PARA_HISTORIA}): probablemente un clone shallow"
        )
    return None


@pytest.mark.historia
def test_la_historia_del_repo_tiene_episodios_reconstruibles():
    """El conjunto de validacion existe y hay que verlo antes de creerle al
    harness. Medido al 2-ago-2026 con `git log --all` daba 61; el numero
    puede subir y no puede ser cero: si es cero, el harness no tiene contra
    que medirse. Si la historia no esta completa (clone shallow, tarball sin
    .git) el test saltea con motivo en vez de reventar: ese caso no dice nada
    sobre si el conjunto se encogio."""
    motivo = _motivo_si_no_hay_historia_usable()
    if motivo is not None:
        pytest.skip(f"sin historia completa para medir episodios: {motivo}")

    salida = subprocess.run(
        ["git", "log", "--format=C %H %ad %s", "--date=short", "--name-only"],
        cwd=_RAIZ,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    eps = episodios_de_git(salida)

    assert len(eps) >= _MINIMO_COMMITS_PARA_HISTORIA, (
        f"solo {len(eps)} episodios reconstruibles: el conjunto de validacion se encogio"
    )
    assert all(e.commit_antes.endswith("~1") for e in eps)
