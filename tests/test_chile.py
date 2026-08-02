"""Validacion de la calibracion Chile 2026.

Estos tests no verifican que el codigo corra: verifican que la aritmetica legal
chilena este bien puesta. Si la ley cambia, tienen que fallar — para eso estan.
"""

import pytest

from fdekit.value import ARCHETYPES, build_archetype
from fdekit.value.chile import (
    FX_CLP_USD,
    GRATIFICACION_TOPE,
    IMM,
    JORNADA_SEMANAL_H,
    chilean_archetypes,
    comparacion_defaults,
    costo_operario_bodega,
    horas_productivas_ano,
    ingreso_3pl_por_pedido_usd,
    parametros_sin_verificar,
)


# --------------------------------------------------------------- la jornada


def test_jornada_vigente_es_42_horas():
    """Ley 21.561, segunda etapa desde el 26-abr-2026. Cuando entre la tercera
    (40 h, abril 2028) este test tiene que fallar y obligar a actualizar."""
    assert JORNADA_SEMANAL_H.valor == 42.0


def test_horas_productivas_bajo_las_2000_del_default():
    h = horas_productivas_ano()
    assert 1_800 < h["horas_productivas"] < 1_950
    assert h["vs_default_2000h"] < -0.04  # el default de EE.UU. sobreestima >4%


def test_menos_jornada_menos_horas_por_persona():
    h42 = horas_productivas_ano(42.0)["horas_productivas"]
    h40 = horas_productivas_ano(40.0)["horas_productivas"]
    assert h40 < h42


def test_el_ausentismo_descuenta():
    sin = horas_productivas_ano(ausentismo=0.0)["horas_productivas"]
    con = horas_productivas_ano(ausentismo=0.10)["horas_productivas"]
    assert con == pytest.approx(sin * 0.9, rel=1e-3)


# ------------------------------------------------------------------ el costo


def test_el_sueldo_base_supera_el_minimo_legal():
    c = costo_operario_bodega()
    assert c["sueldo_base_clp"] >= IMM.valor, "el default no puede estar bajo el IMM vigente"


def test_gratificacion_se_topea_en_sueldos_altos():
    """Sobre ~$853k de base la gratificacion deja de ser 25% y se congela en el
    tope de 4,75 IMM anuales. Ignorarlo sobreestima el costo de los cargos
    medios."""
    bajo = costo_operario_bodega(sueldo_base_clp=560_000)
    alto = costo_operario_bodega(sueldo_base_clp=1_200_000)
    assert not bajo["gratificacion_topeada"]
    assert alto["gratificacion_topeada"]
    assert alto["gratificacion_clp"] == GRATIFICACION_TOPE.valor


def test_el_factor_costo_empresa_esta_en_el_rango_conocido():
    """El costo empresa en Chile va entre 1,45x y 1,75x el sueldo base una vez
    sumadas gratificacion, cargas y provisiones. Fuera de ese rango hay un error
    de estructura, no de parametro."""
    f = costo_operario_bodega()["factor_sobre_sueldo_base"]
    assert 1.45 < f < 1.75


def test_las_provisiones_se_pueden_excluir():
    con = costo_operario_bodega()
    sin = costo_operario_bodega(incluir_provisiones=False)
    assert sin["costo_empresa_mensual_clp"] < con["costo_empresa_mensual_clp"]
    assert sin["provisiones_clp"] == 0


def test_costo_hora_chileno_es_la_mitad_del_default_generico():
    """La correccion mas grande de toda la validacion: los defaults genericos
    eran cifras de EE.UU./frontera, no de Santiago."""
    usd_h = costo_operario_bodega()["costo_hora_productiva_usd"]
    assert 5.0 < usd_h < 8.0
    assert usd_h < ARCHETYPES["ECOMMERCE"].labor_usd_h * 0.7


def test_el_tipo_de_cambio_esta_en_el_rango_observado_2026():
    assert 850 <= FX_CLP_USD.valor <= 935


# ------------------------------------------------------------------- 3PL


def test_el_flete_no_entra_al_ingreso_de_fulfillment():
    """Incluir el flete de traspaso duplica el denominador y hace ver chico un
    beneficio que respecto del negocio real es grande."""
    sin = ingreso_3pl_por_pedido_usd(incluir_flete=False)
    con = ingreso_3pl_por_pedido_usd(incluir_flete=True)
    assert con["total_usd"] > sin["total_usd"] * 1.8
    assert sin["flete_clp"] == 0


def test_el_ingreso_3pl_incluye_la_tarifa_publica_de_pickpack():
    r = ingreso_3pl_por_pedido_usd()
    assert r["pickpack_clp"] == 850.0
    assert r["total_usd"] < ARCHETYPES["3PL"].revenue_per_order_usd  # el default estaba alto


# ------------------------------------------------------------ arquetipos


def test_la_calibracion_chilena_baja_el_costo_laboral_en_todos():
    ch = chilean_archetypes()
    for k, base in ARCHETYPES.items():
        assert ch[k].labor_usd_h < base.labor_usd_h, k


def test_la_calibracion_chilena_usa_la_jornada_chilena():
    for a in chilean_archetypes().values():
        assert a.productive_hours_year == pytest.approx(
            horas_productivas_ano()["horas_productivas"]
        )


def test_el_ticket_ecommerce_sube_respecto_del_default():
    """El default de USD 41 estaba a la mitad del ticket real chileno."""
    ch = chilean_archetypes()
    assert ch["ECOMMERCE"].revenue_per_order_usd > ARCHETYPES["ECOMMERCE"].revenue_per_order_usd


def test_build_archetype_acepta_la_calibracion():
    gen = build_archetype("3PL", "grande", calibration="generico")
    chi = build_archetype("3PL", "grande", calibration="chile")
    assert chi.labor_usd_h < gen.labor_usd_h
    assert chi.orders_per_day == gen.orders_per_day  # la escala no cambia


def test_calibracion_desconocida_falla():
    with pytest.raises(KeyError, match="calibracion desconocida"):
        build_archetype("3PL", calibration="peru")


# -------------------------------------------------------------- honestidad


def test_la_comparacion_reporta_todos_los_cambios():
    filas = comparacion_defaults()
    assert filas
    campos = {f["parametro"] for f in filas}
    assert {"labor_usd_h", "revenue_per_order_usd", "wacc"} <= campos
    assert all(f["delta_pct"] is not None for f in filas)


def test_los_parametros_sin_fuente_se_declaran():
    """Un parametro sin origen no deja de ser un supuesto por estar escrito en
    Python. El modulo tiene que poder decir cuales son."""
    pend = parametros_sin_verificar()
    assert pend
    assert {"AUSENTISMO", "MUTUAL", "WACC_USD_GRANDE"} <= {p["parametro"] for p in pend}
    assert all(p["como_conseguirlo"] for p in pend), "cada supuesto necesita como resolverlo"
