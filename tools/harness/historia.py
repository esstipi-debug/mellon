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

from .episodio import Episodio

FORMATO = "C %H %ad %s"
"""Usar con: git log --format='C %H %ad %s' --date=short --name-only"""


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
        if linea.startswith("C "):
            cerrar()
            partes = linea[2:].split(" ", 2)
            commit = partes[0]
            fecha = partes[1] if len(partes) > 1 else ""
            mensaje = partes[2] if len(partes) > 2 else ""
            archivos = []
        elif linea.strip():
            archivos.append(linea.strip())
    cerrar()
    return eps
