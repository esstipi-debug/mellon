"""Contrato compartido entre las dos capas del harness.

Estos tests fijan lo unico que ambas capas tienen que respetar. Si alguno se
pone rojo, el contrato cambio y las dos capas hay que mirarlas.
"""

from datetime import date

import pytest

from fdekit.guard import CoberturaGuardia, Guardia, Hallazgo, Procedencia, evaluar


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


# --------------------------------------------------------------- guardia


def _guardia(nombre="sin_anualizar_dos_veces", sano=True):
    return Guardia(
        nombre=nombre,
        motivo="anualizar en dos capas dejo L1 y L2 20% bajas, en silencio",
        hallazgo=Hallazgo(regla="una sola anualizacion", evidencia="residuo 250/300", procedencia=_proc()),
        predicado=lambda _obj: sano,
    )


def test_un_guardia_sin_motivo_no_se_construye():
    """Cada excepcion del guardia de convenciones lleva su motivo escrito al
    lado. Un guardia sin motivo es el que nadie sabe si puede borrar."""
    with pytest.raises(ValueError, match="motivo"):
        Guardia(
            nombre="x",
            motivo="",
            hallazgo=Hallazgo(regla="r", evidencia="e", procedencia=_proc()),
            predicado=lambda _obj: True,
        )


def test_evaluar_devuelve_hallazgos_no_booleanos():
    """Un booleano pierde la procedencia. Lo que sale de un guardia violado
    tiene que poder rastrearse hasta el commit que lo origino."""
    hallazgos = evaluar([_guardia(sano=False)], obj={"cualquiera": 1})
    assert len(hallazgos) == 1
    assert hallazgos[0].procedencia.commit == "abc1234"


def test_evaluar_no_devuelve_nada_cuando_todo_esta_sano():
    assert evaluar([_guardia(sano=True)], obj={}) == []


def test_un_guardia_que_revienta_no_tumba_la_evaluacion_entera():
    """Un guardia roto tiene que degradar como el store degrada por archivo:
    el que revienta se reporta como violado con el motivo, y los demas corren.
    Que un guardia nuevo apague a los otros es como se pierde el corpus."""

    def bomba(_obj):
        raise KeyError("campo que ya no existe")

    roto = Guardia(
        nombre="roto",
        motivo="quedo viejo",
        hallazgo=Hallazgo(regla="r", evidencia="e", procedencia=_proc()),
        predicado=bomba,
    )
    hallazgos = evaluar([roto, _guardia(sano=True)], obj={})
    assert len(hallazgos) == 1
    assert "reviento" in hallazgos[0].evidencia
