"""Contrato compartido entre las dos capas del harness.

Estos tests fijan lo unico que ambas capas tienen que respetar. Si alguno se
pone rojo, el contrato cambio y las dos capas hay que mirarlas.
"""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from fdekit.guard import (
    CATALOGO,
    CoberturaGuardia,
    Entrada,
    Guardia,
    Hallazgo,
    Procedencia,
    Veredicto,
    conservacion_de_masa,
    evaluar,
    medir_catalogo,
    no_negativo,
    sonda_guardia,
)


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


def test_bugs_atrapados_sin_medir_no_se_reporta_como_un_cero_medido():
    """Hallazgo 4 de la revision final: el default era 0, y `nota()` publicaba
    'atrapa 0 de 17' sin que nadie hubiera medido nada. Cero es un resultado
    -- medimos y no atrapamos ninguno -- y ausencia de dato no es un resultado.
    Nada en el sistema mapea un episodio a uno de los 17 casos de HANDOFF.md,
    asi que el numerador no existe hasta que alguien lo provea.

    Mata la mutacion de volver el default a 0.
    """
    c = CoberturaGuardia(familias_vigiladas=("anualizacion",))
    assert c.bugs_atrapados is None
    nota = c.nota()
    assert "SIN MEDIR" in nota
    assert "0 de 17" not in nota


def test_un_cero_provisto_por_el_llamador_si_es_un_puntaje():
    """La contracara: si alguien MIDIO y no atrapo ninguno, eso es un dato y se
    publica como tal. La distincion entre 0 y None es el punto entero."""
    nota = CoberturaGuardia(familias_vigiladas=("a",), bugs_atrapados=0).nota()
    assert "0 de 17" in nota
    assert "SIN MEDIR" not in nota


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


# ------------------------------------------------- sonda de dos corridas
#
# Un guardia que solo se corrio sobre datos sanos no prueba nada: el que aprueba
# todo da el mismo resultado que el que funciona. La sonda lo corre dos veces,
# sobre el objeto sano y sobre el mismo objeto con el defecto inyectado. Es
# `sonda_dos_corridas` de Kern (src/bateria/barrido_neteo.py) llevada a los
# guardias.


def _mira_x():
    """Un guardia que de verdad mira el objeto: sano si `x` es positivo."""
    return Guardia(
        nombre="x_positivo",
        motivo="un x negativo es el defecto que se inyecta en la prueba",
        hallazgo=Hallazgo(regla="x positivo", evidencia="x <= 0", procedencia=_proc(),
                          familia="prueba"),
        predicado=lambda obj: obj["x"] > 0,
    )


def test_un_guardia_que_mira_el_objeto_detecta_su_mutacion():
    r = sonda_guardia(_mira_x(), lambda: {"x": 1}, lambda: {"x": -1})
    assert r.veredicto is Veredicto.DETECTA
    assert r.familia == "prueba"


def test_un_guardia_que_siempre_aprueba_es_vacuo():
    """El oraculo vacuo: pasa sobre lo sano y sobre lo roto. Mirado solo sobre
    datos sanos, no se distingue de un guardia que funciona."""
    r = sonda_guardia(_guardia(sano=True), lambda: {"x": 1}, lambda: {"x": -1})
    assert r.veredicto is Veredicto.VACUO


def test_un_guardia_que_siempre_salta_es_falso_positivo():
    r = sonda_guardia(_guardia(sano=False), lambda: {"x": 1}, lambda: {"x": -1})
    assert r.veredicto is Veredicto.FALSO_POSITIVO


def test_una_excepcion_no_cuenta_como_deteccion():
    """`evaluar` reporta como violado al guardia que revienta, para que no apague
    a los demas. Para la sonda eso no es detectar: es no haber podido mirar."""
    r = sonda_guardia(_mira_x(), lambda: {"x": 1}, lambda: {"y": -1})
    assert r.veredicto is Veredicto.REVIENTA
    assert "KeyError" in r.evidencia


def test_un_guardia_que_revienta_sobre_el_sano_no_es_un_falso_positivo():
    r = sonda_guardia(_mira_x(), lambda: {"y": 1}, lambda: {"x": -1})
    assert r.veredicto is Veredicto.REVIENTA


def test_una_mutacion_que_no_cambia_nada_es_sin_medir():
    """Si el mutado es igual al sano no hubo defecto que detectar. Llamarlo
    VACUO acusaria al guardia de algo que no se probo; `sonda_dos_corridas`
    devuelve None en el mismo caso."""
    r = sonda_guardia(_guardia(sano=True), lambda: {"x": 1}, lambda: {"x": 1})
    assert r.veredicto is Veredicto.SIN_MEDIR


def test_detecta_devuelve_el_hallazgo_con_su_procedencia():
    """La deteccion se rastrea hasta el commit: la evidencia lo nombra."""
    r = sonda_guardia(_mira_x(), lambda: {"x": 1}, lambda: {"x": -1})
    assert r.veredicto is Veredicto.DETECTA
    assert "abc1234" in r.evidencia


# ------------------------------------------------------------- catalogo


