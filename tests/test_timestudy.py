"""Herramienta 2 — estudio de tiempos, espagueti y anualizacion.

El modulo alimenta la palanca L1 del caso economico y no tenia ni un test. El
bloque `test_anualizacion` de abajo es el que importa: la unidad con la que
`timestudy` habla con `value` es la ventana observada, nunca el ano. Anualizar
en los dos lados es el bug que no falla y solo miente.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fdekit.layout import DOCK, Layout
from fdekit.processmining.log import EventLog
from fdekit.timestudy import (
    cycle_time_stats,
    cycle_times,
    location_frequency,
    operator_variation,
    plot_heatmap,
    plot_spaghetti,
    slotting_opportunity,
    standard_work_gap,
    takt_analysis,
    travel_report,
    travel_stats,
)
from fdekit.value import ARCHETYPES, build_archetype, levers_from_findings

T0 = pd.Timestamp("2026-03-02 08:00:00")
LAY = Layout(aisles=4, bays=10, levels=2, aisle_pitch=3.0, bay_pitch=1.0)


def make_log(rows: list[tuple]) -> EventLog:
    """rows = (case_id, activity, offset_s, resource, location)."""
    return EventLog(
        pd.DataFrame(
            [
                {
                    "case_id": c,
                    "activity": a,
                    "timestamp": T0 + pd.Timedelta(seconds=off),
                    "resource": r,
                    "location": loc,
                }
                for c, a, off, r, loc in rows
            ]
        )
    )


# --------------------------------------------------------------- cycle_times


def test_cycle_time_stats_mide_punta_a_punta_no_suma_de_pasos():
    # Dos casos: 100 s y 300 s de lead time. Los eventos intermedios no cuentan.
    log = make_log(
        [
            ("A", "RELEASE", 0, None, None),
            ("A", "PICK", 40, "PICK-1", "01-002-1"),
            ("A", "SHIP", 100, None, None),
            ("B", "RELEASE", 0, None, None),
            ("B", "SHIP", 300, None, None),
        ]
    )
    s = cycle_time_stats(log)

    assert s["n_cases"] == 2
    assert s["median_min"] == pytest.approx(200 / 60, abs=0.01)
    assert s["mean_min"] == pytest.approx(200 / 60, abs=0.01)
    # p90 sobre [100, 300] = 280 -> indice = 280/200 = 1.4
    assert s["variability_index"] == pytest.approx(1.4, abs=0.01)


def test_variability_index_sobre_2_5_marca_proceso_inestable():
    # Cola larga: 8 casos de 60 s y 2 de 600 s. El indice es p90/p50, asi que
    # hace falta que la cola llegue al percentil 90 para que se note — con un
    # solo caso lento sobre diez el indice da 1.9 y el proceso pasa por estable.
    rows = []
    for i in range(8):
        rows += [(f"C{i}", "RELEASE", 0, None, None), (f"C{i}", "SHIP", 60, None, None)]
    for i in (8, 9):
        rows += [(f"C{i}", "RELEASE", 0, None, None), (f"C{i}", "SHIP", 600, None, None)]

    assert cycle_time_stats(make_log(rows))["variability_index"] > 2.5


# ---------------------------------------------------------------------- takt


def test_takt_analysis_con_ventana_y_demanda_explicitas():
    log = make_log(
        [
            ("A", "RELEASE", 0, None, None),
            ("A", "SHIP", 600, None, None),
            ("B", "RELEASE", 0, None, None),
            ("B", "SHIP", 600, None, None),
        ]
    )
    t = takt_analysis(log, demand_units=100, available_hours=10.0)

    assert t["takt_s"] == pytest.approx(360.0)  # 10 h / 100 unidades
    assert t["throughput_per_hour"] == pytest.approx(10.0)
    assert t["median_cycle_s"] == pytest.approx(600.0)
    assert t["cycle_over_takt"] == pytest.approx(600 / 360, abs=0.01)


def test_takt_analysis_no_revienta_con_ventana_de_duracion_cero():
    # Un log exportado con el timestamp truncado al dia deja todo en el mismo
    # instante. Es un log malo, pero la herramienta tiene que decirlo, no
    # explotar con ZeroDivisionError en la sala del cliente.
    log = make_log(
        [
            ("A", "RELEASE", 0, None, None),
            ("A", "SHIP", 0, None, None),
            ("B", "RELEASE", 0, None, None),
            ("B", "SHIP", 0, None, None),
        ]
    )
    t = takt_analysis(log)

    assert t["window_hours"] == 0.0
    assert t["takt_s"] is None
    assert t["cycle_over_takt"] is None
    assert "ventana" in t["warning"].lower()


# -------------------------------------------------------- operator_variation


def _pick_log() -> EventLog:
    """8 casos, 4 operadores, 2 picks cada uno, duraciones limpias."""
    rows = []
    for i, (op, dur) in enumerate(
        [("A", 100), ("A", 100), ("B", 200), ("B", 200), ("C", 300), ("C", 300), ("D", 400), ("D", 400)]
    ):
        cid = f"O{i}"
        rows += [
            (cid, "RELEASE", 0, None, None),
            (cid, "PICK", dur, f"PICK-{op}", "01-002-1"),
            (cid, "PACK", dur + 50, "PACK-9", None),
        ]
    return make_log(rows)


def test_operator_variation_atribuye_la_duracion_al_delta_previo():
    ov = operator_variation(_pick_log(), "PICK", "PICK-")

    assert list(ov["resource"]) == ["PICK-A", "PICK-B", "PICK-C", "PICK-D"]
    assert list(ov["n"]) == [2, 2, 2, 2]
    assert list(ov["median_s"]) == [100.0, 200.0, 300.0, 400.0]
    # vs_best se mide contra el mejor mediano, no contra el promedio.
    assert list(ov["vs_best_pct"]) == [0.0, 100.0, 200.0, 300.0]


def test_operator_variation_filtra_por_rol_y_no_mezcla_pack_con_pick():
    ov = operator_variation(_pick_log(), "PACK", "PACK-")
    assert list(ov["resource"]) == ["PACK-9"]
    assert ov.loc[0, "n"] == 8

    # Sin el prefijo correcto no hay a quien atribuir: DataFrame vacio, no error.
    assert operator_variation(_pick_log(), "PICK", "PACK-").empty
    assert operator_variation(_pick_log(), "ACTIVIDAD_INEXISTENTE").empty


def test_operator_variation_no_cruza_el_limite_de_caso():
    # El PICK de B viene justo despues del SHIP de A. Si la resta cruzara el
    # limite de caso, la duracion de B seria 10 s en vez de 250 s.
    log = make_log(
        [
            ("A", "RELEASE", 0, None, None),
            ("A", "SHIP", 990, None, None),
            ("B", "RELEASE", 750, None, None),
            ("B", "PICK", 1000, "PICK-1", "01-002-1"),
        ]
    )
    ov = operator_variation(log, "PICK", "PICK-")
    assert ov.loc[0, "median_s"] == pytest.approx(250.0)


# --------------------------------------------------------- standard_work_gap


def test_standard_work_gap_usa_el_p25_como_meta_no_al_mejor():
    g = standard_work_gap(_pick_log(), "PICK", "PICK-")

    assert g["operators"] == 4
    # np.percentile([100,200,300,400], 25) = 175, no 100.
    assert g["target_median_s"] == pytest.approx(175.0)
    assert g["worst_median_s"] == pytest.approx(400.0)
    assert g["spread_pct"] == pytest.approx(300.0)

    # exceso = (0 + 25 + 125 + 225) x 2 picks = 750 s
    assert g["recoverable_hours_in_window"] == pytest.approx(750 / 3600, abs=0.01)


def test_standard_work_gap_expone_su_denominador_y_no_anualiza():
    g = standard_work_gap(_pick_log(), "PICK", "PICK-")

    # Anualizar aca obliga a hardcodear los dias de operacion, que son del
    # arquetipo del cliente y no del log. La conversion vive en value/levers.
    assert "recoverable_hours_annual" not in g
    assert g["cases_in_window"] == 8


def test_standard_work_gap_sin_datos_devuelve_vacio():
    assert standard_work_gap(_pick_log(), "ACTIVIDAD_INEXISTENTE") == {}


# ------------------------------------------------------------------- travel


def _travel_log() -> EventLog:
    return make_log(
        [
            ("A", "RELEASE", 0, None, None),
            ("A", "PICK", 60, "PICK-1", "01-002-1"),
            ("A", "PICK", 120, "PICK-1", "01-004-1"),
            ("A", "SHIP", 200, None, DOCK),
            ("B", "RELEASE", 0, None, None),
            ("B", "PICK", 60, "PICK-2", "02-003-1"),
            ("B", "SHIP", 200, None, DOCK),
        ]
    )


def test_travel_report_reconstruye_la_ruta_con_ida_y_vuelta_al_dock():
    t = travel_report(_travel_log(), LAY).set_index("case_id")

    # A: DOCK->01-002-1 (5) + ->01-004-1 (2) + ->DOCK (7) = 14 m en 2 paradas
    assert t.loc["A", "distance_m"] == pytest.approx(14.0)
    assert t.loc["A", "n_stops"] == 2
    assert t.loc["A", "m_per_stop"] == pytest.approx(7.0)
    # B: DOCK->02-003-1 (9) + vuelta (9) = 18 m
    assert t.loc["B", "distance_m"] == pytest.approx(18.0)


def test_travel_report_no_cuenta_el_dock_como_parada():
    t = travel_report(_travel_log(), LAY)
    assert int(t["n_stops"].sum()) == 3  # 2 de A + 1 de B, el SHIP en DOCK no


def test_travel_stats_expone_su_denominador_y_no_anualiza():
    s = travel_stats(_travel_log(), LAY, walk_speed=1.1)

    assert s["orders"] == 2
    assert s["total_km"] == pytest.approx(0.03, abs=0.005)
    assert s["walking_hours_in_window"] == pytest.approx(32 / 1.1 / 3600, abs=1e-4)
    assert "walking_hours_annual" not in s


def test_cycle_times_devuelve_una_fila_por_caso():
    c = cycle_times(_travel_log())
    assert list(c.columns) == ["case_id", "start", "end", "cycle_time_s", "n_events"]
    assert len(c) == 2


def test_los_graficos_se_dibujan_y_se_guardan(tmp_path):
    # El espagueti es el grafico que abre la boca del gerente de operaciones:
    # si revienta en la sala, no hay diagnostico. Smoke test, sin backend GUI.
    log = _travel_log()
    for fn, nombre in ((plot_spaghetti, "espagueti.png"), (plot_heatmap, "calor.png")):
        destino = tmp_path / nombre
        fn(log, LAY, path=str(destino))
        assert destino.exists() and destino.stat().st_size > 0


def test_el_espagueti_no_revienta_sin_rutas_que_dibujar():
    # Un log sin picks (solo recepcion, p.ej.) da cero rutas. Eje vacio, no error.
    vacio = make_log([("A", "RECEIVE", 0, None, None), ("A", "PUTAWAY", 60, None, None)])
    assert plot_spaghetti(vacio, LAY) is not None


def test_location_frequency_solo_cuenta_picks():
    f = location_frequency(_travel_log()).set_index("location")
    assert set(f.index) == {"01-002-1", "01-004-1", "02-003-1"}
    assert DOCK not in f.index


def test_slotting_opportunity_premia_mover_la_clase_a_a_la_zona_dorada():
    master = pd.DataFrame(
        [
            {"sku_id": "S1", "home_location": "01-002-1", "abc_class": "C"},
            {"sku_id": "S2", "home_location": "01-004-1", "abc_class": "C"},
            # La clase A esta en el fondo del pasillo 4: el caso de manual.
            {"sku_id": "S3", "home_location": "04-009-1", "abc_class": "A"},
        ]
    )
    log = make_log(
        [
            ("A", "RELEASE", 0, None, None),
            ("A", "PICK", 60, "PICK-1", "01-002-1"),
            ("B", "RELEASE", 0, None, None),
            ("B", "PICK", 60, "PICK-2", "04-009-1"),
            ("C", "RELEASE", 0, None, None),
            ("C", "PICK", 60, "PICK-2", "04-009-1"),
        ]
    )
    s = slotting_opportunity(log, master, LAY)

    assert s["class_a_share_of_visits_pct"] == pytest.approx(66.7, abs=0.1)
    assert s["class_a_already_in_golden_pct"] == pytest.approx(0.0)
    assert s["reduction_pct"] > 0
    assert s["mean_weighted_distance_after_m"] < s["mean_weighted_distance_now_m"]


# ------------------------------------------------------------ anualizacion


def _findings(orders: int, walk_h: float, sw_h: float, slot_cut_pct: float = 10.0) -> dict:
    return {
        "cycle_times": {"n_cases": orders},
        "travel": {"orders": orders, "walking_hours_in_window": walk_h},
        "slotting": {"reduction_pct": slot_cut_pct},
        "standard_work_gap": {"recoverable_hours_in_window": sw_h, "cases_in_window": orders},
    }


def _l1(findings: dict, arch) -> float:
    levers = levers_from_findings(findings, arch, has_control_group=True)
    return next(l for l in levers if l.key == "L1_productividad").annual_units.mode


def test_l1_anual_no_depende_del_largo_de_la_ventana_observada():
    """El invariante que faltaba.

    Medir un turno o medir un mes tiene que dar la misma cifra anual, porque las
    horas y los pedidos observados escalan juntos. Si no, el numero que se le
    muestra al cliente depende de cuantos dias de log mando TI.
    """
    arch = build_archetype("RETAIL_OMNI", "grande")

    turno = _findings(orders=500, walk_h=20.0, sw_h=6.0)
    mes = _findings(orders=500 * 30, walk_h=20.0 * 30, sw_h=6.0 * 30)

    assert _l1(turno, arch) == pytest.approx(_l1(mes, arch), rel=1e-9)


def test_l1_anual_escala_con_los_pedidos_anuales_del_arquetipo():
    """Y el factor es exactamente annual_orders, sin residuo de 250 vs 300.

    Este es el numero que va adelante del cliente. La forma vieja lo dejaba
    multiplicado por 250/operating_days: con el default de 300 salia 17% bajo,
    en silencio, y se movia si el arquetipo cambiaba los dias de operacion.
    """
    arch = build_archetype("RETAIL_OMNI", "grande")
    f = _findings(orders=500, walk_h=20.0, sw_h=6.0, slot_cut_pct=10.0)

    walk_anual = 20.0 / 500 * arch.annual_orders
    sw_anual = 6.0 / 500 * arch.annual_orders
    esperado = walk_anual * 0.10 + sw_anual

    assert _l1(f, arch) == pytest.approx(esperado, rel=1e-9)


@pytest.mark.parametrize("key", sorted(ARCHETYPES))
def test_l1_es_insensible_a_los_dias_de_operacion_del_arquetipo(key):
    """Los dias de operacion mueven el volumen anual, no la tasa por pedido.

    Antes `operating_days` entraba dos veces con signos distintos y el residuo
    250/dias se colaba en la cifra final.
    """
    arch = build_archetype(key, "grande")
    f = _findings(orders=500, walk_h=20.0, sw_h=6.0)

    horas_por_pedido = (20.0 * 0.10 + 6.0) / 500
    assert _l1(f, arch) == pytest.approx(horas_por_pedido * arch.annual_orders, rel=1e-9)


def test_l1_usa_el_denominador_propio_de_travel_no_el_de_cycle_times():
    """No todos los casos del log tienen picks.

    Si 500 casos pasaron por el CD pero solo 400 tuvieron lineas de picking, las
    horas de caminata se reparten entre 400, no entre 500. Dividir por el
    denominador equivocado subestima la caminata por pedido.
    """
    arch = build_archetype("RETAIL_OMNI", "grande")
    f = _findings(orders=500, walk_h=20.0, sw_h=0.0)
    f["travel"]["orders"] = 400

    esperado = 20.0 / 400 * arch.annual_orders * 0.10
    assert _l1(f, arch) == pytest.approx(esperado, rel=1e-9)


def test_hallazgos_con_el_formato_viejo_fallan_ruidosamente():
    """Regla 3 del repo: no mentir en silencio.

    Un `hallazgos.json` de antes del cambio ya no trae `*_hours_in_window` donde
    corresponde. Leerlo con `.get(..., 0.0)` haria desaparecer L1 del caso
    economico sin una linea de aviso — el modo de falla mas caro que tiene este
    repo. Tiene que reventar y decir que hay que regenerar.
    """
    arch = build_archetype("RETAIL_OMNI", "grande")
    viejo = {
        "cycle_times": {"n_cases": 500},
        "travel": {"orders": 500, "walking_hours_annual": 5000.0},
        "slotting": {"reduction_pct": 10.0},
        "standard_work_gap": {"recoverable_hours_annual": 1500.0},
    }

    with pytest.raises(ValueError, match="regenerar"):
        levers_from_findings(viejo, arch, has_control_group=True)


def test_findings_vacio_no_inventa_una_palanca():
    arch = build_archetype("RETAIL_OMNI", "grande")
    levers = levers_from_findings({}, arch, has_control_group=True)
    assert not [l for l in levers if l.key == "L1_productividad"]


def test_l1_es_cero_si_no_hay_pedidos_observados():
    # Division por cero disfrazada: sin denominador no hay tasa, y una tasa
    # inventada es peor que una palanca ausente.
    arch = build_archetype("RETAIL_OMNI", "grande")
    f = _findings(orders=0, walk_h=20.0, sw_h=6.0)
    assert not [l for l in levers_from_findings(f, arch) if l.key == "L1_productividad"]


def test_numpy_no_se_cuela_en_los_hallazgos():
    # `hallazgos.json` se serializa con json.dump; un np.float64 pasa, pero un
    # np.int64 no. Los dos modulos tienen que devolver tipos nativos.
    g = standard_work_gap(_pick_log(), "PICK", "PICK-")
    s = travel_stats(_travel_log(), LAY)
    for d in (g, s):
        for k, v in d.items():
            assert not isinstance(v, (np.integer, np.floating)), f"{k} es numpy"
