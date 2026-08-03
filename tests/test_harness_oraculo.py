"""El oraculo y las fronteras: la contencion mecanica del harness.

La autoridad del harness es amplia -- escribe tests y arregla src -- asi que la
contencion no puede estar en el permiso. Esta en dos lugares y los dos son
codigo: las fronteras se verifican sobre el diff, y el veredicto se decide
corriendo la suite en dos arboles.
"""

import pytest

from tools.harness.roles import viola_frontera


def test_el_testigo_no_puede_tocar_src():
    """El que escribe el test no puede escribir el arreglo. Si pudiera, verde
    solo probaria que los dos comparten el mismo error."""
    assert viola_frontera("testigo", ["tests/test_x.py", "src/fdekit/value/levers.py"]) == [
        "src/fdekit/value/levers.py"
    ]


def test_el_reparador_no_puede_tocar_tests():
    assert viola_frontera("reparador", ["src/fdekit/x.py", "tests/test_x.py"]) == ["tests/test_x.py"]


def test_un_diff_que_respeta_la_frontera_no_da_violaciones():
    assert viola_frontera("testigo", ["tests/test_x.py", "tests/guards/test_anualizacion.py"]) == []


def test_un_rol_desconocido_se_rechaza():
    """Un rol sin frontera declarada seria un rol sin frontera."""
    with pytest.raises(ValueError, match="rol"):
        viola_frontera("cualquiera", ["src/x.py"])


def test_un_archivo_fuera_de_src_y_tests_tambien_viola():
    """El harness no toca pyproject, ni docs, ni tools. Una regla que solo
    prohibe la carpeta del otro rol deja abierto todo lo demas."""
    assert viola_frontera("reparador", ["pyproject.toml"]) == ["pyproject.toml"]
