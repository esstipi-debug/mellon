"""Esquema de la observacion de gemba.

Estructurado a proposito: un campo libre produce notas que nadie puede agregar
despues. La disciplina de clasificar el desperdicio en el momento es lo que
permite que 40 observaciones sueltas se conviertan en un Pareto el viernes.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime

# Los siete desperdicios + el octavo (talento), en el vocabulario del CD.
WASTE_TYPES = {
    "TRANSPORTE": "mover material sin transformarlo (traslados entre zonas)",
    "INVENTARIO": "stock parado, WIP acumulado, pallets esperando",
    "MOVIMIENTO": "movimiento del operador sin valor (buscar, agacharse, caminar)",
    "ESPERA": "operador o material esperando (cola, autorizacion, sistema lento)",
    "SOBREPRODUCCION": "preparar antes de tiempo, olas liberadas de mas",
    "SOBREPROCESO": "pasos que el cliente no pide (doble digitacion, doble control)",
    "DEFECTO": "error que obliga a rehacer (mal picking, mal carton, mal rotulo)",
    "TALENTO": "gente que sabe la solucion y nadie le pregunta",
}

FIVE_WHYS_PROMPTS = [
    "¿Por que ocurre esto?",
    "¿Por que existe esa condicion?",
    "¿Por que nadie la corrigio antes?",
    "¿Por que el sistema/proceso lo permite?",
    "¿Por que nadie se entera cuando pasa?",
]

# Preguntas de gemba. No son para el gerente: son para el operador, y en su turno.
GEMBA_QUESTIONS = [
    "Mostrame como lo haces normalmente, no como deberia hacerse.",
    "¿Que es lo que mas te retrasa en un dia malo?",
    "¿Cuando el sistema se equivoca, que haces?",
    "¿Que sabes vos que el sistema no sabe?",
    "Si pudieras cambiar una sola cosa manana, ¿cual seria?",
    "¿Cada cuanto pasa esto que me acabas de mostrar?",
]


@dataclass
class Observation:
    """Una observacion. Timestamp local, siempre.

    `frequency_per_shift` y `duration_s` son obligatorios en la practica: una
    observacion sin cuantificar no entra al Pareto y por lo tanto no existe.
    """

    area: str
    activity: str
    waste_type: str
    description: str
    duration_s: float | None = None
    frequency_per_shift: float | None = None
    operators_affected: int = 1
    shift: str = ""
    observer: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())
    photo_ref: str = ""
    operator_quote: str = ""
    five_whys: list[str] = field(default_factory=list)
    root_cause: str = ""
    countermeasure_idea: str = ""

    def __post_init__(self):
        if self.waste_type not in WASTE_TYPES:
            raise ValueError(f"waste_type debe ser uno de {sorted(WASTE_TYPES)}")

    @property
    def impact_h_per_shift(self) -> float:
        """Horas perdidas por turno. Es la unica columna que ordena el Pareto."""
        if self.duration_s is None or self.frequency_per_shift is None:
            return 0.0
        return self.duration_s * self.frequency_per_shift * self.operators_affected / 3600

    @property
    def impact_h_per_year(self) -> float:
        return self.impact_h_per_shift * 250

    def to_dict(self) -> dict:
        d = asdict(self)
        d["impact_h_per_shift"] = round(self.impact_h_per_shift, 3)
        d["impact_h_per_year"] = round(self.impact_h_per_year, 1)
        d["quantified"] = self.duration_s is not None and self.frequency_per_shift is not None
        return d