@pytest.mark.parametrize("entrada", CATALOGO, ids=lambda e: e.guardia.nombre)
def test_ningun_guardia_del_catalogo_es_vacuo(entrada):
    """Cada guardia del catalogo salta sobre su mutacion y no sobre su sano."""
    r = sonda_guardia(entrada.guardia, entrada.fabrica_sano, entrada.fabrica_mutado)
    assert r.veredicto is Veredicto.DETECTA, r.evidencia


def test_el_catalogo_cubre_las_cuatro_familias_pedidas():
    familias = {e.guardia.hallazgo.familia for e in CATALOGO}
    assert familias == {"fanout", "conservacion_de_masa", "no_negatividad", "anualizacion"}


def test_la_nota_publica_lo_que_midio_la_sonda():
    """El conteo de la sonda va en la nota, y no se cuela en `bugs_atrapados`:
    detectar su propia mutacion no es atrapar uno de los 17 bugs historicos."""
    c = medir_catalogo()
    assert "Sondas de dos corridas: 4 de 4" in c.nota()
    assert c.bugs_atrapados is None
    assert "SIN MEDIR" in c.nota()
    assert set(c.familias_vigiladas) == {
        "fanout", "conservacion_de_masa", "no_negatividad", "anualizacion"}


def test_la_nota_nombra_al_guardia_que_no_detecta():
    vacuo = Entrada(_guardia(nombre="aprueba_todo", sano=True), lambda: {"x": 1}, lambda: {"x": -1})
    nota = medir_catalogo(CATALOGO + (vacuo,)).nota()
    assert "Sondas de dos corridas: 4 de 5" in nota
    assert "VACUO: aprueba_todo" in nota


@pytest.mark.parametrize(
    "valor", [None, "", "n/a", float("nan"), float("inf"), "inf", "-Infinity"], ids=repr)
def test_no_negativo_no_lee_un_valor_ilegible_como_sano(valor):
    """Un stock vacio, NaN o infinito no es un stock positivo: el guardia revienta
    y `evaluar` lo reporta como roto. `nan < 0` es falso e `inf >= 0` es verdadero,
    asi que sin este cuidado los dos pasaban como sanos; un infinito sale de una
    division por cero aguas arriba."""
    g = no_negativo(("stock",))
    hallazgos = evaluar([g], [{"stock": 10}, {"stock": valor}])
    assert len(hallazgos) == 1
    assert "reviento" in hallazgos[0].evidencia


def _cadena_103_105():
    return conservacion_de_masa(("ebeln",), "menge", "bwart", entradas=("103",),
                                salidas=("105",))


def test_conservacion_de_masa_lee_codigos_que_llegan_como_numero():
    """Hallazgo de la revision final. Desde pandas, una columna bwart con '103'
    llega como el entero 103 (o 103.0 si hay vacios). Sin normalizar, ninguna
    fila caia en la cadena y el balance vacio daba sano."""
    g = _cadena_103_105()
    for codigo_103, codigo_105 in [(103, 105), (103.0, 105.0), (" 103", "105 ")]:
        filas = [{"ebeln": "45", "bwart": codigo_103, "menge": 50.0},
                 {"ebeln": "45", "bwart": codigo_105, "menge": 999.0}]
        assert evaluar([g], filas) == [g.hallazgo], (codigo_103, codigo_105)


def test_conservacion_de_masa_no_acepta_un_texto_como_lista_de_codigos():
    """`entradas="103"` se leia como los codigos '1', '0' y '3': un guardia que
    aprueba todo."""
    with pytest.raises(TypeError, match="lista de codigos"):
        conservacion_de_masa(("ebeln",), "menge", "bwart", entradas="103", salidas="105")


@pytest.mark.parametrize(
    "filas",
    [
        [{"ebeln": "45", "bwart": "101", "menge": 50.0}],
        [{"ebeln": "45", "bwart": "103", "menge": 50.0},
         {"ebeln": "45", "bwart": None, "menge": 999.0}],
    ],
    ids=["ninguna_fila_de_la_cadena", "movimiento_nulo"],
)
def test_conservacion_de_masa_revienta_si_no_puede_mirar(filas):
    """Filas sin ningun movimiento de la cadena, o con el movimiento en blanco:
    el guardia no vio lo que tenia que vigilar, y eso no es 'sano'."""
    hallazgos = evaluar([_cadena_103_105()], filas)
    assert len(hallazgos) == 1
    assert "reviento" in hallazgos[0].evidencia


def test_fdekit_guard_solo_importa_stdlib():
    """Regla 2: fdekit.guard viaja al notebook prestado de un CD, sin permisos de
    instalacion. Se importa en un proceso nuevo, porque en este ya cargaron
    numpy y pandas otros tests, y compara contra sys.stdlib_module_names."""
    src = Path(__file__).resolve().parents[1] / "src"
    codigo = (
        "import sys; antes = set(sys.modules); import fdekit.guard; "
        "nuevos = {m.split('.')[0] for m in set(sys.modules) - antes}; "
        "print(sorted(nuevos - set(sys.stdlib_module_names) - {'fdekit'}))"
    )
    entorno = {**os.environ, "PYTHONPATH": str(src)}
    salida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                            check=True, env=entorno)
    assert salida.stdout.strip() == "[]"
