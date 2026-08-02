"""La cobertura de una medicion de terreno.

Es el analogo de `Coverage` en `decide/query.py`: la promesa del repo no es
resolver siempre, es no mentir nunca en silencio. Una camara que no vio la
mitad de los viajes tiene que decirlo al lado del numero, no despues.
"""

from fdekit.field import MeasurementCoverage


def test_reporta_el_porcentaje_de_frames_con_marcador():
    c = MeasurementCoverage(frames_total=1000, frames_with_marker=750, tracks_seen=8)
    assert c.frame_pct == 75.0


def test_nunca_se_declara_completa():
    # Igual que Coverage: is_complete es False SIEMPRE, y por eso se muestra.
    c = MeasurementCoverage(frames_total=100, frames_with_marker=100, tracks_seen=1)
    assert c.is_complete is False


def test_track_pct_es_none_cuando_no_se_sabe_cuantos_viajes_hubo():
    # Sobre la mesa no hay WMS que diga cuantos pedidos habia. Inventar un
    # denominador seria peor que no tenerlo.
    c = MeasurementCoverage(frames_total=100, frames_with_marker=90, tracks_seen=3)
    assert c.track_pct is None

    c2 = MeasurementCoverage(
        frames_total=100, frames_with_marker=90, tracks_seen=3, tracks_expected=4
    )
    assert c2.track_pct == 75.0


def test_no_divide_por_cero_con_cero_frames():
    c = MeasurementCoverage(frames_total=0, frames_with_marker=0, tracks_seen=0)
    assert c.frame_pct == 0.0


def test_la_nota_menciona_lo_descartado():
    c = MeasurementCoverage(
        frames_total=1000,
        frames_with_marker=600,
        tracks_seen=5,
        discarded_low_confidence=12,
    )
    n = c.note()
    assert "60" in n
    assert "12" in n
    assert "no tratar" in n.lower()
