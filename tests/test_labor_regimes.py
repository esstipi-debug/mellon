"""Calibracion de labor_flex_share — estudio de 4 paises del 1-ago-2026.

Los rangos que se testean aca son los del REFUTADOR, no los del investigador.
El refutador bajo tres de las cuatro estimaciones, y en Chile a la mitad. Si
alguien los sube sin traer fuente nueva, estos tests fallan.
"""

import pytest

from fdekit.value import ARCHETYPES, ValueCase, build_archetype, cost_to_serve, levers_from_findings
from fdekit.value.labor_regimes import (
    REGIMES,
    STAFFING_MODELS,
    apply_regime,
    flex_bounds,
    regime_table,
)


def test_los_cuatro_paises_estan_calibrados():
    assert set(REGIMES) == {"usa", "australia", "chile", "argentina"}


def test_todo_regimen_tiene_fuentes_driver_y_caveats():
    """Un rango sin fuente y sin caveats es un prior con pretensiones."""
    for r in REGIMES.values():
        assert r.sources, r.country
        assert r.caveats, r.country
        assert len(r.driver) > 40, r.country


def test_los_rangos_son_coherentes_y_anchos():
    for r in REGIMES.values():
        assert 0 < r.low < r.mode < r.high <= 1.0, r.country
        # El estudio entrego rangos anchos a proposito: un rango angosto sobre
        # parametros que ninguna estadistica publica cubre seria falsa precision.
        assert r.spread >= 2.0, r.country


def test_estados_unidos_es_el_mas_flexible():
    tabla = regime_table()
    assert tabla[0]["pais"] == "Estados Unidos"
    assert REGIMES["usa"].mode > REGIMES["chile"].mode
    assert REGIMES["usa"].mode > REGIMES["australia"].mode


def test_argentina_es_el_mas_incierto():
    """Su moda sobrevive por compensacion de dos errores de signo opuesto, no
    porque el modelo sea correcto. Eso tiene que verse en el rango."""
    spreads = {k: r.spread for k, r in REGIMES.items()}
    assert max(spreads, key=spreads.get) == "argentina"
    assert any("FRAGIL" in c for c in REGIMES["argentina"].caveats)


def test_chile_registra_el_error_de_run_rate_vs_caja():
    """Es el error mas caro del estudio y no puede perderse del registro."""
    assert any("run-rate" in c for c in REGIMES["chile"].caveats)
    assert REGIMES["chile"].run_rate_ref > REGIMES["chile"].mode


def test_el_run_rate_siempre_supera_la_caja_del_primer_ano():
    for r in REGIMES.values():
        assert r.run_rate_ref > r.mode, r.country


def test_australia_documenta_que_su_linea_base_esta_medida_en_el_valle():
    assert any("VALLE" in c or "valle" in c for c in REGIMES["australia"].caveats)


# ------------------------------------------------------ modelo de dotacion


def test_el_volumen_comprometido_es_el_peor_caso():
    peor = min(STAFFING_MODELS, key=lambda k: STAFFING_MODELS[k]["delta"][0])
    assert peor == "3pl_volumen_comprometido"


def test_open_book_supera_a_planta_propia_y_a_volumen_comprometido():
    propia = flex_bounds("chile", "planta_propia")[1]
    open_book = flex_bounds("chile", "3pl_open_book")[1]
    comprometido = flex_bounds("chile", "3pl_volumen_comprometido")[1]
    assert comprometido < propia < open_book


def test_el_contrato_manda_sobre_el_pais():
    """Un 3PL open-book en Chile puede tener mas flexibilidad de caja que
    planta propia en EE.UU. Es el hallazgo que reordena el modelo."""
    chile_open = flex_bounds("chile", "3pl_open_book")[1]
    usa_propia = flex_bounds("usa", "planta_propia")[1]
    assert chile_open >= usa_propia * 0.95


def test_closed_book_casi_no_mueve_la_caja_del_primer_ano():
    """La eficiencia se captura solo en la renegociacion de tarifa, tipicamente
    en el aniversario del contrato."""
    propia = flex_bounds("usa", "planta_propia")[1]
    closed = flex_bounds("usa", "3pl_closed_book")[1]
    assert 0 <= closed - propia <= 0.05


def test_los_limites_quedan_acotados_a_cero_uno():
    for pais in REGIMES:
        for modelo in STAFFING_MODELS:
            lo, mode, hi = flex_bounds(pais, modelo)
            assert 0.0 <= lo <= mode <= hi <= 1.0, (pais, modelo)


def test_pais_o_modelo_desconocido_falla():
    with pytest.raises(KeyError, match="regimen laboral desconocido"):
        flex_bounds("peru")
    with pytest.raises(KeyError, match="modelo de dotacion desconocido"):
        flex_bounds("chile", "handshake")


# --------------------------------------------------------- integracion


def test_apply_regime_deja_la_procedencia_escrita():
    a = apply_regime(ARCHETYPES["3PL"], "australia", "mix")
    assert a.labor_regime == "australia"
    assert a.staffing_model == "mix"
    assert a.labor_flex_bounds() == flex_bounds("australia", "mix")


def test_build_archetype_toma_el_regimen_chileno_por_defecto():
    a = build_archetype("3PL", calibration="chile")
    assert a.labor_regime == "chile"
    assert a.labor_flex_share == REGIMES["chile"].mode


def test_el_regimen_y_la_calibracion_son_ejes_independientes():
    """Hay costo verificado solo para Chile, pero regimen laboral para cuatro
    paises. Fusionarlos daria a entender que hay datos de costo que no existen."""
    a = build_archetype("3PL", calibration="chile", labor_regime="usa")
    assert a.labor_regime == "usa"
    assert a.labor_usd_h < 8  # sigue siendo el costo chileno


def test_el_arquetipo_ya_no_diferencia_la_flexibilidad(findings=None):
    """El estudio es claro: la institucion que manda es la clausula del
    contrato, no el rubro de la empresa."""
    flex = {
        k: build_archetype(k, calibration="chile").labor_flex_share
        for k in ("3PL", "RETAIL_OMNI", "ECOMMERCE", "MANUFACTURA", "MAYORISTA")
    }
    assert len(set(flex.values())) == 1


def test_el_recargo_de_sobretiempo_ya_no_se_aplica_a_la_fraccion_completa():
    """La correccion que destapo el estudio: `labor_flex_share` esta calibrado
    en HORAS, y el recargo aplica solo a las que eran extra. Multiplicar la
    fraccion entera por 1,5x llegaba a topar en 1,0 — una hora liberada
    valiendo mas que una hora trabajada."""
    a = build_archetype("ECOMMERCE", calibration="chile", labor_regime="usa")
    assert a.overtime_premium > 1
    assert a.cash_labor_bounds() == a.labor_flex_bounds()
    assert max(a.cash_labor_bounds()) < 1.0
