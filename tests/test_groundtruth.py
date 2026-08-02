"""El residual entre el recorrido calculado y el medido.

Es la razon de ser del toolkit: el kit ya dibuja un espagueti a partir de
aritmetica sobre el layout. Este modulo lo falsifica. Cierra H1 — el proyecto
pasa de tener un modelo a tener un modelo con residual medido.

Ronda de arreglo 1 (revision del coordinador) agrego cobertura para dos bugs
de la misma familia que el bug de anualizacion: comparar totales con
denominadores distintos, y no distinguir "error del modelo" de "la camara no
cubre el muelle".
"""

from datetime import date

import pandas as pd
import pytest

from fdekit.field.coverage import MeasurementCoverage
from fdekit.field.tracks import TrackPoint
from fdekit.groundtruth import compare_travel
from fdekit.layout import DOCK, Layout
from fdekit.processmining.log import EventLog

LAY = Layout(aisles=4, bays=10, levels=2, aisle_pitch=3.0, bay_pitch=1.0)
T0 = pd.Timestamp("2026-09-14 10:00:00")
HOY = date(2026, 9, 14)
COV = MeasurementCoverage(frames_total=100, frames_with_marker=100, tracks_seen=1)


def _log_modelado() -> EventLog:
    # Un pedido: DOCK -> 01-002-1 -> 01-004-1 -> DOCK = 5 + 2 + 7 = 14 m
    # (leg al dock 5 + tramo interno 2 + leg al dock 7 = 12 m de dock legs)
    return EventLog(
        pd.DataFrame(
            [
                {"case_id": "A", "activity": "PICK", "timestamp": T0, "resource": None, "location": "01-002-1"},
                {"case_id": "A", "activity": "PICK", "timestamp": T0 + pd.Timedelta(seconds=60), "resource": None, "location": "01-004-1"},
            ]
        )
    )


def _log_de_n_pedidos_identicos(n: int) -> EventLog:
    """n copias del pedido de `_log_modelado`, cada una con su propio case_id."""
    filas = []
    for i in range(n):
        caso = f"caso-{i}"
        filas += [
            {"case_id": caso, "activity": "PICK", "timestamp": T0, "resource": None, "location": "01-002-1"},
            {"case_id": caso, "activity": "PICK", "timestamp": T0 + pd.Timedelta(seconds=60), "resource": None, "location": "01-004-1"},
        ]
    return EventLog(pd.DataFrame(filas))


def _pista_realista_14m() -> list[TrackPoint]:
    """Pista de varias muestras que sigue el mismo camino que el modelo calcula.

    DOCK(0,0) -> transversal a x=3 (3 m) -> sube a y=2 (2 m) = leg al dock,
    5 m. Luego 01-002-1(3,2) -> 01-004-1(3,4): 2 m internos. Luego baja a
    y=0 (4 m) -> transversal de vuelta a x=0 (3 m) = leg al dock, 7 m.
    Total 3+2+2+4+3 = 14 m, igual al modelo -- pero como pista real de
    camara, no como un solo segmento fabricado a medida (eso es lo que
    escondia el bug de denominadores: una pista de UN segmento nunca puede
    mostrar que "medido == modelado" es sospechoso, no perfecto).
    """
    return [
        TrackPoint(0.0, 0.0, 0.0),
        TrackPoint(1.0, 3.0, 0.0),
        TrackPoint(2.0, 3.0, 2.0),
        TrackPoint(3.0, 3.0, 4.0),
        TrackPoint(4.0, 3.0, 0.0),
        TrackPoint(5.0, 0.0, 0.0),
    ]


def test_residual_cero_cuando_la_medicion_coincide_con_el_modelo():
    r = compare_travel(_log_modelado(), {"sub-a": _pista_realista_14m()}, LAY, COV, today=HOY)

    assert r["modeled_m_in_window"] == pytest.approx(14.0)
    assert r["measured_m_in_window"] == pytest.approx(14.0)
    assert r["residual_pct"] == pytest.approx(0.0)
    # Coincidencia exacta cae dentro del margen de "cercano a cero": el
    # modelo es un piso, asi que un empate perfecto es sospechoso, no ideal.
    assert r["residual_flag"] == "sospechoso"


def test_recupera_un_desvio_inyectado():
    # 21 m medidos contra 14 modelados = +50%.
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert r["residual_pct"] == pytest.approx(50.0, abs=0.1)
    assert r["residual_flag"] == "esperado"
    assert "piso" in r["residual_flag_reason"].lower()


