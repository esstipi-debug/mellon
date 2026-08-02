"""Detecciones crudas -> pistas en metros.

Toda esta capa se testea con detecciones sinteticas: sin camara, sin cv2 y sin
video. Ese es el motivo del corte de la regla 2, y el motivo por el que la
etapa 1 se puede terminar antes de comprar nada.
"""

import pandas as pd
import pytest

from fdekit.field.coverage import MeasurementCoverage
from fdekit.field.homography import FloorHomography
from fdekit.field.privacy import new_session_salt
from fdekit.field.tracks import (
    Detection,
    TrackPoint,
    build_tracks,
    dwell_events,
    load_detections,
    nearest_location,
    track_distance_m,
    tracks_to_eventlog,
)
from fdekit.layout import Layout
from fdekit.timestudy import travel_report

# 100 px = 10 m, escala 0.1.
H = FloorHomography.from_points(
    [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
)

LAY = Layout(aisles=4, bays=10, levels=2, aisle_pitch=3.0, bay_pitch=1.0)
T0 = pd.Timestamp("2026-09-14 10:00:00")


def _linea(marker: str, n: int, paso_px: float = 10.0) -> list[Detection]:
    """Un marcador que avanza en linea recta, un paso por frame."""
    return [Detection(marker, f, f * paso_px, 0.0) for f in range(n)]


def test_reconstruye_la_distancia_de_una_recta_conocida():
    # 10 frames avanzando 10 px = 90 px recorridos = 9 m.
    tracks, _ = build_tracks(_linea("M1", 10), H, fps=10.0, salt=new_session_salt(), frames_total=10)
    (puntos,) = tracks.values()
    assert track_distance_m(puntos) == pytest.approx(9.0, abs=0.02)


def test_la_distancia_no_depende_de_la_tasa_de_cuadros():
    """Invariante prioritario del spec, seccion 8.

    Si duplicar los fps cambiara la distancia, el numero dependeria de la
    camara y no del CD — que es la version de camara del bug de anualizacion.
    """
    lenta = _linea("M1", 10, paso_px=10.0)
    rapida = [Detection("M1", f, f * 5.0, 0.0) for f in range(19)]

    d_lenta = track_distance_m(
        list(build_tracks(lenta, H, 10.0, new_session_salt(), frames_total=10)[0].values())[0]
    )
    d_rapida = track_distance_m(
        list(build_tracks(rapida, H, 20.0, new_session_salt(), frames_total=19)[0].values())[0]
    )
    assert d_lenta == pytest.approx(d_rapida, abs=0.02)


def test_el_tiempo_sale_de_los_frames_y_del_fps():
    tracks, _ = build_tracks(_linea("M1", 5), H, fps=10.0, salt=new_session_salt(), frames_total=5)
    (puntos,) = tracks.values()
    assert puntos[0].t_s == pytest.approx(0.0)
    assert puntos[-1].t_s == pytest.approx(0.4)  # frame 4 a 10 fps


def test_separa_marcadores_distintos_en_pistas_distintas():
    dets = _linea("M1", 5) + _linea("M2", 5)
    tracks, cov = build_tracks(dets, H, 10.0, new_session_salt(), frames_total=5)
    assert len(tracks) == 2
    assert cov.tracks_seen == 2


def test_las_claves_son_seudonimos_y_no_el_marcador_crudo():
    # Regla 9: el marker_id no sale de esta funcion.
    tracks, _ = build_tracks(_linea("MARKER-07", 5), H, 10.0, new_session_salt(), frames_total=5)
    (clave,) = tracks.keys()
    assert clave.startswith("sub-")
    assert "MARKER-07" not in clave


def test_una_pista_demasiado_corta_se_descarta_y_baja_la_cobertura():
    # Dos detecciones sueltas no son un viaje: son ruido. Descartarlas en
    # silencio seria mentir; van al contador de descartes.
    dets = _linea("M1", 10) + _linea("M2", 2)
    tracks, cov = build_tracks(dets, H, 10.0, new_session_salt(), frames_total=10, min_points=3)
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
    dets, frames_total = load_detections(csv)
    assert dets == [Detection("M1", 0, 10.5, 20.5), Detection("M1", 1, 11.5, 20.5)]
    assert frames_total is None


def test_load_detections_sin_metadata_da_frames_total_none():
    # Regla 3: un CSV sin la linea de metadatos no permite afirmar cobertura.
    # frames_total tiene que ser None, no una suposicion (como derivarlo de
    # las detecciones, que siempre daria 100%).
    import io

    from fdekit.field.tracks import parse_detections

    dets, frames_total = parse_detections(
        io.StringIO("marker_id,frame,x_px,y_px\nM1,0,10.5,20.5\n")
    )
    assert dets == [Detection("M1", 0, 10.5, 20.5)]
    assert frames_total is None


def test_load_detections_lee_la_linea_de_metadatos_de_frames_total(tmp_path):
    # Contrato entre vision.write_detections y tracks.load_detections: la
    # primera linea del CSV, comentada, con el total de frames del video.
    csv = tmp_path / "detecciones.csv"
    csv.write_text(
        "# frames_total=137\nmarker_id,frame,x_px,y_px\nM1,0,10.5,20.5\n",
        encoding="utf-8",
    )
    dets, frames_total = load_detections(csv)
    assert dets == [Detection("M1", 0, 10.5, 20.5)]
    assert frames_total == 137


def test_load_detections_rechaza_un_csv_sin_las_columnas():
    import io

    from fdekit.field.tracks import parse_detections

    with pytest.raises(ValueError, match="falta"):
        parse_detections(io.StringIO("marcador,cuadro\nM1,0\n"))


def test_load_detections_lee_un_csv_con_bom():
    # Ronda de arreglo 1, hallazgo 1: "CSV UTF-8" desde Excel en Windows lleva
    # BOM. Sin utf-8-sig, DictReader deja '﻿marker_id' en fieldnames y
    # el error dice "falta la columna" cuando en realidad esta ahi.
    contenido = "marker_id,frame,x_px,y_px\nM1,0,10.5,20.5\n"

    def _escribir_con_bom(ruta):
        ruta.write_bytes(contenido.encode("utf-8-sig"))

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "con_bom.csv"
        _escribir_con_bom(ruta)
        dets, _ = load_detections(ruta)
        assert dets == [Detection("M1", 0, 10.5, 20.5)]


def test_parse_detections_fila_mas_corta_que_la_cabecera_da_valueerror():
    # Ronda de arreglo 1, hallazgo 3: una fila corta hace que DictReader
    # rellene con None, y float(None) revienta con TypeError -- inconsistente
    # con el resto del modulo, que siempre informa con ValueError.
    import io

    from fdekit.field.tracks import parse_detections

    with pytest.raises(ValueError, match="falta"):
        parse_detections(io.StringIO("marker_id,frame,x_px,y_px\nM1,0,10.5\n"))


def test_build_tracks_sin_frames_total_es_un_error_de_argumento():
    # Ronda de arreglo 1, hallazgo 2: frames_total opcional reproducia la
    # mentira que el campo existe para evitar (100% de cobertura siempre que
    # se omitiera). Ahora es obligatorio: omitirlo es un TypeError de Python,
    # no una cobertura falsa y silenciosa.
    with pytest.raises(TypeError):
        build_tracks(_linea("M1", 5), H, 10.0, new_session_salt())


def test_parse_detections_fila_mas_larga_que_la_cabecera_da_valueerror():
    # Ronda de arreglo 2, hallazgo 1: una fila mas larga que la cabecera
    # sugiere que un campo tenia una coma sin comillas, y corrio todas las
    # columnas siguientes. Aceptar esa fila en silencio significa que los
    # cuatro primeros valores pueden no ser marker_id/frame/x_px/y_px sino
    # pedazos de un campo roto -- coordenadas plausibles y equivocadas.
    import io

    from fdekit.field.tracks import parse_detections

    with pytest.raises(ValueError, match="coma"):
        parse_detections(io.StringIO("marker_id,frame,x_px,y_px\nM1,0,1.0,2.0,999,888\n"))


def test_parse_detections_devuelve_las_detecciones_y_el_frames_total():
    # Forma general del contrato: parse_detections siempre devuelve la tupla,
    # con o sin la linea de metadatos.
    import io

    from fdekit.field.tracks import parse_detections

    resultado = parse_detections(io.StringIO("marker_id,frame,x_px,y_px\nM1,0,1.0,2.0\n"))
    assert resultado == ([Detection("M1", 0, 1.0, 2.0)], None)


def test_parse_detections_bom_menciona_el_bom_y_no_una_columna():
    # Ronda de arreglo 2, hallazgo 2: el defecto real no era donde estaba el
    # open(), sino que "columna no en fieldnames" no distingue "no esta" de
    # "esta pero con un caracter invisible pegado adelante". El mensaje tiene
    # que nombrar el BOM explicitamente para no mandar a buscar en el lugar
    # equivocado.
    import io

    from fdekit.field.tracks import parse_detections

    con_bom = io.StringIO("﻿marker_id,frame,x_px,y_px\nM1,0,1.0,2.0\n")
    with pytest.raises(ValueError, match="BOM"):
        parse_detections(con_bom)


def test_parse_detections_frame_negativo_da_valueerror():
    # Ronda de arreglo 2, hallazgo 3: un frame negativo no puede existir en un
    # video real, es senal de datos corruptos aguas arriba.
    import io

    from fdekit.field.tracks import parse_detections

    with pytest.raises(ValueError, match="negativo"):
        parse_detections(io.StringIO("marker_id,frame,x_px,y_px\nM1,-1,1.0,2.0\n"))


def test_parse_detections_acepta_notacion_cientifica_en_coordenadas():
    # Caso legitimo: notacion cientifica es un float valido para Python y no
    # tiene que activar ninguno de los rechazos nuevos.
    import io

    from fdekit.field.tracks import parse_detections

    dets, _ = parse_detections(io.StringIO("marker_id,frame,x_px,y_px\nM1,0,1e2,2.5e-1\n"))
    assert dets == [Detection("M1", 0, 100.0, 0.25)]


def test_parse_detections_acepta_un_csv_normal_sin_bom():
    # Caso legitimo: un CSV comun, sin BOM, sigue andando igual que siempre.
    import io

    from fdekit.field.tracks import parse_detections

    dets, _ = parse_detections(io.StringIO("marker_id,frame,x_px,y_px\nM1,0,10.5,20.5\nM1,1,11.5,20.5\n"))
    assert dets == [Detection("M1", 0, 10.5, 20.5), Detection("M1", 1, 11.5, 20.5)]


def test_nearest_location_cae_en_la_ubicacion_del_layout():
    # Layout.xy("01-002-1") = (1*3.0, 2*1.0) = (3.0, 2.0)
    assert nearest_location(LAY, 3.05, 2.05) == "01-002-1"
    assert nearest_location(LAY, 6.0, 3.0) == "02-003-1"


def test_dwell_events_ignora_el_paso_y_marca_la_parada():
    # Pasa cerca de 01-002-1 medio segundo y se queda 6 s en 02-003-1.
    puntos = [TrackPoint(0.0, 3.0, 2.0), TrackPoint(0.5, 4.5, 2.5)]
    puntos += [TrackPoint(1.0 + i, 6.0, 3.0) for i in range(7)]

    paradas = dwell_events(puntos, LAY, min_dwell_s=4.0).stops
    assert [loc for _, loc in paradas] == ["02-003-1"]


def test_tracks_to_eventlog_produce_algo_que_travel_report_ya_sabe_leer():
    """El enchufe: si el EventLog es valido, el kit entero funciona sin cambios."""
    puntos = [TrackPoint(0.0 + i, 3.0, 2.0) for i in range(6)]
    puntos += [TrackPoint(10.0 + i, 6.0, 3.0) for i in range(6)]

    log, _ = tracks_to_eventlog({"sub-abc123456789": puntos}, LAY, t0=T0)
    t = travel_report(log, LAY)

    assert len(t) == 1
    assert t.loc[0, "n_stops"] == 2
    assert t.loc[0, "distance_m"] > 0


def test_tracks_to_eventlog_no_lee_el_reloj():
    """Regla 4: t0 es argumento. Dos llamadas con el mismo t0 dan lo mismo."""
    puntos = [TrackPoint(0.0 + i, 3.0, 2.0) for i in range(6)]
    a, _ = tracks_to_eventlog({"sub-abc123456789": puntos}, LAY, t0=T0)
    b, _ = tracks_to_eventlog({"sub-abc123456789": puntos}, LAY, t0=T0)
    assert a.df["timestamp"].tolist() == b.df["timestamp"].tolist()


def test_el_eventlog_no_lleva_identidad():
    from fdekit.field.privacy import assert_no_identity

    puntos = [TrackPoint(0.0 + i, 3.0, 2.0) for i in range(6)]
    log, _ = tracks_to_eventlog({"sub-abc123456789": puntos}, LAY, t0=T0)
    assert_no_identity(log.df.to_dict("records"))


# --- Ronda de arreglo 1: el algoritmo del ancla fallaba en las dos
# direcciones ante oscilaciones (ruido de deteccion normal, no excepcional).
# M y E son dos ubicaciones bien separadas del layout: M es donde el carro se
# queda, E es la segunda ubicacion (a veces ruido, a veces una visita real).
M_XY = LAY.xy("01-002-1")
E_XY = LAY.xy("03-005-1")


def _tramo(t0: float, xy: tuple[float, float], n: int, paso: float = 1.0) -> list[TrackPoint]:
    """`n` puntos separados por `paso` segundos, arrancando en `t0`."""
    return [TrackPoint(t0 + i * paso, *xy) for i in range(n)]


def test_dwell_events_junta_excursiones_cortas_de_ruido_en_una_sola_parada():
    # 7 visitas de 2 s a M, cada una separada por una excursion de 1 s a E.
    # Los tramos de excursion miden 1 s < max_gap_s (2.0) y son ruido: se
    # toleran, y los 7 tramos de M se fusionan en una sola parada.
    puntos: list[TrackPoint] = []
    t = 0.0
    for _ in range(7):
        puntos += _tramo(t, M_XY, 3)  # 3 puntos, 1 s de paso -> tramo de 2 s
        t += 3.0
        puntos += _tramo(t, E_XY, 2)  # 2 puntos -> tramo de 1 s (ruido)
        t += 2.0

    resultado = dwell_events(puntos, LAY)
    assert [loc for _, loc in resultado.stops] == ["01-002-1"]


def test_dwell_events_no_pierde_una_segunda_ubicacion_real_alternada():
    # La regresion de la ronda 1: dos ubicaciones reales alternando cada 1 s
    # durante 20 s. El tramo de CADA visita mide ~1 s < max_gap_s, asi que es
    # ruido PARA LA OTRA ubicacion -- pero eso no le impide fusionarse con sus
    # propios tramos anteriores. La ronda 1 tiraba el tramo tolerado entero,
    # sin sumarlo a nada: la segunda ubicacion desaparecia sin dejar rastro.
    # El resultado correcto son DOS paradas, una por ubicacion.
    puntos: list[TrackPoint] = []
    t = 0.0
    for _ in range(10):
        puntos += _tramo(t, M_XY, 2)  # tramo de 1 s
        t += 1.0
        puntos += _tramo(t, E_XY, 2)  # tramo de 1 s
        t += 1.0

    resultado = dwell_events(puntos, LAY)
    ubicaciones = sorted(loc for _, loc in resultado.stops)
    assert ubicaciones == ["01-002-1", "03-005-1"]


def test_dwell_events_corta_el_grupo_ante_una_excursion_larga():
    # Permanencia real en M (0-5 s, tramo de 5 s), despues una excursion a E
    # que en si misma dura 4 s (>= max_gap_s: no es ruido), y de nuevo M
    # (8 s). La excursion corta la fusion -- son dos visitas a M distintas --
    # y ademas, si la excursion en si alcanza min_dwell_s, genera su propia
    # parada: dos paradas en M mas una en E.
    puntos = _tramo(0.0, M_XY, 6)  # 0..5, tramo de 5 s
    puntos += _tramo(6.0, E_XY, 5)  # 6..10, tramo de 4 s (no es ruido)
    puntos += _tramo(11.0, M_XY, 9)  # 11..19, tramo de 8 s

    resultado = dwell_events(puntos, LAY)
    conteo = sorted(loc for _, loc in resultado.stops)
    assert conteo == ["01-002-1", "01-002-1", "03-005-1"]


# --- Ronda de arreglo 3: la ronda 2 definia la duracion de un grupo fusionado
# como la SUMA de la duracion propia de cada uno de sus tramos. Con tramos de
# UNA sola muestra (duracion propia cero) eso da una suma de cero, y la
# permanencia real desaparecia -- justo el caso realista: cuando el carro
# alterna entre dos ubicaciones a una frecuencia parecida a la de la camara,
# cada tramo tiene exactamente una muestra. Los tests de arriba con tramos de
# varias muestras (2-3 puntos por visita) siguen pasando sin cambios: ahi el
# span y la suma coinciden porque cada grupo tiene un solo tramo propio
# contribuyendo. Los tres tests de abajo repiten los mismos tres casos con
# tramos de una sola muestra -- el caso que la ronda 2 no cubria -- mas un
# cuarto caso nuevo, el hueco de deteccion.
#
# (El test de la ronda 1 "una sola interrupcion corta no duplica la parada"
# se borro en la ronda 2 y no se repuso: bajo el criterio de tramo-ruido, una
# interrupcion corta es exactamente un tramo con duracion propia menor que
# max_gap_s, y ese comportamiento ya lo cubre
# test_dwell_events_junta_excursiones_cortas_de_ruido_en_una_sola_parada de
# arriba. Un test aparte para el mismo criterio no agregaria cobertura.)


def _otras_ubicaciones_de_paso(n: int) -> list[tuple[float, float]]:
    """`n` ubicaciones del layout, todas distintas entre si y de M_XY/E_XY.

    Sirven para simular ruido de deteccion que "salta" a un lugar distinto
    cada vez -- no siempre al mismo -- que es lo que hace una excursion
    de una sola muestra sin que ninguna de esas ubicaciones de paso acumule
    su propia permanencia.
    """
    return [LAY.xy(f"04-{b:03d}-1") for b in range(1, n + 1)]


def test_dwell_events_junta_excursiones_de_una_sola_muestra_en_una_parada():
    # Caso 1 (ronda 3): 20 s en M, con una excursion de una sola muestra cada
    # 2 s (a una ubicacion de paso distinta cada vez, para que ninguna de esas
    # excursiones acumule permanencia propia). El span de M -- de su primera a
    # su ultima muestra -- llega a los ~18 s, y con eso alcanza min_dwell_s.
    de_paso = _otras_ubicaciones_de_paso(10)
    puntos: list[TrackPoint] = []
    t = 0.0
    for i in range(20):
        puntos.append(TrackPoint(t, *M_XY))
        t += 1.0
        if i % 2 == 1:
            puntos.append(TrackPoint(t, *de_paso[i // 2]))
            t += 1.0

    resultado = dwell_events(puntos, LAY)
    assert [loc for _, loc in resultado.stops] == ["01-002-1"]


def test_dwell_events_no_pierde_una_segunda_ubicacion_con_tramos_de_una_sola_muestra():
    # Caso 2 (ronda 3), el que la ronda 2 todavia perdia: dos ubicaciones
    # reales alternando cada 1 s durante 20 s, con tramos de una sola muestra
    # (duracion propia cero). Con suma, cada tramo de M o de E aporta cero, y
    # ninguna de las dos alcanza min_dwell_s -- la ronda 2 fallaba aca. Con
    # span, M abarca de su primera a su ultima muestra (~18 s) y E lo mismo
    # (~18 s): dos paradas.
    puntos: list[TrackPoint] = []
    t = 0.0
    for i in range(20):
        puntos.append(TrackPoint(t, *(M_XY if i % 2 == 0 else E_XY)))
        t += 1.0

    resultado = dwell_events(puntos, LAY)
    ubicaciones = sorted(loc for _, loc in resultado.stops)
    assert ubicaciones == ["01-002-1", "03-005-1"]


def test_dwell_events_corta_el_grupo_por_hueco_de_deteccion_en_la_misma_ubicacion():
    # Caso 4 (ronda 3), nuevo: el marcador se queda 5 s en M, desaparece 100 s
    # (ningun punto registrado -- un hueco de deteccion, no una excursion a
    # otra ubicacion) y reaparece en la MISMA M durante 6 s mas. Sin el corte
    # por hueco, el span iria de la primera a la ultima muestra e inventaria
    # 111 s de permanencia que nadie observo. Con el corte, son dos tramos de
    # M separados, y cada uno se mide por su cuenta: dos paradas.
    puntos = _tramo(0.0, M_XY, 6)  # 0..5, 5 s
    puntos += _tramo(105.0, M_XY, 7)  # 105..111, 6 s, despues de un hueco de 100 s

    resultado = dwell_events(puntos, LAY)
    assert [loc for _, loc in resultado.stops] == ["01-002-1", "01-002-1"]
    # El hueco no se cuenta como permanencia: la segunda parada arranca
    # donde reaparece el marcador, no donde desaparecio.
    assert resultado.stops[1][0] == 105.0


# --- Ronda de arreglo 4: la ronda 3 media "¿el marcador dejo de verse?" y
# "¿el carro se fue a otro lado?" con la MISMA comprobacion (el hueco entre
# dos puntos del propio grupo). Eso vaciaba la tolerancia al ruido que la
# ronda 2 vino a construir: una ubicacion visitada cada > max_gap_s segundos,
# con OTRA deteccion real en el medio (el marcador nunca dejo de verse), se
# leia como si el marcador hubiera desaparecido. dwell_events ahora separa las
# dos preguntas: el hueco se mide sobre el TRACK completo (_tramos_consecutivos),
# y la duracion propia del tramo decide si es un desplazamiento real.


def test_dwell_events_no_confunde_ruido_interleaveado_con_ausencia_del_marcador():
    # Caso 1 (ronda 4), el que la ronda 3 rompia: A visitada cada 3 s (mas que
    # max_gap_s=2.0 entre visitas propias), con una deteccion de B en el medio
    # cada vez, a 2 s y a 1 s de cada A. El TRACK nunca pierde al marcador (el
    # hueco maximo entre dos puntos cualquiera es 2 s, nunca supera
    # max_gap_s), asi que A se fusiona en una sola parada -- no la ronda 3,
    # que cortaba el grupo de A por el hueco de 3 s entre sus propios puntos,
    # ignorando que B llenaba el medio.
    #
    # Nota de longitud: esta es la instancia MINIMA (3 visitas a A, 2 a B) en
    # la que A cruza min_dwell_s=4.0 (span 6 s) y B se queda corto (span 3 s).
    # El span de B tambien crece con cada repeticion adicional del mismo
    # patron, igual que el de A: en una pista mucho mas larga, B terminaria
    # cruzando min_dwell_s tambien, y a partir de ahi ya no se distingue de
    # una segunda ubicacion real (test de arriba). Este algoritmo no resuelve
    # esa ambiguedad con datos puramente temporales; ver el docstring de
    # dwell_events.
    puntos = [
        TrackPoint(0.0, *M_XY),
        TrackPoint(2.0, *E_XY),
        TrackPoint(3.0, *M_XY),
        TrackPoint(5.0, *E_XY),
        TrackPoint(6.0, *M_XY),
    ]

    resultado = dwell_events(puntos, LAY)
    assert [loc for _, loc in resultado.stops] == ["01-002-1"]


def test_dwell_events_no_corta_cuando_el_hueco_es_exactamente_max_gap_s():
    # Borde: el hueco es IGUAL a max_gap_s, ni mas ni menos. La comparacion en
    # _tramos_consecutivos es estricta (> corta, <= tolera), asi que este caso
    # NO corta el grupo. Fijado con un test para que nadie lo cambie sin
    # darse cuenta.
    puntos = [TrackPoint(float(t), *M_XY) for t in (0.0, 2.0, 4.0, 6.0)]  # pasos de 2 s = max_gap_s

    resultado = dwell_events(puntos, LAY)
    assert [loc for _, loc in resultado.stops] == ["01-002-1"]


def test_dwell_events_marca_el_timestamp_de_entrada_no_el_de_salida():
    # El timestamp de la parada tiene que ser el del primer punto del grupo
    # (la entrada), no el del ultimo punto que ya se habia ido (la salida) --
    # eso sobreestimaria la duracion en un intervalo de muestreo.
    puntos = [TrackPoint(float(t), *M_XY) for t in range(0, 6)]
    resultado = dwell_events(puntos, LAY)
    (t_parada, _), = resultado.stops
    assert t_parada == puntos[0].t_s


def test_nearest_location_con_max_distance_devuelve_none_fuera_de_planta():
    # Un punto lejos de toda ubicacion del layout -- tipico de una homografia
    # mal calibrada -- no se mapea en silencio al borde mas cercano: se
    # rechaza explicitamente si supera max_distance_m.
    assert nearest_location(LAY, 500.0, 500.0, max_distance_m=5.0) is None
    assert nearest_location(LAY, 500.0, 500.0) is not None


def test_dwell_events_cuenta_los_puntos_descartados_por_estar_fuera_de_planta():
    puntos = [TrackPoint(float(t), *M_XY) for t in range(0, 6)]
    puntos.append(TrackPoint(6.0, 500.0, 500.0))

    resultado = dwell_events(puntos, LAY, max_distance_m=5.0)
    assert resultado.discarded_out_of_bounds == 1


# --- Ronda de arreglo 2, hallazgo 2: la cuenta de "cuanto no se pudo medir"
# vive toda en `MeasurementCoverage`, no repartida entre ese objeto y un
# contador aparte que se pierde en el unico llamador real.


def test_tracks_to_eventlog_propaga_los_descartados_a_la_cobertura():
    puntos = [TrackPoint(float(t), *M_XY) for t in range(0, 6)]
    puntos.append(TrackPoint(6.0, 500.0, 500.0))  # fuera de planta

    cobertura_previa = MeasurementCoverage(
        frames_total=100, frames_with_marker=90, tracks_seen=1
    )
    _, cobertura = tracks_to_eventlog(
        {"sub-abc123456789": puntos},
        LAY,
        t0=T0,
        coverage=cobertura_previa,
        max_distance_m=5.0,
    )
    assert cobertura.discarded_out_of_bounds == 1
    # El resto de la cobertura recibida no se pierde: se actualiza, no se
    # reemplaza por una nueva.
    assert cobertura.frames_total == 100
    assert cobertura.tracks_seen == 1


def test_tracks_to_eventlog_sin_cobertura_previa_igual_reporta_los_descartados():
    # Sin `coverage` (por ejemplo, un test que arma pistas a mano sin pasar
    # por build_tracks) igual hay que poder ver cuantos puntos se descartaron.
    puntos = [TrackPoint(float(t), *M_XY) for t in range(0, 6)]
    puntos.append(TrackPoint(6.0, 500.0, 500.0))

    _, cobertura = tracks_to_eventlog(
        {"sub-abc123456789": puntos}, LAY, t0=T0, max_distance_m=5.0
    )
    assert cobertura.discarded_out_of_bounds == 1


def test_la_nota_de_cobertura_menciona_los_puntos_fuera_de_planta():
    c = MeasurementCoverage(
        frames_total=100,
        frames_with_marker=90,
        tracks_seen=1,
        discarded_out_of_bounds=3,
    )
    n = c.note()
    assert "3 puntos descartados por caer fuera de planta" in n
    assert "homografia" in n.lower()
