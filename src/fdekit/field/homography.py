"""Proyeccion del plano de la imagen al plano del piso.

Cuatro puntos del piso con coordenadas conocidas en metros bastan para mapear
cualquier pixel a metros. Se resuelve con numpy —ocho ecuaciones lineales— y
no con cv2.findHomography, porque esta capa tiene que seguir corriendo en el
notebook prestado del CD, sin OpenCV instalado (regla 2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Umbral para detectar si una proyeccion cae en el horizonte de la homografia.
# No es un area en m^2, sino un limite sobre la coordenada homogenea v[2]:
# si |v[2]| es menor que esto, el punto no tiene proyeccion finita en el piso.
_MIN_HOMOGRAPHY_COORD = 1e-6


def _diameter(points: list[tuple[float, float]]) -> float:
    """Calcula la distancia maxima entre dos puntos del conjunto."""
    max_dist = 0.0
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            x1, y1 = points[i]
            x2, y2 = points[j]
            dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            max_dist = max(max_dist, dist)
    return max_dist


def _validate_quadrilateral(points: list[tuple[float, float]], name: str) -> None:
    """Valida que los cuatro puntos formen un cuadrilatero no degenerado.

    Detecta puntos casi colineales calculando areas de triangulos y comparando
    con el diametro del conjunto. Umbral: 1e-4 * diametro^2.
    """
    if len(points) != 4:
        raise ValueError(f"{name} necesita exactamente 4 puntos, llegaron {len(points)}")

    # Area de los cuatro triangulos formados por ternas consecutivas.
    areas_triangles = []
    for i in range(4):
        p0 = points[i]
        p1 = points[(i + 1) % 4]
        p2 = points[(i + 2) % 4]
        # Usando shoelace para triangulo.
        area = abs((p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])) / 2.0
        areas_triangles.append(area)

    min_area = min(areas_triangles)
    diam = _diameter(points)
    threshold = 1e-4 * (diam ** 2)

    if min_area < threshold:
        raise ValueError(
            f"los cuatro puntos en {name} son casi colineales o degenerados: "
            f"no definen un cuadrilatero. Pegar las marcas mas separadas, formando "
            f"un cuadrilatero ancho, no una franja o linea."
        )


@dataclass(frozen=True)
class FloorHomography:
    matrix: tuple[tuple[float, float, float], ...]

    @staticmethod
    def from_points(
        px: list[tuple[float, float]],
        meters: list[tuple[float, float]],
        verify: tuple[tuple[float, float], tuple[float, float]] | None = None,
        tolerance_m: float = 0.10,
    ) -> "FloorHomography":
        """Construye una homografia a partir de cuatro pares de puntos correspondientes.

        Mapea cada pixel (x_px, y_px) a coordenadas del piso (x_m, y_m) usando una
        transformacion proyectiva. Los cuatro puntos de control definen completamente
        esta transformacion resolviendo ocho ecuaciones lineales.

        px[i] corresponde a meters[i]. Con cuatro puntos, la correspondencia no puede
        detectarse desde adentro: cualquier emparejamiento ajusta exacto por construccion.
        Un orden equivocado produce una homografia perfectamente valida pero
        semanticamente falsa. Si necesitas verificar la correspondencia, pasa un quinto
        punto en `verify` — un par (punto_px, punto_metros) que no esté entre los cuatro
        de calibración.

        CONVENCION DE EJES: en una imagen el eje y crece hacia abajo; en el piso hacia
        arriba. El mismo recorrido visual de las esquinas da sentidos de giro opuestos.
        Eso es normal y no es un error del usuario.

        Args:
            px: Lista de cuatro puntos en pixeles.
            meters: Lista de cuatro puntos en metros.
            verify: Opcional, par (punto_px, punto_metros) para verificar la
                correspondencia. Si el error supera tolerance_m, levanta.
            tolerance_m: Umbral de error permitido en metros (default 0.10). Es mayor
                que el error de marcado esperable (5 cm) pero mucho menor que el error
                de correspondencia equivocada (metros).

        Raises:
            ValueError: Si cantidades no coinciden, hay menos de 4 puntos,
                los puntos son degenerados, o verify falla la tolerancia.
        """
        if len(px) != len(meters):
            raise ValueError(
                f"px y meters tienen que tener la misma cantidad de puntos "
                f"({len(px)} vs {len(meters)})"
            )
        if len(px) != 4:
            raise ValueError(f"hacen falta exactamente cuatro correspondencias, llegaron {len(px)}")

        # Validar que cada conjunto de puntos forme un cuadrilatero valido.
        _validate_quadrilateral(px, "pixeles")
        _validate_quadrilateral(meters, "metros")

        a, b = [], []
        for (x, y), (bigx, bigy) in zip(px, meters):
            a.append([x, y, 1, 0, 0, 0, -bigx * x, -bigx * y])
            b.append(bigx)
            a.append([0, 0, 0, x, y, 1, -bigy * x, -bigy * y])
            b.append(bigy)

        amat = np.asarray(a, dtype=float)

        # Chequeo de rango: tiene que ser completo (rango 8).
        if np.linalg.matrix_rank(amat) < 8:
            raise ValueError(
                "los cuatro puntos son colineales o degenerados: no definen un plano. "
                "Pegar las marcas formando un cuadrilatero, no una linea."
            )

        # Chequeo por numero de condicion: si es muy alto, el sistema es inestable.
        cond = np.linalg.cond(amat)
        if cond > 1e8:
            raise ValueError(
                f"la homografia esta mal condicionada (numero de condicion {cond:.2e}): "
                f"los puntos estan casi alineados o casi coplanares. "
                f"Pegar las marcas formando un cuadrilatero bien separado."
            )

        h, *_ = np.linalg.lstsq(amat, np.asarray(b, dtype=float), rcond=None)
        m = np.append(h, 1.0).reshape(3, 3)
        homography = FloorHomography(matrix=tuple(tuple(float(v) for v in fila) for fila in m))

        # Verificar con un quinto punto si se proporciona.
        if verify is not None:
            (x_px_verify, y_px_verify), (x_m_expected, y_m_expected) = verify
            x_m_actual, y_m_actual = homography.to_meters(x_px_verify, y_px_verify)
            error_x = abs(x_m_actual - x_m_expected)
            error_y = abs(y_m_actual - y_m_expected)
            error_total = (error_x**2 + error_y**2) ** 0.5
            if error_total > tolerance_m:
                raise ValueError(
                    f"la verificacion fallo: el quinto punto se proyecta a "
                    f"({x_m_actual:.3f}, {y_m_actual:.3f}) pero esperaba "
                    f"({x_m_expected:.3f}, {y_m_expected:.3f}), error {error_total:.3f} m. "
                    f"La correspondencia entre px y meters parece estar en distinto orden. "
                    f"Verificar que px[i] y meters[i] sean la misma esquina fisica."
                )

        return homography

    def to_meters(self, x_px: float, y_px: float) -> tuple[float, float]:
        """Proyecta un pixel a coordenadas del piso en metros.

        La proyeccion usa la matriz de homografia calculada por from_points. Es una
        transformacion proyectiva, asi que maneja perspectiva y rotaciones.

        Args:
            x_px: Coordenada x del pixel.
            y_px: Coordenada y del pixel.

        Returns:
            Tupla (x_m, y_m) en metros.

        Raises:
            ValueError: Si el punto cae en el horizonte de la homografia
                (coordenada homogenea v[2] muy cercana a cero).
        """
        m = np.asarray(self.matrix, dtype=float)
        v = m @ np.array([float(x_px), float(y_px), 1.0])
        if abs(v[2]) < _MIN_HOMOGRAPHY_COORD:
            raise ValueError(
                f"el punto ({x_px}, {y_px}) cae en el horizonte de la homografia y "
                "no tiene proyeccion finita en el piso"
            )
        return (float(v[0] / v[2]), float(v[1] / v[2]))