def test_siempre_devuelve_la_nota_de_cobertura():
    """Regla 3. Un residual sin cobertura no se publica."""
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert "no tratar" in r["coverage_note"].lower()


def test_no_devuelve_ningun_campo_anual():
    """Regla 8: la anualizacion vive en value/levers, y en ningun otro lado."""
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert not [k for k in r if "annual" in k or "anual" in k]


def test_no_lee_el_reloj():
    """Regla 4: `today` es argumento."""
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert r["today"] == "2026-09-14"


def test_sin_medicion_no_inventa_un_residual():
    r = compare_travel(_log_modelado(), {}, LAY, COV, today=HOY)
    assert r["measured_m_in_window"] == 0.0
    assert r["residual_pct"] is None
    assert r["residual_flag"] == "sin_medicion"


def test_el_residual_no_depende_del_largo_de_la_ventana():
    """Tercer invariante prioritario del spec, seccion 8.

    Es el mismo invariante que el de anualizacion, en su version de camara:
    medir una hora o medir un turno tiene que dar el mismo residual, porque
    modelo y medicion escalan juntos. Si no, el porcentaje que se le muestra al
    cliente depende de cuanto duro la grabacion. El residual se calcula sobre
    tasas por pedido (arreglo 1), asi que el invariante se cumple por
    construccion: promediar tres pedidos identicos da la misma tasa que uno.
    """
    corta_mod = _log_modelado()
    corta_med = {"sub-a": [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)]}

    larga_mod = _log_de_n_pedidos_identicos(3)
    larga_med = {
        f"sub-{i}": [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)] for i in range(3)
    }

    r_corta = compare_travel(corta_mod, corta_med, LAY, COV, today=HOY)
    r_larga = compare_travel(larga_mod, larga_med, LAY, COV, today=HOY)
    assert r_corta["residual_pct"] == pytest.approx(r_larga["residual_pct"], abs=0.1)


# --------------------------------------------------------- arreglo 1: tasas


def test_denominadores_distintos_no_inventan_un_residual_falso():
    """El caso exacto que reporto el revisor: 100 pedidos modelados, 40
    medidos, MISMO recorrido por pedido (14 m). Antes del arreglo, comparar
    totales (1400 vs 560) daba -60% -- el modelo parecia sobreestimar un 60%
    cuando en realidad predecia perfecto. Comparando tasas por pedido
    (14 vs 14) el residual es 0%, no -60%.
    """
    modelado = _log_de_n_pedidos_identicos(100)
    medido = {f"sub-{i}": _pista_realista_14m() for i in range(40)}

    r = compare_travel(modelado, medido, LAY, COV, today=HOY)

    assert r["orders_modeled"] == 100
    assert r["orders_measured"] == 40
    assert r["modeled_m_in_window"] == pytest.approx(1400.0)
    assert r["measured_m_in_window"] == pytest.approx(560.0)
    assert r["modeled_m_per_order"] == pytest.approx(14.0)
    assert r["measured_m_per_order"] == pytest.approx(14.0)
    assert r["residual_pct"] == pytest.approx(0.0, abs=0.1)


def test_totals_note_advierte_que_los_totales_no_se_comparan_directo():
    """Regla del arreglo 1: los totales solos, sin la advertencia al lado,
    son como alguien los resta a mano y se equivoca -- exactamente el bug
    que este mismo modulo tenia."""
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    nota = r["totals_note"].lower()
    assert "no son comparables" in nota
    assert "modeled_m_per_order" in r["totals_note"]


# ----------------------------------------------------- arreglo 2: dock legs


def test_dock_legs_se_exponen_por_separado_del_total_modelado():
    r = compare_travel(_log_modelado(), {"sub-a": _pista_realista_14m()}, LAY, COV, today=HOY)
    # leg 1 (DOCK->01-002-1) = 5, leg 2 (01-004-1->DOCK) = 7, total 12 de 14.
    assert r["dock_legs_m_in_window"] == pytest.approx(12.0)
    assert r["dock_legs_pct_of_modeled"] == pytest.approx(12.0 / 14.0 * 100, abs=0.1)


