"""Detecciones crudas -> pistas en metros.

Toda esta capa se testea con detecciones sinteticas: sin camara, sin cv2 y sin
video. Ese es el motivo del corte de la regla 2, y el motivo por el que la
etapa 1 se puede terminar antes de comprar nada.
"""

import pytest

from fdekit.field.homography import FloorHomography
from fdekit.field.privacy import new_session_salt
from fdekit.field.tracks import Detection, build_tracks, load_detections, track_distance_m

# 100 px = 10 m, escala 0.1.
H = FloorHomography.from_points(
    [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
)


def _linea(marker: str, n: int, paso_px: float = 10.0) -> list[Detection]:
    """Un marcador que avanza en linea recta, un paso por frame."""
    return [Detection(marker, f, f * paso_px, 0.0) for f in range(n)]


def test_reconstruye_la_distancia_de_una_recta_conocida():
    # 10 frames avanzando 10 px = 90 px recorridos = 9 m.
    tracks, _ = build_tracks(_linea("M1", 10), H, fps=10.0, salt=new_session_salt())
    (puntos,) = tracks.values()
    assert track_distance_m(puntos) == pytest.approx(9.0, abs=0.02)


def test_la_distancia_no_depende_de_la_tasa_de_cuadros():
    """Invariante prioritario del spec, seccion 8.

    Si duplicar los fps cambiara la distancia, el numero dependeria de la
    camara y no del CD — que es la version de camara del bug de anualizacion.
    """
    lenta = _linea("M1", 10, paso_px=10.0)
    rapida = [Detection("M1", f, f * 5.0, 0.0) for f in range(19)]

    d_lenta = track_distance_m(list(build_tracks(lenta, H, 10.0, new_session_salt())[0].values())[0])
    d_rapida = track_distance_m(
        list(build_tracks(rapida, H, 20.0, new_session_salt())[0].values())[0]
    )
    assert d_lenta == pytest.approx(d_rapida, abs=0.02)


def test_el_tiempo_sale_de_los_frames_y_del_fps():
    tracks, _ = build_tracks(_linea("M1", 5), H, fps=10.0, salt=new_session_salt())
    (puntos,) = tracks.values()
    assert puntos[0].t_s == pytest.approx(0.0)
    assert puntos[-1].t_s == pytest.approx(0.4)  # frame 4 a 10 fps


def test_separa_marcadores_distintos_en_pistas_distintas():
    dets = _linea("M1", 5) + _linea("M2", 5)
    tracks, cov = build_tracks(dets, H, 10.0, new_session_salt())
    assert len(tracks) == 2
    assert cov.tracks_seen == 2


def test_las_claves_son_seudonimos_y_no_el_marcador_crudo():
    # Regla 9: el marker_id no sale de esta funcion.
    tracks, _ = build_tracks(_linea("MARKER-07", 5), H, 10.0, new_session_salt())
    (clave,) = tracks.keys()
    assert clave.startswith("sub-")
    assert "MARKER-07" not in clave


def test_una_pista_demasiado_corta_se_descarta_y_baja_la_cobertura():
    # Dos detecciones sueltas no son un viaje: son ruido. Descartarlas en
    # silencio seria mentir; van al contador de descartes.
    dets = _linea("M1", 10) + _linea("M2", 2)
    tracks, cov = build_tracks(dets, H, 10.0, new_session_salt(), min_points=3)
    assert len(tracks) == 1
    assert cov.discarded_low_confidence == 1


def test_la_oclusion_baja_la_cobertura_pero_no_la_distancia_en_silencio():
    """El invariante que mas importa de todos.

    Si el marcador se pierde 5 frames en el medio, la distancia medida baja
    —porque el tramo tapado no se vio— pero la cobertura TIENE que reflejarlo.
    Una distancia menor con cobertura del 100% seria el bug de la clase
    'no falla, miente' en su version de camara.
    """
    completa = _linea("M1", 20)
    con_hueco = [d for d in completa if not (8 <= d.frame < 13)]

    _, cov_ok = build_tracks(completa, H, 10.0, new_session_salt(), frames_total=20)
    _, cov_hueco = build_tracks(con_hueco, H, 10.0, new_session_salt(), frames_total=20)

    assert cov_ok.frame_pct == 100.0
    assert cov_hueco.frame_pct == 75.0


def test_load_detections_lee_el_csv_del_detector(tmp_path):
    csv = tmp_path / "detecciones.csv"
    csv.write_text(
        "marker_id,frame,x_px,y_px\nM1,0,10.5,20.5\nM1,1,11.5,20.5\n", encoding="utf-8"
    )
    dets = load_detections(csv)
    assert dets == [Detection("M1", 0, 10.5, 20.5), Detection("M1", 1, 11.5, 20.5)]


def test_load_detections_rechaza_un_csv_sin_las_columnas():
    import io

    from fdekit.field.tracks import parse_detections

    with pytest.raises(ValueError, match="falta"):
        parse_detections(io.StringIO("marcador,cuadro\nM1,0\n"))
