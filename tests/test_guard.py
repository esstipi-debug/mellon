"""Contrato compartido entre las dos capas del harness.

Estos tests fijan lo unico que ambas capas tienen que respetar. Si alguno se
pone rojo, el contrato cambio y las dos capas hay que mirarlas.
"""

from datetime import date

import pytest

from fdekit.guard import CoberturaGuardia, Hallazgo, Procedencia


def _proc(commit="abc1234", dueno="stipi"):
    return Procedencia(commit=commit, fecha=date(2026, 8, 2), dueno=dueno)


def test_un_hallazgo_sin_commit_no_se_construye():
    """La leccion de los hashes del HANDOFF, aplicada al tipo: una afirmacion
    sobre el repo sin commit que la ancle es la que despues engana."""
    with pytest.raises(ValueError, match="commit"):
        Procedencia(commit="", fecha=date(2026, 8, 2), dueno="stipi")


def test_un_hallazgo_sin_dueno_no_se_construye():
    """Regla 1 del repo: lo que va a una cola de revision va con dueno."""
    with pytest.raises(ValueError, match="dueno"):
        Procedencia(commit="abc1234", fecha=date(2026, 8, 2), dueno="")


def test_un_hallazgo_sin_regla_no_se_construye():
    with pytest.raises(ValueError, match="regla"):
        Hallazgo(regla="", evidencia="algo", procedencia=_proc())


def test_un_hallazgo_completo_es_inmutable():
    h = Hallazgo(regla="no anualizar dos veces", evidencia="L1 20% baja", procedencia=_proc())
    with pytest.raises(Exception):
        h.regla = "otra"


# ------------------------------------------------------------- cobertura


def test_la_cobertura_nunca_dice_estar_completa():
    """Mismo motivo que Coverage en decide/query.py: heredar la interfaz de la
    promesa 'detecta los bugs' sin heredar la garantia, y callarlo, es el error
    mas grave que puede cometer este diseno."""
    c = CoberturaGuardia(familias_vigiladas=("anualizacion", "unidades"), bugs_atrapados=17)
    assert c.is_complete is False


def test_la_nota_nombra_primero_lo_que_NO_vigila():
    """El limite que hereda el oraculo elegido: sin invariantes externas, el
    harness solo aprende de fracasos que ya se manifestaron como test rojo. El
    bug que nunca falla no lo atrapa nadie, y eso va en la primera linea."""
    nota = CoberturaGuardia(familias_vigiladas=("anualizacion",)).nota()
    primera = nota.splitlines()[0]
    assert "no vigila" in primera
    assert "nunca fallo" in primera


def test_la_nota_publica_el_puntaje_crudo_contra_los_bugs_historicos():
    """El numero honesto no es 17/17: es cuantos de los 17 atrapa."""
    nota = CoberturaGuardia(familias_vigiladas=("a", "b"), bugs_atrapados=2).nota()
    assert "2 de 17" in nota


def test_sin_familias_la_nota_lo_dice_en_vez_de_quedar_muda():
    nota = CoberturaGuardia().nota()
    assert "ninguna familia" in nota
