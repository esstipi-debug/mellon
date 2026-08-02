import json
from pathlib import Path

import numpy as np
import pytest

from fdekit.value import (
    ARCHETYPES,
    SCALES,
    Range,
    ValueCase,
    build_archetype,
    cost_to_serve,
    gainshare_terms,
    levers_from_findings,
    price_band,
)
from fdekit.value.levers import _attr, _knee_savings
from fdekit.value.pricing import model_ladder


@pytest.fixture(scope="module")
def findings():
    p = Path("out/hallazgos.json")
    if not p.exists():
        from fdekit.demo import run_full_diagnosis

        return run_full_diagnosis("out", quiet=True)
    return json.loads(p.read_text(encoding="utf-8"))


def case(findings, key="RETAIL_OMNI", scale="grande", control=True, sites=1):
    arch = build_archetype(key, scale)
    levers = levers_from_findings(findings, arch, has_control_group=control)
    cost = cost_to_serve(70, 900, travel_trips=5)["costo_total_usd"]
    return ValueCase(arch, levers, cost, sites=sites, has_control_group=control)


# ------------------------------------------------------------------- Range


def test_range_muestrea_dentro_de_los_limites():
    rng = np.random.default_rng(0)
    s = Range(1, 2, 5).sample(rng, 5000)
    assert s.min() >= 1 and s.max() <= 5
    assert 1.5 < s.mean() < 3.5


def test_range_puntual_es_constante():
    rng = np.random.default_rng(0)
    s = Range.of(7).sample(rng, 100)
    assert np.all(s == 7)


# -------------------------------------------------------------- arquetipos


def test_la_hora_liberada_vale_menos_que_el_costo_cargado():
    """La variable que decide todo: solo una fraccion de la hora liberada es
    caja. Si esta propiedad se rompe, todo el modelo miente hacia arriba."""
    for a in ARCHETYPES.values():
        assert a.cash_labor_usd_h() < a.labor_usd_h


def test_los_limites_de_flex_share_por_defecto_son_anchos():
    """Sin fuente, el rango tiene que ser generoso. Un rango angosto sobre un
    dato sin origen es peor que no tenerlo."""
    a = build_archetype("RETAIL_OMNI")
    lo, mode, hi = a.labor_flex_bounds()
    assert lo < mode < hi
    assert (hi - lo) / mode > 0.5


def test_flex_share_explicito_reemplaza_el_default():
    from dataclasses import replace

    a = replace(
        build_archetype("RETAIL_OMNI"),
        labor_flex_share=0.30,
        labor_flex_low=0.18,
        labor_flex_high=0.55,
    )
    assert a.labor_flex_bounds() == (0.18, 0.30, 0.55)


def test_la_conversion_a_caja_nunca_pasa_de_uno():
    """Con premio de sobretiempo 1,5x y flex alto, el producto puede exceder 1.
    Una hora liberada no puede valer mas que una hora."""
    from dataclasses import replace

    a = replace(build_archetype("ECOMMERCE"), labor_flex_share=0.9, labor_flex_high=0.95)
    assert max(a.cash_labor_bounds()) <= 1.0


def test_cash_share_como_rango_produce_dispersion(findings):
    import numpy as np

    from fdekit.value.levers import Lever, Range

    lev = Lever(
        "L1_productividad", "x", "h/ano",
        Range.of(1000), Range.of(10),
        cash_share=Range(0.1, 0.3, 0.7),
        attribution=Range.of(1.0), realization=Range.of(1.0),
    )
    total, cash = lev.sample_annual_usd(np.random.default_rng(0), 3000)
    assert np.std(cash) > 0
    assert np.all(cash <= total + 1e-9)
    assert lev.cash_share_mode == 0.3


def test_escala_multiplica_volumen_no_economia_unitaria():
    chico = build_archetype("3PL", "pyme")
    grande = build_archetype("3PL", "grande")
    assert grande.orders_per_day > chico.orders_per_day
    assert grande.revenue_per_order_usd == chico.revenue_per_order_usd
    assert grande.labor_usd_h == chico.labor_usd_h


