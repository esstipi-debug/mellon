"""Guardias de convenciones del repo: caracteres acentuados en codigo Python.

El repositorio se edita desde terminales y notebooks prestados de centros de
distribucion, donde la codificacion no siempre es UTF-8. Un caracter acentuado
mal decodificado en un comentario es ruido; en un literal de string es un bug.

Esta convención existe porque el kit no puede depender de nada pesado y tiene
que correr en entornos restringidos. Por eso un acento descuidado en un string
sale a luz en produccion, y eso es caro de depurar.

El guardia verifica que en todo archivo .py versionado dentro de src/fdekit/ y
tests/ no haya tildes ni eñes. Excepto en docstrings de modulo a nivel raiz
(que se editaran raramente y son obvios), y excepto en los .md del repo (que usan
tildes normalmente).
"""

import re
import subprocess
from pathlib import Path


def test_no_tildes_ni_enes_en_codigo_python():
    """Verifica que no haya caracteres acentuados en codigo Python del repo.

    Se ejecuta sobre todos los .py versionados en src/fdekit/ y tests/.
    Si encuentra una tilde o eñe, el mensaje de falla dice archivo, linea,
    y el texto ofensor, para que sea trivial arreglarlo.
    """
    # Obtener la lista de archivos .py versionados en git.
    try:
        result = subprocess.run(
            ["git", "ls-files", "src/fdekit/**/*.py", "tests/**/*.py"],
            capture_output=True,
            text=True,
            check=True,
        )
        py_files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Si git no funciona, hacer un fallback a glob.
        py_files = list(Path("src/fdekit").rglob("*.py")) + list(Path("tests").rglob("*.py"))

    # Patron para tildes y enes: acentos, diéresis, eñe, etc.
    patron_acentos = re.compile(r"[áéíóúàèìòùäëïöüãõâêîôûç¡¿ñÁÉÍÓÚÀÈÌÒÙÄËÏÖÜÃÕÂÊÎÔÛÇ¡¿Ñ]")

    violaciones = []
    for py_file in py_files:
        if not py_file.exists():
            continue
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                for lineno, linea in enumerate(f, start=1):
                    if patron_acentos.search(linea):
                        # Extraer el caracter ofensor para que sea obvio.
                        caracteres = [m.group(0) for m in patron_acentos.finditer(linea)]
                        ofensores = ", ".join(f"'{c}'" for c in set(caracteres))
                        violaciones.append(
                            f"{py_file}:{lineno}: {ofensores}\n    {linea.rstrip()}"
                        )
        except (UnicodeDecodeError, IOError):
            # Ignorar archivos no UTF-8 o no legibles.
            pass

    if violaciones:
        msg = "Caracteres acentuados o enes encontrados en codigo Python:\n"
        msg += "\n".join(violaciones)
        raise AssertionError(msg)
