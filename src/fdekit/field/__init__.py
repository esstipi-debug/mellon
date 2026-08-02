"""Toolkit de terreno — sensores que miden lo que el WMS infiere.

El corte que gobierna el paquete: `vision` es la unica pieza que toca cv2, y
solo produce detecciones crudas. Todo lo demas es Python puro sobre un CSV, y
por eso se testea sin camara.
"""

from .coverage import MeasurementCoverage

__all__ = ["MeasurementCoverage"]