def test_pyme_tiene_mayor_costo_de_capital():
    assert build_archetype("3PL", "pyme").wacc > build_archetype("3PL", "enterprise").wacc


def test_base_laboral_escala_con_las_lineas():
    a = build_archetype("MAYORISTA", "grande")
    assert a.direct_hours_year == pytest.approx(a.annual_lines / a.lines_per_direct_hour)
    assert a.direct_ftes == pytest.approx(a.direct_hours_year / a.productive_hours_year)
    assert a.annual_labor_cost_usd > 0


def test_reducir_la_jornada_cambia_dotacion_no_costo():
    """Con 42 h/semana hacen falta mas personas para el mismo trabajo, pero el
    trabajo —y por lo tanto la base de costo— es el mismo. Confundir las dos
    cosas es como se justifica mal una reduccion de dotacion."""
    from dataclasses import replace

    a = build_archetype("MAYORISTA", "grande")
    b = replace(a, productive_hours_year=1_873.0)
    assert b.direct_ftes > a.direct_ftes
    assert b.annual_labor_cost_usd == pytest.approx(a.annual_labor_cost_usd)


def test_arquetipo_desconocido_falla():
    with pytest.raises(KeyError, match="arquetipo desconocido"):
        build_archetype("NO_EXISTE")


# ----------------------------------------------------------------- palancas


def test_sin_grupo_de_control_la_atribucion_se_castiga():
    """Es el argumento economico completo de la herramienta 6 en un assert."""
    con, sin = _attr(True), _attr(False)
    assert con.mode > sin.mode * 2
    assert (sin.high - sin.low) > (con.high - con.low)  # mas ignorancia, rango mas ancho


def test_las_palancas_declaran_su_fuente(findings):
    levers = levers_from_findings(findings, build_archetype("3PL"), has_control_group=True)
    assert levers
    assert all(l.source for l in levers), "una palanca sin herramienta que la mida no entra"


def test_arquetipo_sin_inventario_no_genera_palanca_de_capital(findings):
    lev3pl = levers_from_findings(findings, build_archetype("3PL"))
    assert "L5_capital" not in {l.key for l in lev3pl}  # el stock no es del 3PL
    lev_may = levers_from_findings(findings, build_archetype("MAYORISTA"))
    assert "L5_capital" in {l.key for l in lev_may}


def test_rodilla_de_la_curva_de_dimensionamiento():
    sweep = [
        {"n_pickers": 4, "mean_cycle_min": 90},
        {"n_pickers": 5, "mean_cycle_min": 39},
        {"n_pickers": 6, "mean_cycle_min": 12},
        {"n_pickers": 7, "mean_cycle_min": 9.6},
        {"n_pickers": 8, "mean_cycle_min": 9.6},
        {"n_pickers": 9, "mean_cycle_min": 9.5},
    ]
    # la rodilla esta en 6: de 6 a 7 la mejora es 20% (>5%), de 7 a 8 es 0%
    assert _knee_savings(sweep) == 2  # 9 - 7


def test_rodilla_con_datos_insuficientes():
    assert _knee_savings([]) == 0.0


# -------------------------------------------------------------------- caso


def test_simulacion_determinista(findings):
    a = case(findings).simulate(2000)
    b = case(findings).simulate(2000)
    assert np.allclose(a.npv_usd, b.npv_usd)


def test_caja_nunca_supera_el_total(findings):
    r = case(findings).simulate(3000)
    assert np.all(r.annual_cash_usd <= r.annual_total_usd + 1e-6)


def test_rollout_multisitio_es_sublineal():
    """El sitio 2 nunca rinde como el sitio 1. Asumir linealidad es como se
    firma un contrato multi-sitio que no cierra en el ano 2."""
    c = ValueCase(build_archetype("3PL"), [], 0.0, sites=8)
    assert 1 < c.benefit_multiplier < 8
    assert 1 < c.cost_multiplier < 8


