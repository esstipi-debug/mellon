"""El contrato de `hallazgos.json`: que lee el caso economico y que pasa si falta.

El archivo tiene unas treinta secciones y el caso economico toca once campos.
El contrato es lo que se LEE, no lo que se escribe — que es lo que lo vuelve
util para un productor distinto de `fdekit demo`.
"""

import pytest

from fdekit.value import build_archetype, levers_from_findings
from fdekit.value.contract import (
    CONTRACT_VERSION,
    FINDINGS_CONTRACT,
    findings_contract,
)


def test_el_demo_cumple_el_contrato_entero(findings):
    """El productor de referencia no puede estar fuera de su propio contrato.

    Si esto falla, o el demo dejo de emitir un bloque o alguien renombro un
    campo consumido sin subir `CONTRACT_VERSION`.
    """
    c = findings_contract(findings)
    assert c["parciales"] == ()
    assert set(c["completas"]) == set(FINDINGS_CONTRACT)
    assert c["cuadra"] is True


def test_un_bloque_ausente_marca_la_palanca_como_parcial(findings):
    """El unico caso que miente: la palanca aparece, pero le falta un termino."""
    sin_travel = {k: v for k, v in findings.items() if k != "travel"}
    c = findings_contract(sin_travel)

    assert c["parciales"] == ("L1_productividad",)
    assert c["palancas"]["L1_productividad"]["estado"] == "PARCIAL"
    assert "travel.walking_hours_in_window" in c["palancas"]["L1_productividad"]["ausentes"]
    # Las otras cinco no se contagian.
    assert c["palancas"]["L2_reproceso"]["estado"] == "COMPLETA"


def test_la_palanca_parcial_efectivamente_sale_subestimada(findings):
    """La mitad que le da sentido al contrato.

    Un contrato que dice 'falta un campo' sin que eso cambie ningun numero es
    burocracia. Este test mide el dano: sin el bloque `travel`, L1 pierde la
    caminata excedente, sigue apareciendo con la brecha de trabajo estandar y
    las horas de gemba, y nada en el resultado la distingue de una L1 entera.

    Es el mismo modo de falla que `_reject_preannualized` dice existir para
    proteger, en el caso que esa funcion no cubre: no una clave vieja, sino un
    bloque que nunca vino.
    """
    arch = build_archetype("RETAIL_OMNI", "grande")
    sin_travel = {k: v for k, v in findings.items() if k != "travel"}

    def l1(f):
        return next(
            (x for x in levers_from_findings(f, arch) if x.key == "L1_productividad"), None
        )

    entera, mocha = l1(findings), l1(sin_travel)

    # Sigue existiendo -- ese es el problema, no un bug.
    assert mocha is not None, "si desapareciera se notaria; el peligro es que no"
    assert mocha.annual_units.mode < entera.annual_units.mode

    # Y lo unico que lo declara es el contrato.
    assert findings_contract(sin_travel)["parciales"] == ("L1_productividad",)
    assert findings_contract(findings)["parciales"] == ()


def test_presente_y_en_cero_no_es_lo_mismo_que_ausente(findings):
    """`rework: []` es una medicion; sin la clave `rework` no se midio nada.

    Tratar las dos igual es como se convierte 'no sabemos' en 'es cero', que es
    la regla dura 1 al reves. Misma semantica de tres estados que
    `Observation.in_event_log`.
    """
    medido_vacio = {**findings, "rework": []}
    nunca_medido = {k: v for k, v in findings.items() if k != "rework"}

    assert findings_contract(medido_vacio)["palancas"]["L2_reproceso"]["estado"] == "COMPLETA"
    assert findings_contract(nunca_medido)["palancas"]["L2_reproceso"]["estado"] == "PARCIAL"


def test_una_fila_sin_el_campo_esperado_no_cuenta_como_presente(findings):
    """Lista con filas del formato equivocado es ausencia, no presencia.

    Es el caso de un productor externo que emite `rework` con otro esquema: la
    clave esta, el bloque parece medido, y el campo que se lee no existe.
    """
    otro_esquema = {**findings, "rework": [{"actividad": "PACK", "horas": 3.0}]}
    c = findings_contract(otro_esquema)
    assert c["palancas"]["L2_reproceso"]["estado"] == "PARCIAL"
    assert "rework[].hours_lost_in_window" in c["palancas"]["L2_reproceso"]["ausentes"]


def test_findings_vacio_no_deja_ninguna_parcial():
    """El caso extremo ya era seguro y tiene que seguir siendolo.

    Sin nada, ninguna palanca se calcula, asi que ninguna puede subestimarse.
    Pareja con `test_findings_vacio_no_inventa_una_palanca` en test_timestudy.
    """
    c = findings_contract({})
    assert c["parciales"] == ()
    assert set(c["ausentes"]) == set(FINDINGS_CONTRACT)
    assert c["cuadra"] is True


@pytest.mark.parametrize("palanca,campos", sorted(FINDINGS_CONTRACT.items()))
def test_cada_campo_declarado_existe_en_la_salida_real(palanca, campos, findings):
    """El contrato no puede declarar campos que el productor no emite.

    Un campo de mas en `FINDINGS_CONTRACT` marcaria PARCIAL para siempre y el
    aviso se volveria ruido que nadie lee.
    """
    from fdekit.value.contract import _presente

    faltan = [c for c in campos if not _presente(findings, c)]
    assert not faltan, f"{palanca} declara campos que el demo no emite: {faltan}"


def test_la_version_del_contrato_esta_declarada():
    assert isinstance(CONTRACT_VERSION, int)
    assert findings_contract({})["contract_version"] == CONTRACT_VERSION
