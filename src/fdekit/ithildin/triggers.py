"""Detonadores logicos condicionales y automatizacion reactiva pasiva.

El Patron Ithildin:
El trigger permanece dormido sin hacer polling ruidoso ni consumir CPU en vano.
Solo se "ilumina" y dispara cuando un estimulo externo o payload calificado
cumple con el predicado operacional predefinido, respetando tiempos de enfriamiento (cooldown).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class TriggerResult:
    """Resultado de la evaluacion de un estimulo contra un trigger."""

    trigger_name: str
    illuminated: bool
    silenced_by_cooldown: bool
    reason: str
    matched_payload: Mapping[str, Any] | None = None


class ConditionalTrigger:
    """Detonador logico que se activa bajo estimulos precisos."""

    def __init__(
        self,
        name: str,
        predicate: Callable[[Mapping[str, Any]], bool],
        cooldown_seconds: float = 0.0,
        description: str = "",
    ) -> None:
        if not name:
            raise ValueError("name no puede ser vacio")
        self.name = name
        self.predicate = predicate
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.description = description
        self._last_fired_epoch: float | None = None

    def evaluate(self, event_payload: Mapping[str, Any], current_epoch: float) -> TriggerResult:
        """Evalua el payload contra el predicado y el estado de enfriamiento."""
        try:
            matched = self.predicate(event_payload)
        except Exception as exc:  # Un fallo en el predicado no tumba la evaluacion
            return TriggerResult(
                trigger_name=self.name,
                illuminated=False,
                silenced_by_cooldown=False,
                reason=f"Excepcion al evaluar predicado: {exc!r}",
            )

        if not matched:
            return TriggerResult(
                trigger_name=self.name,
                illuminated=False,
                silenced_by_cooldown=False,
                reason="El estimulo no cumple las condiciones del predicado.",
            )

        # Chequeo de cooldown
        if self._last_fired_epoch is not None:
            elapsed = current_epoch - self._last_fired_epoch
            if elapsed < self.cooldown_seconds:
                return TriggerResult(
                    trigger_name=self.name,
                    illuminated=False,
                    silenced_by_cooldown=True,
                    reason=f"Silenciado por cooldown: restan {self.cooldown_seconds - elapsed:.2f}s.",
                    matched_payload=event_payload,
                )

        self._last_fired_epoch = current_epoch
        return TriggerResult(
            trigger_name=self.name,
            illuminated=True,
            silenced_by_cooldown=False,
            reason="Estimulo calificado. Trigger iluminado con exito.",
            matched_payload=event_payload,
        )


class IthildinTriggerRegistry:
    """Registro y despachador de triggers condicionales."""

    def __init__(self, triggers: Sequence[ConditionalTrigger] = ()) -> None:
        self._triggers: dict[str, ConditionalTrigger] = {t.name: t for t in triggers}

    def register(self, trigger: ConditionalTrigger) -> None:
        """Registra un nuevo trigger condicional."""
        self._triggers[trigger.name] = trigger

    def evaluate_all(
        self, event_payload: Mapping[str, Any], current_epoch: float
    ) -> list[TriggerResult]:
        """Evalua el estimulo contra todos los triggers registrados."""
        results: list[TriggerResult] = []
        for trigger in self._triggers.values():
            results.append(trigger.evaluate(event_payload, current_epoch))
        return results

    def get_illuminated(
        self, event_payload: Mapping[str, Any], current_epoch: float
    ) -> list[TriggerResult]:
        """Filtra y devuelve unicamente los triggers que se iluminaron activamente."""
        return [
            res
            for res in self.evaluate_all(event_payload, current_epoch)
            if res.illuminated
        ]
