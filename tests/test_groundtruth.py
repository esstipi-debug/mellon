"""El residual entre el recorrido calculado y el medido.

Es la razon de ser del toolkit: el kit ya dibuja un espagueti a partir de
aritmetica sobre el layout. Este modulo lo falsifica. Cierra H1 — el proyecto
pasa de tener un modelo a tener un modelo con residual medido.
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
    return EventLog(
        pd.DataFrame(
            [
                {"case_id": "A", "activity": "PICK", "timestamp": T0, "resource": None, "location": "01-002-1"},
                {"case_id": "A", "activity": "PICK", "timestamp": T0 + pd.Timedelta(seconds=60), "resource": None, "location": "01-004-1"},
            ]
        )
    )


def test_residual_cero_cuando_la_medicion_coincide_con_el_modelo():
    # Pista que recorre exactamente 14 m.
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)

    assert r["modeled_m_in_window"] == pytest.approx(14.0)
    assert r["measured_m_in_window"] == pytest.approx(14.0)
    assert r["residual_pct"] == pytest.approx(0.0)


def test_recupera_un_desvio_inyectado():
    # 21 m medidos contra 14 modelados = +50%.
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert r["residual_pct"] == pytest.approx(50.0, abs=0.1)


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


def test_el_residual_no_depende_del_largo_de_la_ventana():
    """Tercer invariante prioritario del spec, seccion 8.

    Es el mismo invariante que el de anualizacion, en su version de camara:
    medir una hora o medir un turno tiene que dar el mismo residual, porque
    modelo y medicion escalan juntos. Si no, el porcentaje que se le muestra al
    cliente depende de cuanto duro la grabacion.
    """
    corta_mod = _log_modelado()
    corta_med = {"sub-a": [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)]}

    # La misma ventana, tres veces: tres pedidos identicos y tres pistas.
    filas = []
    for caso in ("A", "B", "C"):
        filas += [
            {"case_id": caso, "activity": "PICK", "timestamp": T0, "resource": None, "location": "01-002-1"},
            {"case_id": caso, "activity": "PICK", "timestamp": T0 + pd.Timedelta(seconds=60), "resource": None, "location": "01-004-1"},
        ]
    larga_mod = EventLog(pd.DataFrame(filas))
    larga_med = {
        f"sub-{i}": [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)] for i in range(3)
    }

    r_corta = compare_travel(corta_mod, corta_med, LAY, COV, today=HOY)
    r_larga = compare_travel(larga_mod, larga_med, LAY, COV, today=HOY)
    assert r_corta["residual_pct"] == pytest.approx(r_larga["residual_pct"], abs=0.1)