def test_medicion_que_no_cubre_el_muelle_se_ve_en_dock_legs_no_solo_en_el_residual():
    """La camara mira solo la zona de estanterias: la pista mide unicamente
    el tramo interno (2 m de 01-002-1 a 01-004-1), sin los dos tramos al
    dock. El residual sale muy negativo, pero `dock_legs_pct_of_modeled`
    (85.7%) le dice a quien lee que gran parte de lo modelado es
    precisamente lo que la camara no cubrio -- no error del modelo."""
    puntos = [TrackPoint(0.0, 3.0, 2.0), TrackPoint(1.0, 3.0, 4.0)]  # solo el tramo interno
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)

    assert r["measured_m_in_window"] == pytest.approx(2.0)
    assert r["dock_legs_m_in_window"] == pytest.approx(12.0)
    assert r["dock_legs_pct_of_modeled"] == pytest.approx(85.7, abs=0.1)
    assert r["residual_pct"] < -50  # muy negativo: no es que el modelo se equivoque
    assert r["residual_flag"] == "sospechoso"


# ------------------------------------------------- arreglo 4: modelo_no_vio_nada


def test_modelo_no_vio_nada_con_medicion_positiva_es_el_hallazgo_mas_fuerte():
    """El modelo predice cero (no hay lineas de PICK en el log) y la camara
    midio 30 m: no es un residual indefinido cualquiera, es recorrido 100%
    invisible al WMS. Antes del arreglo se descartaba junto con sin_medicion."""
    log_sin_picks = EventLog(
        pd.DataFrame(
            [{"case_id": "A", "activity": "ARRIVE", "timestamp": T0, "resource": None, "location": DOCK}]
        )
    )
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 30.0)]
    r = compare_travel(log_sin_picks, {"sub-a": puntos}, LAY, COV, today=HOY)

    assert r["modeled_m_in_window"] == 0.0
    assert r["orders_modeled"] == 0
    assert r["measured_m_in_window"] == pytest.approx(30.0)
    assert r["residual_pct"] is None
    assert r["residual_flag"] == "modelo_no_vio_nada"
    assert r["residual_flag"] != "sin_medicion"


# ------------------------------ arreglo final: medicion_contaminada (bloqueante)


COV_CONTAMINADA = MeasurementCoverage(
    frames_total=100, frames_with_marker=100, tracks_seen=1, discarded_out_of_bounds=100
)


def test_puntos_descartados_dan_medicion_contaminada_aunque_el_residual_sea_positivo():
    """El caso que hoy decia "esperado" con confianza, y era falso.

    El punto fuera de planta se descarta de las PARADAS pero sigue entero en
    el NUMERADOR de metros (`track_distance_m` suma la pista cruda). Sobre el
    mismo recorrido real, el salto de 500 m da un residual enorme y POSITIVO,
    que sin este arreglo cae en "esperado" -- y el motivo le explica al lector
    que el numero es coherente con que el modelo sea un piso. El flag se daba
    vuelta justo por el defecto que `max_distance_m` existe para detectar.
    """
    # 500 m medidos contra 14 modelados: +3471%, muy por encima del margen.
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 500.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV_CONTAMINADA, today=HOY)

    assert r["residual_pct"] > 0
    assert r["residual_flag"] == "medicion_contaminada"
    assert r["residual_flag"] != "esperado"


def test_puntos_descartados_ganan_tambien_sobre_sospechoso():
    """La contaminacion tiene precedencia sobre LOS DOS flags de lectura.

    Con residual negativo el flag "sospechoso" no seria falso, pero apunta a
    la causa equivocada: manda a revisar cobertura cuando lo que hay es un
    numerador con metros que no son recorrido.
    """
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 2.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV_CONTAMINADA, today=HOY)

    assert r["residual_pct"] < 0
    assert r["residual_flag"] == "medicion_contaminada"


def test_el_motivo_de_contaminada_dice_cuantos_puntos_y_que_igual_sumaron_metros():
    """Regla 3: el motivo no puede ser un rotulo, tiene que decir el defecto.

    Tres cosas: cuantos puntos se descartaron, que esos puntos IGUAL aportaron
    metros al numerador, y que por eso el residual no se lee hasta recalibrar
    la homografia.
    """
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 500.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV_CONTAMINADA, today=HOY)

    motivo = r["residual_flag_reason"]
    assert "100 punto" in motivo
    assert "METROS" in motivo
    assert "homografia" in motivo
    assert "measured_m_in_window" in motivo
    # Y no se cuela el texto del flag que este reemplaza.
    assert "coherente con que el modelo" not in motivo


