"""Pixeles -> metros del sistema de coordenadas de `Layout`.

Es el punto de enchufe entre la camara y todo lo que el kit ya sabe hacer: si
la proyeccion cae en el mismo sistema que `Layout.xy`, `travel_report` y el
espagueti funcionan sin tocarse.
"""

import numpy as np
import pytest

from fdekit.field.homography import FloorHomography

# Cuadrado de 100x100 px que en el piso son 10x10 m.
PX = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
M = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_recupera_una_escala_pura():
    h = FloorHomography.from_points(PX, M)
    assert h.to_meters(50.0, 50.0) == pytest.approx((5.0, 5.0), abs=1e-6)


def test_clava_las_esquinas_que_se_le_dieron():
    h = FloorHomography.from_points(PX, M)
    for (xp, yp), (xm, ym) in zip(PX, M):
        assert h.to_meters(xp, yp) == pytest.approx((xm, ym), abs=1e-6)


def test_recupera_una_homografia_con_perspectiva_real():
    # Una camara en diagonal no da una escala pura: da perspectiva. Se genera
    # una homografia conocida, se proyectan 4 puntos, y se verifica que
    # from_points la reconstruye para un QUINTO punto que no vio.
    verdad = np.array([[0.10, 0.01, 0.0], [0.00, 0.09, 0.0], [0.0012, 0.0004, 1.0]])

    def proyectar(x, y):
        v = verdad @ np.array([x, y, 1.0])
        return (v[0] / v[2], v[1] / v[2])

    px = [(0.0, 0.0), (120.0, 5.0), (130.0, 95.0), (10.0, 110.0)]
    metros = [proyectar(x, y) for x, y in px]

    h = FloorHomography.from_points(px, metros)
    assert h.to_meters(60.0, 55.0) == pytest.approx(proyectar(60.0, 55.0), abs=1e-4)


def test_error_bajo_5_cm_en_el_centro_de_la_escena():
    # Criterio de la seccion 8 del spec.
    h = FloorHomography.from_points(PX, M)
    x, y = h.to_meters(50.0, 50.0)
    assert abs(x - 5.0) < 0.05 and abs(y - 5.0) < 0.05


def test_exige_exactamente_cuatro_correspondencias():
    with pytest.raises(ValueError, match="cuatro"):
        FloorHomography.from_points(PX[:3], M[:3])

    with pytest.raises(ValueError, match="misma cantidad"):
        FloorHomography.from_points(PX, M[:3])


def test_puntos_colineales_fallan_con_mensaje_util():
    # Cuatro puntos sobre una recta no definen un plano. Es el error que comete
    # todo el mundo la primera vez que pega las marcas en el piso.
    colineales = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    with pytest.raises(ValueError, match="colineales|degenerad"):
        FloorHomography.from_points(colineales, M)


def test_rechaza_puntos_casi_colineales_a_0_001_px():
    # Ataque del revisor: cuatro puntos a 0,001 px de una recta.
    # Sin chequeo geometrico, no levanta; con chequeo, si.
    casi_colineales = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.0, 0.001),
        (0.0, 0.001),
    ]
    m = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    with pytest.raises(ValueError, match="casi colineales|degenerados"):
        FloorHomography.from_points(casi_colineales, m)


def test_acepta_cuadrilatero_delgado_pero_valido():
    # Un rectangulo de 1000x50 px es delgado pero valido.
    # El umbral de 1e-4 * diametro^2 es ~1025, area minima es ~25k.
    # Debe pasar para que casos reales de camaras alejadas sigan funcionando.
    px_delgado = [(0.0, 0.0), (1000.0, 0.0), (1000.0, 50.0), (0.0, 50.0)]
    m_delgado = [(0.0, 0.0), (10.0, 0.0), (10.0, 0.5), (0.0, 0.5)]
    h = FloorHomography.from_points(px_delgado, m_delgado)
    # Debe proyectar el centro correctamente.
    x, y = h.to_meters(500.0, 25.0)
    assert x == pytest.approx(5.0, abs=1e-6)
    assert y == pytest.approx(0.25, abs=1e-6)


def test_acepta_camara_real_con_ejes_opuestos():
    # Caso del coordinador: camara real donde el eje y crece hacia abajo en imagen
    # pero hacia arriba en piso. El mismo recorrido visual da areas con signo opuesto.
    # Eso es normal y no es un error del usuario. Debe construir sin error.
    px = [(120.0, 880.0), (1800.0, 910.0), (1650.0, 300.0), (300.0, 290.0)]
    metros = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0)]
    h = FloorHomography.from_points(px, metros)
    # Debe proyectar correctamente las esquinas de calibración.
    for (xp, yp), (xm, ym) in zip(px, metros):
        actual = h.to_meters(xp, yp)
        assert actual[0] == pytest.approx(xm, abs=1e-4)
        assert actual[1] == pytest.approx(ym, abs=1e-4)


def test_lista_rotada_sin_verify_construye_pero_proyecta_mal():
    # Limite conocido: una lista rotada un lugar tiene el mismo sentido de giro,
    # pasa todos los chequeos, pero proyecta mal. Sin un quinto punto (verify)
    # es indetectable desde adentro. Esta en silencio es lo que el revisor
    # habia reportado: to_meters(0,0) devuelve (10,0) en vez de (0,0).
    px = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    m = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    # Rotar metros un lugar.
    m_rotado = m[1:] + m[:1]
    h = FloorHomography.from_points(px, m_rotado)
    # Sin verify, la homografia se construye exitosamente pero proyecta mal.
    # Esto es un limite conocido: la correspondencia no se puede verificar
    # con solo cuatro puntos.
    x, y = h.to_meters(0.0, 0.0)
    # Deberia ser (10, 0) pero sin verify no hay proteccion.
    assert not (x == pytest.approx(0.0, abs=1e-4) and y == pytest.approx(0.0, abs=1e-4))


def test_lista_rotada_con_verify_correcto_levanta():
    # El quinto punto detecta la rotacion. Usar un punto en una esquina donde
    # la rotacion causa error mayor a la tolerancia.
    px = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    m = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    # Rotar metros un lugar: [(10,0), (10,10), (0,10), (0,0)].
    m_rotado = m[1:] + m[:1]
    # En una esquina, la rotacion causa error grande. Por ej, px[0]=(0,0)
    # deberia proyectar a (0,0) pero la rotacion hace que vaya a (10,0).
    verify_point = ((0.0, 0.0), (0.0, 0.0))
    with pytest.raises(ValueError, match="verificacion fallo"):
        FloorHomography.from_points(px, m_rotado, verify=verify_point)


def test_verify_bien_puesto_en_calibracion_correcta_pasa():
    # Un quinto punto sobre una calibracion correcta debe pasar.
    px = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    m = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    # Quinto punto en el centro.
    verify_point = ((50.0, 50.0), (5.0, 5.0))
    h = FloorHomography.from_points(px, m, verify=verify_point)
    # Debe pasar y la homografia debe ser valida.
    assert h.to_meters(50.0, 50.0) == pytest.approx((5.0, 5.0), abs=1e-6)


def test_verify_fuera_de_tolerancia_levanta():
    # Un quinto punto cuyo error supera la tolerancia levanta.
    px = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    m = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    # Quinto punto con valor esperado **muy** erroneo (15 cm de error).
    verify_point = ((50.0, 50.0), (5.15, 5.0))
    with pytest.raises(ValueError, match="verificacion fallo"):
        FloorHomography.from_points(px, m, verify=verify_point, tolerance_m=0.10)
