"""Conditional logical triggers and passive reactive automation.

The Ithildin Pattern:
The trigger remains dormant without loud polling or CPU waste.
It only "illuminates" and fires when an external stimulus or qualified payload
satisfies the predefined operational predicate, enforcing cooldown intervals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class TriggerResult:
    """Outcome of stimulus evaluation against a trigger."""

    trigger_name: str
    illuminated: bool
    silenced_by_cooldown: bool
    reason: str
    matched_payload: Mapping[str, Any] | None = None


class ConditionalTrigger:
    """Logical trigger activated only by precise stimuli."""

    def __init__(
        self,
        name: str,
        predicate: Callable[[Mapping[str, Any]], bool],
        cooldown_seconds: float = 0.0,
        description: str = "",
    ) -> None:
        if not name:
            raise ValueError("name cannot be empty")
        self.name = name
        self.predicate = predicate
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self.description = description
        self._last_fired_epoch: float | None = None

    def evaluate(self, event_payload: Mapping[str, Any], current_epoch: float) -> TriggerResult:
        """Evaluates payload against predicate and cooldown state."""
        try:
            matched = self.predicate(event_payload)
        except Exception as exc:  # A predicate failure does not crash the evaluation
            return TriggerResult(
                trigger_name=self.name,
                illuminated=False,
                silenced_by_cooldown=False,
                reason=f"Predicate evaluation error: {exc!r}",
            )

        if not matched:
            return TriggerResult(
                trigger_name=self.name,
                illuminated=False,
                silenced_by_cooldown=False,
                reason="Stimulus does not satisfy predicate condition.",
            )

        # Cooldown check
        if self._last_fired_epoch is not None:
            elapsed = current_epoch - self._last_fired_epoch
            if elapsed < self.cooldown_seconds:
                return TriggerResult(
                    trigger_name=self.name,
                    illuminated=False,
                    silenced_by_cooldown=True,
                    reason=f"Silenced by cooldown: {self.cooldown_seconds - elapsed:.2f}s remaining.",
                    matched_payload=event_payload,
                )

        self._last_fired_epoch = current_epoch
        return TriggerResult(
            trigger_name=self.name,
            illuminated=True,
            silenced_by_cooldown=False,
            reason="Qualified stimulus. Trigger successfully illuminated.",
            matched_payload=event_payload,
        )


class IthildinTriggerRegistry:
    """Registry and dispatcher for conditional triggers."""

    def __init__(self, triggers: Sequence[ConditionalTrigger] = ()) -> None:
        self._triggers: dict[str, ConditionalTrigger] = {t.name: t for t in triggers}

    def register(self, trigger: ConditionalTrigger) -> None:
        """Registers a new conditional trigger."""
        self._triggers[trigger.name] = trigger

    def evaluate_all(
        self, event_payload: Mapping[str, Any], current_epoch: float
    ) -> list[TriggerResult]:
        """Evaluates stimulus against all registered triggers."""
        results: list[TriggerResult] = []
        for trigger in self._triggers.values():
            results.append(trigger.evaluate(event_payload, current_epoch))
        return results

    def get_illuminated(
        self, event_payload: Mapping[str, Any], current_epoch: float
    ) -> list[TriggerResult]:
        """Filters and returns only actively illuminated triggers."""
        return [
            res
            for res in self.evaluate_all(event_payload, current_epoch)
            if res.illuminated
        ]
