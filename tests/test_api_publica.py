"""Guardia de la superficie publica de cada paquete.

El arreglo de los `__all__` no sirve sin esto: la inversion se produjo sola, por
acumulacion, y se vuelve a producir sola. Cada vez que alguien necesita algo de
otro paquete, el camino de menor resistencia es importarlo del submodulo — y ahi
el `__init__` deja de describir para que sirve el paquete.

Dos invariantes, y la segunda es la que importa:

  1. Todo nombre de `__all__` existe y se puede importar del paquete.
  2. Ningun modulo de `src/` alcanza el submodulo de OTRO paquete para traerse
     un nombre publico. Dentro del mismo paquete es normal; cruzando el limite
     es la senal de que el `__init__` de destino no ofrece lo que hace falta.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "fdekit"
PAQUETES = sorted(p.parent.name for p in SRC.glob("*/__init__.py"))


def _all_de(pkg: str) -> list[str]:
    tree = ast.parse((SRC / pkg / "__init__.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "__all__" for t in node.targets
        ):
            return [e.value for e in node.value.elts]
    return []


def _resolver(mod: str | None, level: int, archivo: Path) -> str:
    """Nombre absoluto del modulo importado, resolviendo los relativos."""
    if not level:
        return mod or ""
    partes = list(archivo.relative_to(SRC.parent).parts[:-1])
    base = partes[: len(partes) - (level - 1)]
    return ".".join(base + ([mod] if mod else []))


@pytest.mark.parametrize("pkg", PAQUETES)
def test_todo_lo_declarado_en_all_existe(pkg):
    """Un `__all__` que nombra lo que no existe rompe `from pkg import *` y
    miente en la documentacion, que es peor."""
    m = importlib.import_module(f"fdekit.{pkg}")
    faltan = [n for n in getattr(m, "__all__", []) if not hasattr(m, n)]
    assert not faltan, f"fdekit.{pkg}.__all__ nombra lo que no existe: {faltan}"


@pytest.mark.parametrize("pkg", PAQUETES)
def test_todo_paquete_declara_su_superficie(pkg):
    assert _all_de(pkg), f"fdekit.{pkg} no declara __all__"


def test_ningun_paquete_alcanza_el_submodulo_de_otro():
    """La invariante que evita que la inversion vuelva.

    Si este test falla, la respuesta correcta casi siempre es **exportar el
    nombre en el `__init__` de destino**, no agregar una excepcion aca. Que un
    paquete tenga que ir a buscar adentro de otro significa que el otro no esta
    diciendo para que sirve.
    """
    exportado = {f"fdekit.{p}": set(_all_de(p)) for p in PAQUETES}
    infracciones: list[str] = []

    for f in SRC.rglob("*.py"):
        if f.name == "__init__.py":
            continue
        rel = f.relative_to(SRC)
        origen = f"fdekit.{rel.parts[0]}" if len(rel.parts) > 1 else "fdekit"

        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom):
                continue
            full = _resolver(node.module, node.level, f)
            destino = ".".join(full.split(".")[:2])
            # Mismo paquete, o import del paquete entero: nada que objetar.
            if destino not in exportado or full == destino or destino == origen:
                continue
            for alias in node.names:
                # Los privados se dejan pasar: si alguien importa un `_nombre`
                # de otro paquete ya sabe lo que esta haciendo, y el linter de
                # convenciones no es este test.
                if alias.name.startswith("_") or alias.name in exportado[destino]:
                    continue
                infracciones.append(
                    f"{rel} importa '{alias.name}' de {full} "
                    f"— deberia estar en {destino}.__all__"
                )

    assert not infracciones, "\n  " + "\n  ".join(infracciones)
