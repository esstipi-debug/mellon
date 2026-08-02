"""Modelo geometrico del centro de distribucion.

Un CD de pasillos paralelos con dos pasillos transversales (frontal y trasero).
La distancia entre dos ubicaciones no es euclidiana: para cambiar de pasillo hay
que salir por una transversal. Esa es exactamente la razon por la que el mapa de
espagueti sorprende al cliente — la distancia "en linea recta" que todos tienen
en la cabeza subestima el recorrido real entre 30% y 200%.

Codigo de ubicacion: ``AA-BBB-L`` (pasillo-modulo-nivel), p.ej. ``03-017-2``.
El muelle/estacion de packing es la ubicacion especial ``DOCK``.
"""

from __future__ import annotations

from dataclasses import dataclass

DOCK = "DOCK"

# Velocidades y tiempos base, medidos en terreno y sobreescribibles por cliente.
WALK_SPEED_MPS = 1.1  # caminata con carro de picking cargado
VERTICAL_PENALTY_S = {1: 0.0, 2: 2.0, 3: 6.0, 4: 14.0}  # escalera / alcance


@dataclass(frozen=True)
class Layout:
    """Geometria del CD.

    aisles      cantidad de pasillos
    bays        modulos por pasillo
    levels      niveles verticales por modulo
    aisle_pitch distancia entre ejes de pasillo (m)
    bay_pitch   largo de un modulo (m)
    """

    aisles: int = 12
    bays: int = 50
    levels: int = 4
    aisle_pitch: float = 3.0
    bay_pitch: float = 1.2

    # ------------------------------------------------------------------ coords

    @property
    def depth_m(self) -> float:
        return self.bays * self.bay_pitch

    def location_code(self, aisle: int, bay: int, level: int) -> str:
        return f"{aisle:02d}-{bay:03d}-{level}"

    def parse(self, code: str) -> tuple[int, int, int]:
        """Devuelve (pasillo, modulo, nivel). DOCK -> (0, 0, 1)."""
        if code == DOCK:
            return (0, 0, 1)
        aisle, bay, level = code.split("-")
        return (int(aisle), int(bay), int(level))

    def xy(self, code: str) -> tuple[float, float]:
        """Coordenadas en planta, en metros. El dock esta en el origen."""
        aisle, bay, _ = self.parse(code)
        return (aisle * self.aisle_pitch, bay * self.bay_pitch)

    def all_locations(self) -> list[str]:
        return [
            self.location_code(a, b, l)
            for a in range(1, self.aisles + 1)
            for b in range(1, self.bays + 1)
            for l in range(1, self.levels + 1)
        ]

    # --------------------------------------------------------------- distancia

    def distance(self, a: str, b: str) -> float:
        """Distancia de recorrido en metros entre dos ubicaciones.

        Dentro del mismo pasillo se recorre a lo largo. Entre pasillos hay que
        salir por la transversal frontal (y=0) o la trasera (y=depth), lo que
        sea mas corto.
        """
        (ax, ay), (bx, by) = self.xy(a), self.xy(b)
        if abs(ax - bx) < 1e-9:
            return abs(ay - by)

        cross = abs(ax - bx)
        via_front = ay + cross + by
        via_back = (self.depth_m - ay) + cross + (self.depth_m - by)
        return min(via_front, via_back)

    def travel_time_s(self, a: str, b: str) -> float:
        return self.distance(a, b) / WALK_SPEED_MPS

    def reach_penalty_s(self, code: str) -> float:
        """Penalidad por alcanzar un nivel alto. El nivel 4 cuesta 14s: esa es
        la razon por la que el slotting vertical importa tanto como el
        horizontal, y casi nadie lo mide."""
        _, _, level = self.parse(code)
        return VERTICAL_PENALTY_S.get(level, 20.0)

    def route_distance(self, stops: list[str]) -> float:
        """Distancia total de una ruta que sale del dock, visita las paradas en
        orden y vuelve al dock."""
        if not stops:
            return 0.0
        path = [DOCK, *stops, DOCK]
        return sum(self.distance(p, q) for p, q in zip(path, path[1:]))

    def golden_zone(self, fraction: float = 0.2) -> set[str]:
        """Ubicaciones cerca del dock y a nivel ergonomico (1-2).

        Es donde deberian estar los SKU clase A. Cuando no lo estan, el kit lo
        detecta y esa sola observacion suele pagar el despliegue."""
        max_bay = max(1, int(self.bays * fraction))
        return {
            self.location_code(a, b, l)
            for a in range(1, self.aisles + 1)
            for b in range(1, max_bay + 1)
            for l in (1, 2)
        }
