import pandas as pd
import pytest

from fdekit.processmining import EventLog, bottlenecks, conformance, rework_summary, variants
from fdekit.processmining.dfg import directly_follows, to_mermaid
from fdekit.processmining.variants import pareto_coverage
from fdekit.synth import DCConfig, generate_dc


def mklog(rows):
    return EventLog(
        pd.DataFrame(rows, columns=["case_id", "activity", "timestamp", "resource", "location"])
    )


@pytest.fixture(scope="module")
def log():
    return EventLog(generate_dc(DCConfig(seed=4, n_orders=400, n_skus=600)).events)


def test_falta_columna_obligatoria_falla():
    with pytest.raises(ValueError, match="faltan columnas"):
        EventLog(pd.DataFrame({"case_id": ["a"], "activity": ["X"]}))


def test_columnas_opcionales_se_rellenan():
    lg = EventLog(pd.DataFrame({"case_id": ["a"], "activity": ["X"], "timestamp": ["2026-01-01"]}))
    assert "resource" in lg.df and "location" in lg.df


def test_dfg_no_cruza_casos():
    """Si el DFG uniera el ultimo evento de un caso con el primero del siguiente,
    inventaria una transicion que no existe. Es el bug clasico de un DFG hecho a
    mano con shift()."""
    lg = mklog(
        [
            ("c1", "A", "2026-01-01 00:00:00", None, None),
            ("c1", "B", "2026-01-01 00:00:10", None, None),
            ("c2", "C", "2026-01-01 00:00:20", None, None),
            ("c2", "D", "2026-01-01 00:00:30", None, None),
        ]
    )
    dfg = directly_follows(lg)
    pares = set(zip(dfg["source"], dfg["target"]))
    assert pares == {("A", "B"), ("C", "D")}
    assert ("B", "C") not in pares


def test_espera_del_dfg_es_correcta():
    lg = mklog(
        [
            ("c1", "A", "2026-01-01 00:00:00", None, None),
            ("c1", "B", "2026-01-01 00:01:00", None, None),
        ]
    )
    dfg = directly_follows(lg)
    assert dfg.loc[0, "median_wait_s"] == 60.0


def test_variantes_colapsadas():
    lg = mklog(
        [
            ("c1", "A", "2026-01-01 00:00:00", None, None),
            ("c1", "A", "2026-01-01 00:00:01", None, None),
            ("c1", "B", "2026-01-01 00:00:02", None, None),
        ]
    )
    v = variants(lg, collapse_repeats=True)
    assert v.loc[0, "variant"] == "A -> B"


def test_conformidad_detecta_actividades_no_declaradas(log):
    c = conformance(log, ["ORDER_RELEASED", "PICK", "CONSOLIDATE", "PACK", "QC", "SHIP"])
    assert 0 <= c["conformance_pct"] <= 100
    assert "CARTON_REWORK" in c["undeclared_activities"]


def test_conformidad_perfecta_da_100():
    lg = mklog(
        [
            ("c1", "A", "2026-01-01 00:00:00", None, None),
            ("c1", "B", "2026-01-01 00:00:01", None, None),
            ("c2", "A", "2026-01-01 00:00:02", None, None),
            ("c2", "B", "2026-01-01 00:00:03", None, None),
        ]
    )
    assert conformance(lg, ["A", "B"])["conformance_pct"] == 100.0


def test_cuellos_ordenados_por_tiempo_total(log):
    b = bottlenecks(log)
    assert b["total_wait_h"].is_monotonic_decreasing
    assert b["pct_of_total_wait"].iloc[0] > 0


def test_reproceso_encuentra_las_actividades_esperadas(log):
    r = rework_summary(log)
    assert set(r["activity"]) >= {"CARTON_REWORK", "REPACK", "SHORT_PICK"}
    assert (r["pct_cases"] <= 100).all()


def test_reproceso_atrapa_la_consecuencia_que_no_se_llama_reproceso(log):
    """Un SHORT_PICK cuesta 50 s de registro y dispara un REPLENISH de ocho
    minutos que retiene al picker. El nombre no matchea ningun patron, asi que
    esas horas se caian enteras del caso economico mientras la tabla mostraba el
    SHORT_PICK como un problema menor: no falla, muestra un numero chico."""
    r = rework_summary(log).set_index("activity")

    assert r.loc["REPLENISH", "rework_kind"] == "consecuencia"
    assert r.loc["SHORT_PICK", "rework_kind"] == "directa"
    # La consecuencia pesa mucho mas que el evento que la nombra.
    assert r.loc["REPLENISH", "hours_lost_in_window"] > r.loc["SHORT_PICK", "hours_lost_in_window"]


def test_el_flujo_normal_no_se_cuela_como_consecuencia(log):
    """PACK sigue a CARTON_REWORK, pero tambien ocurre en los casos sanos. Si el
    umbral dejara entrar una actividad de flujo normal, L2 se duplicaria."""
    r = rework_summary(log)
    assert not {"PACK", "QC", "PICK"} & set(r["activity"])


def test_pasar_la_lista_explicita_desactiva_la_inferencia(log):
    """Si el FDE ya mapeo la taxonomia del cliente, adivinar encima seria peor."""
    r = rework_summary(log, rework_activities=["CARTON_REWORK"])
    assert list(r["activity"]) == ["CARTON_REWORK"]
    assert set(r["rework_kind"]) == {"directa"}


def test_pareto_de_variantes(log):
    p = pareto_coverage(log, target_pct=80)
    assert 1 <= p["variants_needed"] <= p["total_variants"]


def test_mermaid_es_valido(log):
    m = to_mermaid(log, min_freq_pct=2.0)
    assert m.startswith("flowchart TD")
    assert "-->" in m