def test_el_costo_baja_mas_rapido_que_el_beneficio_al_sumar_sitios():
    """Es la razon economica del rollout: el descubrimiento se hace una vez. Si
    las dos curvas fueran iguales, sumar sitios no mejoraria nada y el consejo
    de 'subir la escala' que da el modelo seria falso."""
    c = ValueCase(build_archetype("3PL"), [], 0.0, sites=6)
    assert c.cost_multiplier < c.benefit_multiplier
    assert c.cost_multiplier / c.benefit_multiplier < 0.7


def test_un_solo_sitio_no_altera_nada():
    c = ValueCase(build_archetype("3PL"), [], 0.0, sites=1)
    assert c.benefit_multiplier == 1.0
    assert c.cost_multiplier == 1.0


def test_sin_beneficio_no_hay_payback(findings):
    arch = build_archetype("3PL")
    c = ValueCase(arch, [], cost_to_serve_usd=500_000)
    r = c.simulate(500)
    assert not np.isfinite(np.median(r.payback_months))
    assert np.all(r.npv_usd < 0)
    assert any("no hay payback" in x for x in c.warnings(r))


def test_alerta_cuando_la_atribucion_es_alta_sin_control(findings):
    arch = build_archetype("RETAIL_OMNI")
    # atribucion alta declarada a mano, sin contrafactual
    levers = levers_from_findings(findings, arch, has_control_group=True)
    c = ValueCase(arch, levers, 60_000, has_control_group=False)
    assert any("sin grupo de control" in x for x in c.warnings(c.simulate(1000)))


def test_alerta_cuando_las_horas_prometidas_son_implausibles():
    """Un caso que promete recortar una fraccion grande de las horas de la
    operacion tiene que gritar antes de llegar a la reunion."""
    from fdekit.value.levers import Lever

    arch = build_archetype("MANUFACTURA", "pyme")
    absurdo = arch.direct_ftes * 2_000 * 0.5  # medio ano-hombre por cada FTE
    lev = Lever(
        "L1_productividad", "Horas recuperadas", "h/ano",
        Range.of(absurdo), Range.of(arch.labor_usd_h),
        cash_share=0.3, attribution=Range.of(0.9), realization=Range.of(1.0),
    )
    c = ValueCase(arch, [lev], 50_000, has_control_group=True)
    assert any("base de costo laboral" in x for x in c.warnings(c.simulate(800)))


def test_no_alerta_cuando_las_horas_son_plausibles():
    from fdekit.value.levers import Lever

    arch = build_archetype("MANUFACTURA", "pyme")
    modesto = arch.direct_ftes * 2_000 * 0.03
    lev = Lever(
        "L1_productividad", "Horas recuperadas", "h/ano",
        Range.of(modesto), Range.of(arch.labor_usd_h),
        cash_share=0.3, attribution=Range.of(0.8), realization=Range.of(0.7),
    )
    c = ValueCase(arch, [lev], 50_000, has_control_group=True)
    assert not any("base de costo laboral" in x for x in c.warnings(c.simulate(800)))


# ------------------------------------------------------------------ precio


def test_gainshare_no_es_viable_sin_contrafactual(findings):
    r = case(findings, control=False).simulate(1500)
    p = price_band(r, "gainshare", has_control_group=False)
    assert p["viable"] is False
    assert p["alternativa"] == "tiempo_materiales"


def test_gainshare_viable_con_contrafactual(findings):
    r = case(findings, control=True, sites=4).simulate(1500)
    p = price_band(r, "gainshare", has_control_group=True)
    assert p["viable"] is True
    assert p["banda_precio_anual_usd"][0] <= p["banda_precio_anual_usd"][1]


def test_un_solo_sitio_no_sostiene_gainshare(findings):
    """No es un defecto del modelo: 70 dias de FDE contra un solo CD no dejan
    margen para cobrar por resultado. El modelo lo dice en vez de emitir una
    banda degenerada."""
    r = case(findings, control=True, sites=1).simulate(1500)
    p = price_band(r, "gainshare", has_control_group=True)
    assert p["viable"] is False
    assert "subir la escala" in " ".join(p["salidas"])


