"""La suite dice cuanto de si misma no corrio, y ese numero es correcto.

El reporte lo imprime un hook de `conftest.py`; la aritmetica vive en
`_cobertura_suite.py` justamente para poder probarla sin levantar una corrida
de pytest adentro de otra.
"""

import re
import tomllib
from pathlib import Path

import pytest

from _cobertura_suite import cobertura_de_la_suite, contar_por_marcador
from conftest import MARCADORES_EXCLUIDOS

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_sin_exclusiones_no_hay_nada_que_declarar():
    cob = cobertura_de_la_suite({}, ejecutados=100, no_ejecutados=0, recolectados=100)
    assert cob["no_ejecutados"] == 0
    assert "ninguno excluido" in cob["nota"]
    assert "NO EJECUTADOS" not in cob["nota"]


def test_la_nota_nombra_los_marcadores_y_como_correrlos():
    """Un aviso que no dice que hacer se ignora a la segunda corrida."""
    cob = cobertura_de_la_suite(
        {"audio": 3, "vision": 1}, ejecutados=1135, no_ejecutados=4, recolectados=1139
    )

    assert cob["no_ejecutados"] == 4
    assert cob["total"] == 1139
    assert "**4 NO EJECUTADOS**" in cob["nota"]
    assert "audio: 3" in cob["nota"] and "vision: 1" in cob["nota"]
    assert "pytest -m audio" in cob["nota"]
    # El numero de arriba no puede quedar sin calificar: es lo que hizo que una
    # firma rota sobreviviera tres corridas verdes.
    assert "no dice nada sobre ellos" in cob["nota"]


def test_el_denominador_lo_pone_pytest_y_no_la_aritmetica():
    """El caso que la primera version imprimia mal.

    `pytest -m vision` corre 1 test y deselecciona 1146, de los cuales solo 3
    cargan un marcador de `addopts`. Derivando el total como
    `ejecutados + sum(por_marcador)` salia "1 de 4 ejecutados" con 1147
    recolectados: un denominador inventado, exactamente el defecto que este
    reporte existe para cerrar.
    """
    cob = cobertura_de_la_suite(
        {"audio": 3}, ejecutados=1, no_ejecutados=1146, recolectados=1147
    )
    assert cob["total"] == 1147
    assert "1 de 1147" in cob["nota"]
    assert cob["cuadra"] is True


def test_cuadra_es_falso_si_el_reporte_pierde_un_test():
    """`cuadra` tiene que poder dar False, o no mide nada.

    Misma leccion que `_cobertura` en transcribe.py, donde derivar un termino
    por resta volvia el booleano una tautologia.
    """
    cob = cobertura_de_la_suite({"audio": 3}, ejecutados=1, no_ejecutados=3, recolectados=1147)
    assert cob["cuadra"] is False


def test_la_cuenta_cierra():
    cob = cobertura_de_la_suite(
        {"audio": 3, "vision": 1}, ejecutados=1135, no_ejecutados=4, recolectados=1139
    )
    assert cob["ejecutados"] + cob["no_ejecutados"] == cob["total"]
    assert cob["cuadra"] is True


def test_un_test_con_dos_marcadores_cuenta_en_los_dos():
    """Y por eso `no_ejecutados` puede superar la cantidad de tests excluidos.

    Es una decision, no un descuido: para el que lee, "cuantos escondio el
    marcador `audio`" es la pregunta util, aunque ese test tambien sea `vision`.
    """
    conteo = contar_por_marcador([("audio",), ("audio", "vision"), ("vision",)])
    assert conteo == {"audio": 2, "vision": 2}


def test_sin_marcadores_no_cuenta_nada():
    assert contar_por_marcador([(), ()]) == {}


def test_los_marcadores_declarados_son_los_que_addopts_excluye():
    """El guardia que importa: la lista y `addopts` no pueden divergir.

    `MARCADORES_EXCLUIDOS` esta escrita a mano en `conftest.py`. Si alguien
    agrega un marcador a `addopts` y no a la lista, esos tests desaparecen de
    la corrida Y del reporte de cobertura -- que es el mismo agujero que este
    reporte existe para tapar, un nivel mas abajo.
    """
    cfg = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    addopts = cfg["tool"]["pytest"]["ini_options"]["addopts"]

    en_addopts = set(re.findall(r"not\s+(\w+)", addopts))
    assert en_addopts == set(MARCADORES_EXCLUIDOS), (
        f"addopts excluye {sorted(en_addopts)} y MARCADORES_EXCLUIDOS dice "
        f"{sorted(MARCADORES_EXCLUIDOS)}. Lo que no este en las dos, no se reporta."
    )


@pytest.mark.parametrize("marcador", MARCADORES_EXCLUIDOS)
def test_cada_marcador_excluido_esta_declarado_en_pyproject(marcador):
    """Un marcador sin declarar en `[tool.pytest.ini_options].markers` es un
    warning que a la larga se silencia, y ahi deja de existir."""
    cfg = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    declarados = [m.split(":")[0].strip() for m in cfg["tool"]["pytest"]["ini_options"]["markers"]]
    assert marcador in declarados
