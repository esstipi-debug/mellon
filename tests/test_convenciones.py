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


# CRITERIO DE EXCEPCION: Se exceptua un archivo cuando el acento es DATO BAJO
# PRUEBA o materia del modulo, NUNCA cuando es prosa descuidada. Los acentos en
# datos de prueba son obligatorios cuando lo que se prueba es justamente el
# manejo de acentos. Un acento descuidado en un comentario de un archivo
# exceptuado no se detecta — ese es el precio de la simplicidad.

ARCHIVOS_CON_ACENTOS_A_PROPOSITO = {
    "tests/test_convenciones.py": (
        "Este guardia detecta caracteres acentuados, asi que necesita contenerlos "
        "en su regex. La regex misma es la unica forma de especificar qué "
        "caracteres buscar."
    ),
    "tests/test_transcribe.py": (
        "Prueba strip_accents() con entrada acentuada: 'día andén reposición'. "
        "El acento es la entrada de la funcion bajo prueba; sin acentos el test "
        "no prueba nada."
    ),
    "tests/test_decide.py": (
        "Verifica que el lexico acepte 'quizás' y 'a más tardar'. Es el test "
        "del bug de normalizacion: 'quizas' se rechazaba y 'quizás' pasaba. "
        "Los acentos en datos de prueba son la materia del test."
    ),
    "tests/test_decide_parse.py": (
        "Test del agujero H14: resolve_owner('dueño Fabián', ROSTER). El nombre "
        "acentuado es parte del caso que revela el bug. Sin acentos, el test "
        "no atraparia el problema."
    ),
    "src/fdekit/gemba/transcribe.py": (
        "Este modulo normaliza acentos en transcripciones. Necesita ejemplos "
        "acentuados (dia, quizas, etc.) para probar que los quita correctamente."
    ),
}


def _get_py_files_to_check() -> list[Path]:
    """Obtiene todos los archivos .py versionados bajo src/fdekit/ y tests/."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Filtrar por prefijo en Python para evitar problemas de glob.
        py_files = [
            Path(line.strip())
            for line in result.stdout.splitlines()
            if line.strip() and (line.startswith("src/fdekit/") or line.startswith("tests/"))
        ]
        return py_files
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: glob recursivo desde raiz, luego filtrar por prefijo.
        py_files = list(Path(".").glob("src/fdekit/**/*.py"))
        py_files += list(Path(".").glob("tests/**/*.py"))
        # Tambien agregar archivos directos (que glob no cubre).
        py_files += [p for p in Path("src/fdekit").glob("*.py") if p.is_file()]
        py_files += [p for p in Path("tests").glob("*.py") if p.is_file()]
        return sorted(set(py_files))


def test_no_tildes_ni_enes_en_codigo_python():
    """Verifica que no haya caracteres acentuados en codigo Python del repo.

    Se ejecuta sobre todos los .py versionados en src/fdekit/ y tests/.
    Si encuentra una tilde o ene, el mensaje de falla dice archivo, linea,
    y el texto ofensor, para que sea trivial arreglarlo.
    """
    py_files = _get_py_files_to_check()

    # Patron: solo tildes en vocales castellanas y ene, minuscula y mayuscula.
    # Excluye puntuacion espanola legitima y caracteres de otros idiomas.
    # Usar escape Unicode para no violar la propia regla del guardia.
    patron_acentos = re.compile("[áéíóúñÁÉÍÓÚÑ]")

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


def test_guardia_cubre_todos_los_archivos():
    """Verifica que el guardia efectivamente revisa todos los .py versionados.

    Esta es la metaprueba: si el guardia cubre menos archivos de los que
    deberia, esta prueba falla. Impide cambios silenciosos en el patrón de
    busqueda que dejen archivos sin vigilar.
    """
    # Contar los .py versionados bajo src/fdekit/ y tests/.
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            capture_output=True,
            text=True,
            check=True,
        )
        todos = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and (line.startswith("src/fdekit/") or line.startswith("tests/"))
        ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        todos = []

    # Contar los que el guardia revisa.
    py_files = _get_py_files_to_check()
    revisados = [str(p) for p in py_files]

    # Comparar.
    if len(revisados) != len(todos):
        faltantes = set(todos) - set(revisados)
        msg = (
            f"El guardia revisa {len(revisados)} archivos pero hay {len(todos)} "
            f".py versionados bajo src/fdekit/ y tests/. "
            f"Faltantes: {sorted(faltantes)}"
        )
        raise AssertionError(msg)


def test_el_guardia_cubre_el_corpus_de_guardias_del_harness():
    """tests/guards/ es donde escribe un agente. Si el guardia no lo cubre, una
    tilde entra ahi y nadie la mira hasta que el archivo se abre en un notebook
    prestado con otra codificacion.

    El guardia filtra `git ls-files` por prefijo, asi que esto tambien verifica
    que el corpus este VERSIONADO: un tests/guards/ sin git add no lo cubre
    nadie.
    """
    cubiertos = [str(p).replace("\\", "/") for p in _get_py_files_to_check()]
    assert any("tests/guards/" in c for c in cubiertos), (
        "tests/guards/ no esta cubierto por el guardia de convenciones"
    )
