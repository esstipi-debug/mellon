"""Reconstruye episodios de la historia de git.

El conjunto de validacion del harness no se inventa: ya existe en la historia
del repo. Todo commit que toca src/ y tests/ a la vez es un episodio
reconstruible -- el arbol de antes es el commit padre, el de despues es el
commit mismo, y el test que trae es el candidato a guardia.

Al 2-ago-2026 hay 61 commits asi, y el HANDOFF documenta 17 bugs de clase "no
falla, miente". El numero que importa es cuantos de esos el harness convierte
en guardia, publicado crudo.

`episodios_de_git` es puro sobre la salida de git para poder testearlo sin la
historia real. El comando que la produce vive en el test marcado `historia`.
"""

from __future__ import annotations

import re

from .episodio import Episodio

FORMATO = "C %H %ad %s"
"""Usar con: git log --format='C %H %ad %s' --date=short --name-only"""

_ENCABEZADO = re.compile(r"^C ([0-9a-f]{40}) (\S+)(?: (.*))?$")
"""Un encabezado real trae un hash de 40 hex despues de 'C '. Un path
versionado que empiece con 'C ' (por ejemplo `C notas.md`) no matchea esto y
se trata como archivo, no como encabezado -- si no, un archivo asi partiria
un episodio real en dos, en silencio."""


def episodios_de_git(salida: str) -> list[Episodio]:
    """Parsea la salida de `git log --format=FORMATO --date=short --name-only`."""
    eps: list[Episodio] = []
    commit = fecha = mensaje = ""
    archivos: list[str] = []

    def cerrar() -> None:
        if not commit:
            return
        tiene_src = any(a.startswith("src/") for a in archivos)
        tiene_tests = any(a.startswith("tests/") for a in archivos)
        if tiene_src and tiene_tests:
            eps.append(
                Episodio(
                    fecha=fecha,
                    commit_antes=f"{commit}~1",
                    commit_despues=commit,
                    tests_que_fallaban=(),
                    archivos_tocados=tuple(archivos),
                    mensaje=mensaje,
                )
            )

    for linea in salida.splitlines():
        m = _ENCABEZADO.match(linea)
        if m:
            cerrar()
            commit = m.group(1)
            fecha = m.group(2)
            mensaje = m.group(3) or ""
            archivos = []
        elif linea.strip():
            archivos.append(linea.strip())
    cerrar()
    return eps
