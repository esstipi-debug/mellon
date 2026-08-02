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
