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
    assert "600/1000 frames con marcador (60.0%)" in n
    assert "12 tramos descartados por baja confianza" in n
    assert "no tratar" in n.lower()


def test_track_pct_es_none_cuando_tracks_expected_es_none():
    # Caso explicito: cuando no se sabe cuantos viajes hubo.
    c = MeasurementCoverage(frames_total=100, frames_with_marker=90, tracks_seen=3)
    assert c.track_pct is None


def test_track_pct_menciona_cuando_zero_viajes_esperados_y_zero_vistos():
    # tracks_expected=0 y tracks_seen=0 es un caso particular: se esperaban
    # cero viajes y se reconstruyeron cero. Es coherente pero inusual.
    # track_pct devuelve None (0/0 indefinido), pero la nota lo menciona.
    c = MeasurementCoverage(
        frames_total=100, frames_with_marker=90, tracks_seen=0, tracks_expected=0
    )
    assert c.track_pct is None
    n = c.note()
    assert "0 viajes reconstruidos" in n
    assert "0.0% de los viajes esperados" in n


def test_error_cuando_se_ven_viajes_pero_none_se_esperaban():
    # Incoherencia: se reconstruyeron viajes que nadie esperaba. Falla en construccion.
    import pytest
    with pytest.raises(ValueError, match="reconstruyeron.*incoherencia"):
        MeasurementCoverage(
            frames_total=100,
            frames_with_marker=90,
            tracks_seen=5,
            tracks_expected=0,
        )


def test_error_con_frames_total_negativo():
    # frames_total negativo no tiene sentido.
    import pytest
    with pytest.raises(ValueError, match="negativo|invalido"):
        MeasurementCoverage(
            frames_total=-10,
            frames_with_marker=5,
            tracks_seen=1,
        )


def test_error_con_frames_with_marker_negativo():
    # frames_with_marker negativo no tiene sentido.
    import pytest
    with pytest.raises(ValueError, match="negativo|invalido"):
        MeasurementCoverage(
            frames_total=100,
            frames_with_marker=-5,
            tracks_seen=1,
        )


def test_error_con_tracks_seen_negativo():
    # tracks_seen negativo no tiene sentido.
    import pytest
    with pytest.raises(ValueError, match="negativo|invalido"):
        MeasurementCoverage(
            frames_total=100,
            frames_with_marker=50,
            tracks_seen=-1,
        )


def test_error_con_frames_with_marker_mayor_que_frames_total():
    # No se pueden tener mas frames marcados que frames totales.
    import pytest
    with pytest.raises(ValueError, match="mayor que"):
        MeasurementCoverage(
            frames_total=100,
            frames_with_marker=150,
            tracks_seen=1,
        )


def test_error_con_tracks_expected_negativo():
    # tracks_expected negativo no tiene sentido.
    import pytest
    with pytest.raises(ValueError, match="negativo|invalido"):
        MeasurementCoverage(
            frames_total=100,
            frames_with_marker=50,
            tracks_seen=1,
            tracks_expected=-5,
        )


def test_error_con_discarded_negativo():
    # discarded_low_confidence negativo no tiene sentido.
    import pytest
    with pytest.raises(ValueError, match="negativo|invalido"):
        MeasurementCoverage(
            frames_total=100,
            frames_with_marker=50,
            tracks_seen=1,
            discarded_low_confidence=-3,
        )
