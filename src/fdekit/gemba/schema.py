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
    # ¿Este desperdicio ya deja rastro en el log del WMS?
    #
    # Es el campo que permite que gemba entre al caso economico sin contar dos
    # veces. Casi todo lo que se observa en un pasillo YA esta en el log bajo
    # otro nombre: "buscar un SKU que no esta" es PICK_EXCEPTION_LOCATION,
    # "rehacer el carton" es CARTON_REWORK, "esperar pedidos liberados" es la
    # espera de la transicion ORDER_RELEASED -> PICK. Sumar esas horas a las que
    # ya aporta `timestudy` duplicaria la palanca L1 entera.
    #
    # Lo que gemba ve y el log no puede ver es el trabajo sin transaccion:
    # buscar el carro, esperar al supervisor, la planilla paralela, el traslado
    # que nadie escanea. Eso es lo unico que suma.
    #
    # `None` significa "no se declaro", no "no esta": va a la cola de revision.
    # Un default de True o False decidiria en silencio si la observacion vale
    # plata, que es exactamente lo que la regla 1 del repo prohibe.
    in_event_log: bool | None = None
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
    def quantified(self) -> bool:
        return self.duration_s is not None and self.frequency_per_shift is not None

    @property
    def counts_for_value(self) -> bool:
        """Si esta observacion puede entrar al caso economico.

        Exige las dos condiciones: cuantificada, y declarada como fuera del log.
        Ver `in_event_log`.
        """
        return self.quantified and self.in_event_log is False

    def to_dict(self) -> dict:
        d = asdict(self)
        # Unidad de salida: el turno observado. El `* 250` que vivia aca era el
        # ultimo resto de la anualizacion doble que el repo ya elimino de
        # `travel_stats` y `standard_work_gap`, y sobrevivio solo porque nadie
        # aguas abajo lo leia. Ahora que gemba alimenta L1, el 250 seria un
        # residuo de 250/operating_days (-17% con los 300 dias del arquetipo).
        # La anualizacion es una sola y vive en `value/levers.py`.
        d["impact_h_per_shift"] = round(self.impact_h_per_shift, 4)
        d["quantified"] = self.quantified
        d["counts_for_value"] = self.counts_for_value
        return d