def test_el_precio_nunca_baja_del_piso_por_margen(findings):
    r = case(findings, control=True, sites=6).simulate(1500)
    p = price_band(r, "hitos_por_resultado", has_control_group=True, min_margin_pct=0.4)
    assert p["viable"], p.get("motivo")
    assert p["banda_precio_anual_usd"][0] >= p["piso_por_margen_usd"]
    assert p["piso_por_margen_usd"] > p["costo_de_servir_usd"]


def test_si_el_costo_de_servir_come_el_beneficio_el_modelo_no_es_viable(findings):
    """Sin esta rama el modelo emite una banda degenerada que captura el 90% del
    beneficio del cliente y se ve razonable en una planilla."""
    arch = build_archetype("3PL", "pyme")
    levers = levers_from_findings(findings, arch, has_control_group=True)
    c = ValueCase(arch, levers, cost_to_serve_usd=400_000, has_control_group=True)
    p = price_band(c.simulate(1500), "gainshare", has_control_group=True)
    assert p["viable"] is False
    assert p["captura_requerida_pct"] > 30
    assert p["salidas"]


def test_gainshare_degenerado_se_declara_precio_fijo(findings):
    arch = build_archetype("3PL", "pyme")
    levers = levers_from_findings(findings, arch, has_control_group=True)
    r = ValueCase(arch, levers, cost_to_serve_usd=300_000, has_control_group=True).simulate(1500)
    t = gainshare_terms(r, share_pct=0.05)  # share ridiculo: el piso domina todo
    assert t["es_precio_fijo_disfrazado"] is True
    assert "precio fijo" in t["advertencia"]


def test_gainshare_sano_diferencia_los_escenarios(findings):
    r = case(findings, "RETAIL_OMNI", control=True, sites=3).simulate(2000)
    t = gainshare_terms(r, share_pct=0.20, floor_usd=50_000)
    assert t["es_precio_fijo_disfrazado"] is False
    assert t["pago_escenario_p90_usd"] > t["pago_escenario_p10_usd"]
    assert t["pago_escenario_p90_usd"] <= t["techo_anual_usd"]


def test_tiempo_materiales_no_requiere_medicion(findings):
    r = case(findings, control=False).simulate(1000)
    assert price_band(r, "tiempo_materiales", has_control_group=False)["viable"]


def test_modelo_desconocido_falla(findings):
    r = case(findings).simulate(500)
    with pytest.raises(KeyError, match="modelo desconocido"):
        price_band(r, "trueque")


def test_gainshare_el_piso_cubre_el_costo_en_el_peor_escenario(findings):
    r = case(findings, control=True).simulate(2000)
    t = gainshare_terms(r, share_pct=0.2)
    assert t["pago_escenario_p10_usd"] >= t["piso_anual_usd"]
    assert t["pago_escenario_p50_usd"] >= t["pago_escenario_p10_usd"]
    assert len(t["clausulas_obligatorias"]) >= 5


def test_costo_de_servir_incluye_overhead():
    c = cost_to_serve(100, 900, travel_trips=8, trip_cost_usd=1500, overhead_pct=0.2)
    directo = 100 * 900 + 8 * 1500
    assert c["costo_total_usd"] == pytest.approx(directo * 1.2, rel=1e-3)


def test_la_escalera_de_precio_se_sube_no_se_salta():
    assert model_ladder(False, 2) == "tiempo_materiales"
    assert model_ladder(False, 18) == "precio_fijo"
    assert model_ladder(True, 6) == "hitos_por_resultado"
    assert model_ladder(True, 24) == "gainshare"


def test_cada_arquetipo_produce_un_perfil_de_palancas_distinto(findings):
    """El mismo hallazgo vale plata distinta segun quien lo reciba. Si todos los
    arquetipos dieran el mismo ranking, el modelo no estaria aportando nada."""
    top = {}
    for k in ("3PL", "MAYORISTA"):
        r = case(findings, k, control=True).simulate(2000)
        top[k] = r.per_lever.iloc[0]["key"]
    assert top["3PL"] != top["MAYORISTA"]
