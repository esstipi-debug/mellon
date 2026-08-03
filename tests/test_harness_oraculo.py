"""El oraculo y las fronteras: la contencion mecanica del harness.

La autoridad del harness es amplia -- escribe tests y arregla src -- asi que la
contencion no puede estar en el permiso. Esta en dos lugares y los dos son
codigo: las fronteras se verifican sobre el diff, y el veredicto se decide
corriendo la suite en dos arboles.
"""

import pytest

from tools.harness.oraculo import veredicto
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


# ---------------------------------------------------------------- oraculo


def _correr(mapa):
    """Simula la suite: devuelve los tests que fallan en cada arbol."""
    return lambda commit: set(mapa[commit])


def test_un_test_que_falla_antes_y_pasa_despues_se_acepta():
    v = veredicto(
        test_nuevo="tests/guards/test_anual.py::test_una_sola_vez",
        correr=_correr({"antes": ["tests/guards/test_anual.py::test_una_sola_vez"], "despues": []}),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is True


def test_un_test_vacuo_se_rechaza():
    """El chequeo que hace que esto no sea un teatro: un test que pasa en el
    arbol donde el bug TODAVIA EXISTE no prueba nada. Verde no lo distingue de
    un test que prueba algo; correrlo contra el arbol viejo si."""
    v = veredicto(
        test_nuevo="tests/guards/test_vacuo.py::test_nada",
        correr=_correr({"antes": [], "despues": []}),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is False
    assert v.fallo_en_antes is False
    assert "vacuo" in v.motivo


def test_un_test_que_sigue_fallando_despues_se_rechaza():
    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=_correr({"antes": ["tests/guards/test_x.py::test_x"], "despues": ["tests/guards/test_x.py::test_x"]}),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is False
    assert v.paso_en_despues is False


def test_una_regresion_voltea_el_episodio_aunque_el_test_nuevo_este_verde():
    """No basta con que el numero nuevo este bien: ninguno de los viejos puede
    haber empeorado. La suite completa corre en los dos arboles."""
    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=_correr(
            {
                "antes": ["tests/guards/test_x.py::test_x"],
                "despues": ["tests/test_value.py::test_que_pasaba_antes"],
            }
        ),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is False
    assert v.regresiones == ("tests/test_value.py::test_que_pasaba_antes",)
    assert "regres" in v.motivo


def test_un_test_que_ya_fallaba_por_otro_motivo_no_cuenta_como_regresion():
    """Un test roto de antes sigue roto y no es culpa de este episodio. La
    semantica es 'no empeorar', igual que save() en el store."""
    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=_correr(
            {
                "antes": ["tests/guards/test_x.py::test_x", "tests/test_viejo.py::test_roto"],
                "despues": ["tests/test_viejo.py::test_roto"],
            }
        ),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is True
    assert v.regresiones == ()


def test_vacuo_gana_sobre_regresion_cuando_son_las_dos_cosas():
    """Si el test nuevo es vacuo (pasa en el arbol roto) y tambien hay
    regresion (otro test empeoro), el diagnostico es vacuo. El orden de
    los chequeos importa: primero vacuo, porque es la causa raiz."""
    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=_correr(
            {
                "antes": [],
                "despues": ["tests/test_value.py::test_que_pasaba_antes"],
            }
        ),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is False
    assert v.fallo_en_antes is False
    assert "vacuo" in v.motivo
    assert "regres" not in v.motivo


def test_snapshot_de_conjuntos_evita_aliasing_con_runner_que_reutiliza_objeto():
    """El runner puede reutilizar el objeto set entre llamadas o mutarlo.
    Sin el snapshot set(...), fallan_antes y fallan_despues serian aliases
    del mismo objeto, y regresiones siempre seria vacio aunque el runner
    muteara el conjunto."""
    mutable_set = {"tests/guards/test_x.py::test_x"}

    def correr_que_muta(commit):
        if commit == "despues":
            mutable_set.add("tests/test_value.py::test_nuevo")
        return mutable_set

    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=correr_que_muta,
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.regresiones == ("tests/test_value.py::test_nuevo",)
