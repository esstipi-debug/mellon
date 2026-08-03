"""Genera el indice legible del corpus de guardias.

El corpus ejecutable es la memoria; esto es solo una vista. Se arma parseando
el texto de cada guardia con ast en vez de importarlo: un guardia con un
SyntaxError, o uno que hace algo al importarse, no puede apagar la generacion
del indice de todos los demas.
"""

from __future__ import annotations

import ast
from pathlib import Path

CAMPOS_DE_PROCEDENCIA = ("commit", "fecha", "dueno")
"""Los campos que `fdekit.guard.hallazgo.Procedencia` exige para construirse.

Se listan aca en vez de importar Procedencia porque `tools/` no se instala y no
puede depender del paquete para una tabla de markdown. Si un LECCION no los
trae todos, el guardia NO tiene procedencia -- da igual que traiga regla y
familia. Rellenarlos con `-` los mostraria como un guardia sano al que le falta
un dato cosmetico, que es la mentira exacta que Procedencia existe para
impedir."""

ENCABEZADO = (
    "# Lecciones del harness\n\n"
    "> Archivo GENERADO por `tools/harness/indice.py` desde `tests/guards/`.\n"
    "> No editar a mano: la proxima regeneracion se come los cambios.\n"
    "> La memoria real son los tests; esto es una vista.\n\n"
)


def _leccion(texto: str) -> dict | None:
    """Extrae el dict LECCION de nivel de modulo, sin importar el modulo."""
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return None
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if isinstance(destino, ast.Name) and destino.id == "LECCION":
                try:
                    valor = ast.literal_eval(nodo.value)
                except ValueError:
                    return None
                return valor if isinstance(valor, dict) else None
    return None


def _faltantes(lec: dict) -> list[str]:
    """Los campos de procedencia que el LECCION no trae o trae vacios."""
    return [c for c in CAMPOS_DE_PROCEDENCIA if not str(lec.get(c, "")).strip()]


def _texto(p: Path) -> str | None:
    """Lee el guardia, o None si no se puede leer.

    Un `.py` con bytes que no son UTF-8 es exactamente el modo de falla que este
    modulo existe para impedir: un archivo roto no puede apagar la generacion
    del indice de todos los demas.
    """
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def indice(guards_dir: Path) -> str:
    d = Path(guards_dir)
    archivos = sorted(p for p in d.glob("*.py") if p.name != "__init__.py")
    if not archivos:
        return ENCABEZADO + "Todavia no hay guardias en el corpus.\n"

    filas = ["| guardia | familia | regla | commit | fecha | dueno |", "|---|---|---|---|---|---|"]
    for p in archivos:
        texto = _texto(p)
        if texto is None:
            filas.append(f"| `{p.stem}` | - | **ilegible** - no se pudo leer como UTF-8 | - | - | - |")
            continue
        lec = _leccion(texto)
        if lec is None:
            filas.append(f"| `{p.stem}` | - | **sin procedencia** - no declara `LECCION` | - | - | - |")
            continue
        faltan = _faltantes(lec)
        if faltan:
            filas.append(
                f"| `{p.stem}` | {lec.get('familia', '-')} | "
                f"**sin procedencia** - a `LECCION` le falta {', '.join(faltan)} | - | - | - |"
            )
            continue
        filas.append(
            f"| `{p.stem}` | {lec.get('familia', '-')} | {lec.get('regla', '-')} | "
            f"`{lec.get('commit', '-')}` | {lec.get('fecha', '-')} | {lec.get('dueno', '-')} |"
        )
    return ENCABEZADO + "\n".join(filas) + "\n"
