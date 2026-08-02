import pytest

from fdekit.a3 import A3
from fdekit.gemba import GembaSession, Observation
from fdekit.standardwork import JobBreakdown


def test_tipo_de_desperdicio_invalido_falla():
    with pytest.raises(ValueError, match="waste_type"):
        Observation(area="a", activity="b", waste_type="INVENTADO", description="x")


def test_impacto_requiere_duracion_y_frecuencia():
    sin = Observation(area="a", activity="b", waste_type="ESPERA", description="x")
    assert sin.impact_h_per_shift == 0.0

    con = Observation(
        area="a", activity="b", waste_type="ESPERA", description="x",
        duration_s=60, frequency_per_shift=30, operators_affected=2,
    )
    assert con.impact_h_per_shift == pytest.approx(60 * 30 * 2 / 3600)
    assert con.impact_h_per_year == pytest.approx(con.impact_h_per_shift * 250)


def test_sesion_persiste_y_recarga(tmp_path):
    p = tmp_path / "g.jsonl"
    s = GembaSession(p, site="CD", observer="fde")
    s.add(Observation(area="a", activity="b", waste_type="DEFECTO", description="x",
                      duration_s=10, frequency_per_shift=5))
    assert len(GembaSession(p)) == 1


def test_pareto_excluye_no_cuantificadas_y_las_reporta(tmp_path):
    s = GembaSession(tmp_path / "g.jsonl", site="CD")
    s.add(Observation(area="a", activity="b", waste_type="DEFECTO", description="medido",
                      duration_s=100, frequency_per_shift=10))
    s.add(Observation(area="a", activity="c", waste_type="ESPERA", description="sin medir"))

    par = s.pareto()
    assert set(par["waste_type"]) == {"DEFECTO"}
    assert par.loc[0, "cum_pct"] == 100.0
    assert len(s.unquantified()) == 1


def test_pareto_ordenado_descendente(tmp_path):
    s = GembaSession(tmp_path / "g.jsonl")
    s.add(Observation(area="a", activity="b", waste_type="DEFECTO", description="chico",
                      duration_s=10, frequency_per_shift=1))
    s.add(Observation(area="a", activity="b", waste_type="ESPERA", description="grande",
                      duration_s=600, frequency_per_shift=50))
    par = s.pareto()
    assert par.loc[0, "waste_type"] == "ESPERA"
    assert par["hours_per_year"].is_monotonic_decreasing


def test_twi_exige_una_razon_por_punto_clave():
    jb = JobBreakdown(task="t", role="r", escalation="lider")
    jb.add("paso", ["punto a", "punto b"], ["razon a"])
    assert any("razon" in i for i in jb.validate())


def test_twi_exige_escalamiento():
    jb = JobBreakdown(task="t", role="r")
    jb.add("paso", ["p"], ["r"])
    assert any("escalamiento" in i for i in jb.validate())


def test_twi_hoja_valida_no_tiene_problemas():
    jb = JobBreakdown(task="t", role="r", escalation="lider de turno")
    jb.add("paso", ["p"], ["r"], target_time_s=30)
    assert jb.validate() == []
    assert "| 1 | paso |" in jb.to_markdown()


def test_twi_rechaza_hojas_muy_largas():
    jb = JobBreakdown(task="t", role="r", escalation="lider")
    for i in range(15):
        jb.add(f"paso {i}", ["p"], ["r"])
    assert any("12" in i for i in jb.validate())


def test_a3_exige_numeros_en_la_condicion_actual():
    a3 = A3(title="t", owner="o")
    a3.current_condition = ["el proceso es lento"]
    a3.target_condition = ["que sea rapido"]
    a3.root_cause = ["porque si"]
    assert any("numero" in i for i in a3.validate())


def test_a3_exige_dueno_y_fecha_en_contramedidas():
    a3 = A3(title="t", owner="o")
    a3.current_condition = ["reproceso 12%"]
    a3.target_condition = ["bajar a 5%"]
    a3.root_cause = ["maestro errado"]
    a3.add_countermeasure("arreglar", "", "", "menos reproceso")
    assert any("dueno" in i for i in a3.validate())


def test_a3_valido_no_tiene_problemas():
    a3 = A3(title="t", owner="o")
    a3.current_condition = ["reproceso 12% de los pedidos"]
    a3.target_condition = ["bajar a 5% en 90 dias"]
    a3.root_cause = ["dimensiones del maestro erradas"]
    a3.add_countermeasure("corregir maestro clase A", "cliente", "semana 3", "-7pp de reproceso")
    assert a3.validate() == []
    assert "# A3 — t" in a3.to_markdown()
