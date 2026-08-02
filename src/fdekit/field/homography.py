"""Proyeccion del plano de la imagen al plano del piso.

Cuatro puntos del piso con coordenadas conocidas en metros bastan para mapear
cualquier pixel a metros. Se resuelve con numpy —ocho ecuaciones lineales— y
no con cv2.findHomography, porque esta capa tiene que seguir corriendo en el
notebook prestado del CD, sin OpenCV instalado (regla 2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_MIN_AREA_M2 = 1e-6


@dataclass(frozen=True)
class FloorHomography:
    matrix: tuple[tuple[float, float, float], ...]

    @staticmethod
    def from_points(
        px: list[tuple[float, float]], meters: list[tuple[float, float]]
    ) -> "FloorHomography":
        if len(px) != len(meters):
            raise ValueError(
                f"px y meters tienen que tener la misma cantidad de puntos "
                f"({len(px)} vs {len(meters)})"
            )
        if len(px) != 4:
            raise ValueError(f"hacen falta exactamente cuatro correspondencias, llegaron {len(px)}")

        a, b = [], []
        for (x, y), (bigx, bigy) in zip(px, meters):
            a.append([x, y, 1, 0, 0, 0, -bigx * x, -bigx * y])
            b.append(bigx)
            a.append([0, 0, 0, x, y, 1, -bigy * x, -bigy * y])
            b.append(bigy)

        amat = np.asarray(a, dtype=float)
        if np.linalg.matrix_rank(amat) < 8:
            raise ValueError(
                "los cuatro puntos son colineales o degenerados: no definen un plano. "
                "Pegar las marcas formando un cuadrilatero, no una linea."
            )

        h, *_ = np.linalg.lstsq(amat, np.asarray(b, dtype=float), rcond=None)
        m = np.append(h, 1.0).reshape(3, 3)
        return FloorHomography(matrix=tuple(tuple(float(v) for v in fila) for fila in m))

    def to_meters(self, x_px: float, y_px: float) -> tuple[float, float]:
        m = np.asarray(self.matrix, dtype=float)
        v = m @ np.array([float(x_px), float(y_px), 1.0])
        if abs(v[2]) < _MIN_AREA_M2:
            raise ValueError(
                f"el punto ({x_px}, {y_px}) cae en el horizonte de la homografia y "
                "no tiene proyeccion finita en el piso"
            )
        return (float(v[0] / v[2]), float(v[1] / v[2]))