def test_sin_puntos_descartados_los_flags_de_siempre_siguen_saliendo():
    """El flag nuevo no se come los dos existentes cuando la medicion esta limpia."""
    limpia = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)]
    r = compare_travel(_log_modelado(), {"sub-a": limpia}, LAY, COV, today=HOY)
    assert r["residual_flag"] == "esperado"


def test_la_contaminacion_no_pisa_sin_medicion_ni_modelo_no_vio_nada():
    """Ninguno de los dos publica un residual_pct: no hay numero que contaminar."""
    sin_med = compare_travel(_log_modelado(), {}, LAY, COV_CONTAMINADA, today=HOY)
    assert sin_med["residual_flag"] == "sin_medicion"

    log_sin_picks = EventLog(
        pd.DataFrame(
            [{"case_id": "A", "activity": "ARRIVE", "timestamp": T0, "resource": None, "location": DOCK}]
        )
    )
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 30.0)]
    sin_modelo = compare_travel(log_sin_picks, {"sub-a": puntos}, LAY, COV_CONTAMINADA, today=HOY)
    assert sin_modelo["residual_flag"] == "modelo_no_vio_nada"


# --------------------------------------------------------------- bordes


def test_log_modelado_vacio_no_rompe():
    log_vacio = EventLog(
        pd.DataFrame(columns=["case_id", "activity", "timestamp", "resource", "location"])
    )
    r = compare_travel(log_vacio, {}, LAY, COV, today=HOY)
    assert r["orders_modeled"] == 0
    assert r["modeled_m_in_window"] == 0.0
    assert r["dock_legs_m_in_window"] == 0.0
    assert r["residual_flag"] == "sin_medicion"


def test_pista_de_un_solo_punto_no_aporta_distancia_medida():
    """Una pista con una sola muestra no tiene ningun segmento que medir
    (`track_distance_m` suma entre pares consecutivos). Se cuenta como un
    viaje visto (orders_measured=1) que aporto 0 m, no como ausencia de
    medicion -- son preguntas distintas."""
    puntos = [TrackPoint(0.0, 0.0, 0.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert r["measured_m_in_window"] == 0.0
    assert r["orders_measured"] == 1
    assert r["residual_pct"] == pytest.approx(-100.0)
    assert r["residual_flag"] == "sospechoso"


def test_frames_total_cero_no_rompe_el_calculo():
    cov_vacia = MeasurementCoverage(frames_total=0, frames_with_marker=0, tracks_seen=0)
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, cov_vacia, today=HOY)
    assert "no tratar" in r["coverage_note"].lower()
    assert r["residual_pct"] is not None


# ------------------------------------------- arreglo final: track_pct computable


def test_track_pct_deja_de_ser_none_cuando_hay_log_modelado():
    """El criterio de exito de la etapa 3 del spec necesita un denominador de
    PEDIDOS, y `compare_travel` lo tenia en la mano sin usarlo. Lo que se
    reportaba era cobertura de CUADROS, que responde otra pregunta: el marcador
    puede verse el 100% del tiempo y haberse capturado 2 de 100 viajes."""
    assert COV.track_pct is None

    modelado = _log_de_n_pedidos_identicos(10)
    medido = {f"sub-{i}": _pista_realista_14m() for i in range(4)}
    cov = MeasurementCoverage(frames_total=100, frames_with_marker=100, tracks_seen=4)

    r = compare_travel(modelado, medido, LAY, cov, today=HOY)

    assert r["orders_modeled"] == 10
    # 4 pistas reconstruidas sobre 10 pedidos declarados por el WMS.
    assert r["track_pct"] == pytest.approx(40.0)
    assert "40.0% de los viajes esperados" in r["coverage_note"]


def test_track_pct_queda_en_none_cuando_el_modelo_no_vio_nada():
    """`tracks_expected=0` con pistas vistas es incoherente para
    `MeasurementCoverage`, y con razon: "0% de 0 pedidos esperados" no describe
    nada. Ese caso es el hallazgo `modelo_no_vio_nada`, y la respuesta honesta
    para track_pct es None, no un porcentaje fabricado."""
    log_sin_picks = EventLog(
        pd.DataFrame(
            [{"case_id": "A", "activity": "ARRIVE", "timestamp": T0, "resource": None, "location": DOCK}]
        )
    )
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 30.0)]
    r = compare_travel(log_sin_picks, {"sub-a": puntos}, LAY, COV, today=HOY)

    assert r["residual_flag"] == "modelo_no_vio_nada"
    assert r["track_pct"] is None
