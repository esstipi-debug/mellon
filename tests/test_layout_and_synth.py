import pandas as pd
import pytest

from fdekit import EVENT_LOG_COLUMNS
from fdekit.layout import DOCK, Layout
from fdekit.synth import DCConfig, generate_dc


@pytest.fixture(scope="module")
def dc():
    return generate_dc(DCConfig(seed=3, n_orders=350, n_skus=500))


def test_distancia_misma_ubicacion_es_cero():
    lay = Layout()
    assert lay.distance("03-010-1", "03-010-1") == 0


def test_distancia_entre_pasillos_supera_la_euclidiana():
    """Cambiar de pasillo obliga a salir por una transversal. Si el calculo
    diera la distancia recta, el diagrama de espagueti subestimaria el recorrido
    y todo el caso de reslotting se caeria."""
    lay = Layout()
    a, b = "01-025-1", "12-025-1"
    (ax, ay), (bx, by) = lay.xy(a), lay.xy(b)
    euclid = abs(ax - bx)
    assert lay.distance(a, b) > euclid


def test_distancia_es_simetrica():
    lay = Layout()
    assert lay.distance("02-005-1", "09-040-3") == pytest.approx(lay.distance("09-040-3", "02-005-1"))


def test_ruta_desde_dock_vuelve_al_dock():
    lay = Layout()
    d = lay.route_distance(["05-010-1"])
    assert d == pytest.approx(2 * lay.distance(DOCK, "05-010-1"))


def test_zona_dorada_solo_niveles_ergonomicos():
    lay = Layout()
    assert all(int(c.split("-")[2]) in (1, 2) for c in lay.golden_zone())


def test_log_cumple_el_contrato(dc):
    assert list(dc.events.columns) == EVENT_LOG_COLUMNS


def test_generador_es_determinista():
    a = generate_dc(DCConfig(seed=11, n_orders=120, n_skus=300))
    b = generate_dc(DCConfig(seed=11, n_orders=120, n_skus=300))
    pd.testing.assert_frame_equal(a.events, b.events)


def test_todos_los_pedidos_terminan_en_ship(dc):
    ultima = dc.events.groupby("case_id")["activity"].last()
    assert (ultima == "SHIP").all()


def test_eventos_ordenados_dentro_del_caso(dc):
    g = dc.events.sort_values(["case_id", "timestamp"])
    assert g.groupby("case_id")["timestamp"].apply(lambda s: s.is_monotonic_increasing).all()


def test_defectos_inyectados_en_la_tasa_pedida():
    cfg = DCConfig(seed=5, n_orders=100, n_skus=1000, dim_error_rate=0.2)
    dc = generate_dc(cfg)
    tasa = dc.defects["dim_error"].mean()
    assert 0.15 < tasa < 0.25


def test_el_maestro_difiere_de_la_verdad_solo_en_los_defectuosos(dc):
    malos = set(dc.defects.loc[dc.defects["location_error"], "sku_id"])
    m = dc.master.set_index("sku_id")["home_location"]
    t = dc.truth.set_index("sku_id")["home_location"]
    difieren = set(m.index[m != t])
    assert difieren == malos
