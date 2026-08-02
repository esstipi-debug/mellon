"""Capa pesada: la unica que toca cv2.

Marcado `vision` y excluido por defecto -- la suite tiene que correr en el
notebook prestado del CD, sin OpenCV. Correr con: pytest -m vision
"""

import pytest

from fdekit.field.tracks import Detection


def test_el_modulo_no_importa_cv2_al_cargarse():
    """Regla 2: importar `fdekit.field` no puede exigir OpenCV.

    Este test NO esta marcado `vision` a proposito: es justamente el que
    verifica que se puede vivir sin OpenCV, asi que tiene que correr siempre.
    """
    import sys

    sys.modules.pop("cv2", None)
    import fdekit.field.vision  # noqa: F401

    assert "cv2" not in sys.modules


def test_detect_markers_avisa_claro_si_falta_opencv():
    import fdekit.field.vision as v

    if v._tiene_cv2():
        pytest.skip("OpenCV instalado; el camino de error no aplica")
    with pytest.raises(ImportError, match="pip install"):
        v.detect_markers("cualquier.mp4")


def test_detect_markers_avisa_que_el_csv_ya_hecho_no_necesita_opencv():
    # El mensaje de ImportError tiene que decir que hacer, no solo que fallo:
    # el comando de instalacion, y que un CSV ya grabado no necesita cv2.
    import fdekit.field.vision as v

    if v._tiene_cv2():
        pytest.skip("OpenCV instalado; el camino de error no aplica")
    with pytest.raises(ImportError, match="load_detections"):
        v.detect_markers("cualquier.mp4")


@pytest.mark.vision
def test_detecta_un_marcador_en_un_video_de_muestra(tmp_path):
    import fdekit.field.vision as v

    dets, frames = v.detect_markers("tests/data/marcador_muestra.mp4")
    assert frames > 0
    assert dets and isinstance(dets[0], Detection)


def test_write_detections_escribe_las_columnas_que_load_detections_espera(tmp_path):
    import fdekit.field.vision as v
    from fdekit.field.tracks import load_detections

    dets = [Detection("M1", 0, 10.5, 20.5), Detection("M1", 1, 11.5, 20.5)]
    destino = tmp_path / "d.csv"
    v.write_detections(dets, destino, frames_total=2)

    dets_leidos, frames_total = load_detections(destino)
    assert dets_leidos == dets


def test_write_detections_guarda_frames_total_en_la_primera_linea(tmp_path):
    # El defecto que este task tiene que resolver: detect_markers devuelve
    # (detecciones, frames_total), pero si write_detections no lo guarda, el
    # numero se pierde al pasar por el CSV y build_tracks -- que lo exige como
    # argumento obligatorio -- se queda sin de donde sacarlo.
    import fdekit.field.vision as v
    from fdekit.field.tracks import load_detections

    dets = [Detection("M1", 0, 10.5, 20.5)]
    destino = tmp_path / "d.csv"
    v.write_detections(dets, destino, frames_total=137)

    dets_leidos, frames_total = load_detections(destino)
    assert dets_leidos == dets
    assert frames_total == 137


def test_write_detections_metadata_es_la_primera_linea_comentada(tmp_path):
    import fdekit.field.vision as v

    destino = tmp_path / "d.csv"
    v.write_detections([Detection("M1", 0, 1.0, 2.0)], destino, frames_total=42)

    primera_linea = destino.read_text(encoding="utf-8").splitlines()[0]
    assert primera_linea == "# frames_total=42"
