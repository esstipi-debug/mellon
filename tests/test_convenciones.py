"""Guardias de convenciones del repo: caracteres acentuados en codigo Python.

El repositorio se edita desde terminales y notebooks prestados de centros de
distribucion, donde la codificacion no siempre es UTF-8. Un caracter acentuado
mal decodificado en un comentario es ruido; en un literal de string es un bug
que aparece recien en terreno. Por eso se evita en codigo Python y se usa
normalmente en los .md del repo.

El guardia verifica que en todo archivo .py versionado dentro de src/fdekit/ y
tests/ no haya tildes (a, e, i, o, u) ni enes (n). Admite puntuacion espanola
legitima (¿, ¡). Excepto en archivos con motivo documentado que necesitan
ejemplos acentuados para probar su comportamiento (p.ej., modulos que normalizan
acentos).
"""

import re
import subprocess
from pathlib import Path


# Archivos que contienen acentos a proposito, con motivo documentado.
ARCHIVOS_CON_ACENTOS_A_PROPOSITO = {
    "src/fdekit/gemba/transcribe.py": (
        "Este modulo normaliza acentos en transcripciones. Necesita ejemplos "
        "acentuados (dia, quizas, etc.) para probar que los quita correctamente."
    ),
}


def test_no_tildes_ni_enes_en_codigo_python():
    """Verifica que no haya caracteres acentuados en codigo Python del repo.

    Se ejecuta sobre todos los .py versionados en src/fdekit/ y tests/.
    Si encuentra una tilde o ene, el mensaje de falla dice archivo, linea,
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

    # Patron: solo tildes en vocales castellanas y ene, minuscula y mayuscula.
    # Excluye puntuacion espanola legitima (¿, ¡) y caracteres de otros idiomas.
    patron_acentos = re.compile(r"[áéíóúñÁÉÍÓÚÑ]")

    violaciones = []
    for py_file in py_files:
        if not py_file.exists():
            continue

        # Saltar archivos excepto si tienen motivo documentado.
        if any(py_file.as_posix().endswith(exc) for exc in ARCHIVOS_CON_ACENTOS_A_PROPOSITO):
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
        msg = "Caracteres acentuados encontrados en codigo Python:\n"
        msg += "\n".join(violaciones)
        msg += "\n\nMotivos de excepcion documentados:\n"
        for archivo, motivo in ARCHIVOS_CON_ACENTOS_A_PROPOSITO.items():
            msg += f"  - {archivo}: {motivo}\n"
        raise AssertionError(msg)
