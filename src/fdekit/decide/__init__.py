"""fdekit.decide — el canal DECIDIDA.

Implementa las cinco fases del diseno de `docs/reuniones-decide-diseno.md`:

    0  piloto de proceso, dos semanas, sin software en la sala   `pilot`
    1  registro direccionable versionado en git                  `schema/store/query`
    2  parser de habla espanola y cola de revision               `parse/lexicon/draft`
    3  canal HABLADA, cita congelada y resolutor L0/L1/L2        `transcript/anchor/resolve`
    4  medicion, con compuerta de volumen                        `eventlog/metrics/export`

`__all__` expone la superficie de las fases 0-1 mas los helpers de parseo. Lo de
fases 3-4 —`AliasStore`, `resolve`, `confirm`, `freeze`, `verify`, `volume_gate`,
`report`, `to_graphify`, `evaluate_pilot`— se importa del submodulo
correspondiente, a proposito: son APIs de uso puntual y no queremos que el
espacio de nombres del paquete sugiera que todas se usan igual de seguido.

Lo que entrega la fase 1 sola, sin audio ni resolutor:

  - `agenda()` se calcula sobre el estado del registro y **puede recomendar
    cancelar la reunion**. Es la unica operacion del sistema que ataca la causa
    y no el efecto.
  - `tick()` cierra el lazo supuesto vencido -> decision EN_RIESGO -> agenda,
    sin que nadie tenga que acordarse de nada.
  - `safe_close()` se niega a cerrar una decision que todavia tiene compromisos
    abiertos, y lista cuales.

La regla que gobierna todo el modulo:

    No prometemos resolver siempre. Prometemos no mentir nunca en silencio.

Por eso `referencing()` devuelve siempre `Coverage`: en fase 1 el indice solo
contiene enlaces puestos a mano, y decirlo es parte del contrato. Heredar la
interfaz de la promesa de Serena sin heredar la garantia —y callarlo— es el
error mas grave que puede cometer este diseno.
"""

from .schema import (
    ASSUMPTION_STATUS,
    COMMITMENT_STATUS,
    DECISION_STATUS,
    QUESTION_STATUS,
    Anchor,
    Assumption,
    Commitment,
    Consent,
    Decision,
    Meeting,
    OpenQuestion,
    parse_date,
)
from .draft import (
    EXPIRA_EN_HORAS,
    DecisionDraft,
    DraftStore,
    draft_decisions,
    expire,
    review_queue,
    to_entity,
)
from .parse import (
    DateHit,
    MarkerHit,
    OwnerHit,
    classify_marker,
    extract_rationale,
    extract_slots,
    parse_due_date,
    resolve_owner,
)
from .store import MAX_PROMOTIONS_PER_MEETING, DecideStore, PromotionBudgetExceeded
from .query import (
    Agenda,
    Coverage,
    agenda,
    implementations,
    referencing,
    safe_close,
    tick,
    why,
)

__all__ = [
    "Anchor",
    "Assumption",
    "Commitment",
    "Consent",
    "Decision",
    "Meeting",
    "OpenQuestion",
    "parse_date",
    "DECISION_STATUS",
    "COMMITMENT_STATUS",
    "ASSUMPTION_STATUS",
    "QUESTION_STATUS",
    "DecideStore",
    "PromotionBudgetExceeded",
    "MAX_PROMOTIONS_PER_MEETING",
    "DecisionDraft",
    "DraftStore",
    "draft_decisions",
    "review_queue",
    "expire",
    "to_entity",
    "EXPIRA_EN_HORAS",
    "DateHit",
    "OwnerHit",
    "MarkerHit",
    "parse_due_date",
    "resolve_owner",
    "classify_marker",
    "extract_rationale",
    "extract_slots",
    "Agenda",
    "Coverage",
    "agenda",
    "why",
    "referencing",
    "implementations",
    "safe_close",
    "tick",
]
