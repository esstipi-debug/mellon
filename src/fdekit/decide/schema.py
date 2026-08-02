"""Las siete entidades del canal DECIDIDA.

El techo es siete. Una entidad mas entra solo si hay una operacion que la lee y
un diagnostico que la usa.

Cada una expone `validate() -> list[str]`, no un booleano — mismo contrato que
`A3.validate` y `BaselineSpec.validate`: la lista vacia significa "listo", y la
lista con contenido es la conversacion que hay que tener. Un booleano obliga a
adivinar que falta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

DECISION_STATUS = ("VIGENTE", "SUPERADA", "REVERTIDA", "EN_RIESGO")
COMMITMENT_STATUS = ("ABIERTO", "CUMPLIDO", "VENCIDO", "CANCELADO", "ZOMBI")
# VERIFICADO no esta en el diseno original. Se agrega porque sin el, un supuesto
# vencido no tiene forma de dejar de poner en riesgo a su decision, y la agenda
# arrastraria el mismo item para siempre.
ASSUMPTION_STATUS = ("VIGENTE", "VENCIDO", "VIOLADO", "VERIFICADO")
QUESTION_STATUS = ("ABIERTA", "RESUELTA", "EXPIRADA")
ANCHOR_SOURCE_STATE = ("VIVA", "CADUCADA")
ALIAS_STATUS = ("VIGENTE", "EN_DISPUTA", "RETIRADO")

# Capas del resolutor. El tier dice cuanto se puede confiar en una arista, y
# acompana a la arista para siempre — es el mismo vocabulario que usa graphify
# para su audit trail.
TIER_EXTRACTED = "EXTRACTED"  # deterministico: ID literal o alias confirmado
TIER_INFERRED = "INFERRED"  # heuristico: coincidencia de slots
TIER_AMBIGUOUS = "AMBIGUOUS"  # empate: es un error reportado, no una eleccion

# Un `statement` que empieza asi no es una decision: es la intencion de decidir
# mas adelante. Registrarlo como decision es como el registro empieza a mentir.
HEDGES = (
    "evaluar si", "ver si", "analizar si", "estudiar si", "revisar si",
    "quizas", "tal vez", "posiblemente", "considerar", "explorar",
    "discutir", "conversar", "definir mas adelante", "queda pendiente",
)

# Un criterio es verificable si trae un numero o uno de estos predicados. Regla
# heredada de `A3.validate`, que rechaza una condicion actual sin numeros.
VERIFIABLE_PREDICATES = (
    "%", "por ciento", "menor", "mayor", "igual", "antes de", "a mas tardar",
    "sin ", "cero", "ninguno", "todos", "ninguna", "existe", "aprobado",
    "firmado", "publicado", "desplegado", "<", ">", "=",
)

# Aperturas que no producen una pregunta cerrable. El gate de agenda las rechaza:
# un punto que no se puede cerrar no es un punto de decision, es una charla.
NON_CLOSABLE_OPENERS = (
    "como ", "por que", "porque", "que opinan", "que piensan", "cual es la mejor forma",
    "que hacemos con", "que pasa con", "hablemos", "revisemos",
)


def parse_date(value) -> date:
    """Acepta solo fecha absoluta ISO (`YYYY-MM-DD`) o un `date`.

    El habla relativa ("el viernes", "en dos semanas") se resuelve en fase 2 con
    `parse_due_date`. Aceptarla aca sin resolver produciria compromisos con
    fecha ambigua, que es la forma mas comun de que un compromiso no se cumpla
    y nadie pueda decir que estaba atrasado.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise TypeError(f"fecha no reconocida: {value!r}")
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"fecha no absoluta: {value!r}. Usar YYYY-MM-DD. "
            "El habla relativa se resuelve en fase 2."
        ) from exc


def _has_number(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


# La normalizacion es una sola en todo el kit. Definirla aca otra vez —sin
# quitar acentos— hacia que `HEDGES` y `VERIFIABLE_PREDICATES`, que estan
# escritos sin tildes, fallaran contra el espanol real.
from ..gemba.transcribe import normalize as _norm


# ------------------------------------------------------------------ soporte


@dataclass(frozen=True)
class Consent:
    """Consentimiento para grabar. Argumento obligatorio de `Meeting`.

    Es un objeto y no un flag de configuracion a proposito: un flag se olvida en
    un default y despues no hay forma de saber si alguien lo autorizo. Esto
    levanta excepcion si falta, que es la unica pieza de cumplimiento imposible
    de retrofitear.

    En Chile la Ley 21.719 entra en vigencia el 1-dic-2026. Ojo con `basis`: el
    "consentimiento" de un trabajador a ser grabado por el consultor de su
    empleador no es libre, y por lo tanto es una base de licitud debil. La base
    correcta suele ser interes legitimo con informacion previa y posibilidad
    real de no ser grabado.
    """

    granted: bool
    granted_by: str
    basis: str  # "consentimiento" | "interes_legitimo" | "contrato" | ...
    recording_allowed: bool = False
    retention_days: int | None = None
    note: str = ""

    def validate(self) -> list[str]:
        issues = []
        if self.granted and not self.granted_by:
            raise_msg = "consentimiento otorgado sin decir quien lo otorgo"
            issues.append(raise_msg)
        if not self.basis:
            issues.append("sin base de licitud declarada")
        if self.recording_allowed and self.retention_days is None:
            issues.append(
                "se permite grabar sin politica de retencion: definir retention_days "
                "antes de grabar, no despues"
            )
        return issues


@dataclass
class Anchor:
    """Puente DECIDIDA -> HABLADA. Se llena en fase 3; en fase 1 queda vacio.

    La cita se **copia**, no se enlaza: el canal HABLADA tiene fecha de
    vencimiento y un puntero a un recurso con politica de retencion es un
    puntero colgante por diseno.
    """

    meeting_id: str = ""
    t_start: float | None = None
    t_end: float | None = None
    cita_congelada: str = ""
    transcript_sha256: str = ""
    estado_fuente: str = "VIVA"

    @property
    def empty(self) -> bool:
        return not self.cita_congelada

    def validate(self) -> list[str]:
        issues = []
        if self.cita_congelada and len(self.cita_congelada) > 500:
            issues.append("cita congelada sobre 500 chars: una cita larga no se revisa")
        if self.cita_congelada and not self.transcript_sha256:
            issues.append("cita sin hash del transcripto: no es auditable")
        if self.estado_fuente not in ANCHOR_SOURCE_STATE:
            issues.append(f"estado_fuente invalido: {self.estado_fuente}")
        return issues


# ----------------------------------------------------------------- entidades


@dataclass
class Decision:
    """El simbolo. `id` es el nombre calificado; `statement + owner + criteria`
    es la firma. Nunca se navega por el minuto del audio, siempre por lo que
    significa."""

    id: str
    statement: str
    owner: str
    date_decided: date
    criteria: str
    rationale: str
    meeting_id: str = ""
    status: str = "VIGENTE"
    depends_on: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str = ""
    scope: str = ""
    version: int = 1
    historial_statements: list[str] = field(default_factory=list)
    # Fase 3. Se persisten para no perderlos, no se usan todavia.
    aliases: list[str] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)
    anchor: Anchor = field(default_factory=Anchor)

    def validate(self, roster: tuple[str, ...] | None = None) -> list[str]:
        issues: list[str] = []

        s = _norm(self.statement)
        if len(s) < 10:
            issues.append("statement demasiado corto para ser una decision")
        if s.endswith("?"):
            issues.append("el statement es una pregunta: eso es un OpenQuestion, no una decision")
        hedge = next((h for h in HEDGES if s.startswith(h)), None)
        if hedge:
            issues.append(
                f"el statement empieza con '{hedge}': es la intencion de decidir, no una "
                "decision. Registrarlo como decision es como el registro empieza a mentir"
            )

        if not self.owner:
            issues.append("sin dueno")
        elif roster is not None and self.owner not in roster:
            issues.append(
                f"dueno '{self.owner}' no esta en el roster {list(roster)}: el roster es "
                "una lista cerrada y es lo que hace deterministica la resolucion de duenos"
            )

        if not self.criteria:
            issues.append("sin criterio: no hay forma de saber si se cumplio")
        elif not (_has_number(self.criteria) or any(p in _norm(self.criteria) for p in VERIFIABLE_PREDICATES)):
            issues.append(
                "el criterio no contiene un numero ni un predicado verificable: "
                "'que funcione mejor' no es un criterio"
            )

        if not self.rationale:
            issues.append("sin rationale: en seis semanas nadie va a saber por que, y se revierte")

        if self.status not in DECISION_STATUS:
            issues.append(f"status invalido: {self.status}")
        if self.status == "SUPERADA" and not self.superseded_by:
            issues.append("marcada SUPERADA sin decir por cual")
        if self.id in self.depends_on:
            issues.append("depende de si misma")

        issues.extend(self.anchor.validate())
        return issues


@dataclass
class Commitment:
    """`find_implementations`. Es una relacion 1:N real y verificable, no una
    metafora: `safe_close` se apoya en esto.

    `decision_id` es obligatorio: un compromiso huerfano es una tarea, y las
    tareas viven en el gestor de tareas del cliente, no aca.
    """

    id: str
    decision_id: str
    what: str
    owner: str
    due: date
    evidence_of_done: str = ""
    status: str = "ABIERTO"
    owner_presente_al_decidir: bool | None = None
    meeting_id: str = ""

    def validate(self, roster: tuple[str, ...] | None = None) -> list[str]:
        issues: list[str] = []
        if not self.decision_id:
            issues.append(
                "sin decision_id: un compromiso huerfano es una tarea, no un compromiso"
            )
        if len(_norm(self.what)) < 8:
            issues.append("descripcion demasiado corta")
        if not self.owner:
            issues.append("sin dueno")
        elif roster is not None and self.owner not in roster:
            issues.append(f"dueno '{self.owner}' fuera del roster {list(roster)}")
        if not isinstance(self.due, date):
            issues.append("due no es una fecha absoluta")
        if not self.evidence_of_done:
            issues.append(
                "sin evidencia de cumplimiento: sin eso, 'hecho' es una opinion"
            )
        if self.status not in COMMITMENT_STATUS:
            issues.append(f"status invalido: {self.status}")
        if self.owner_presente_al_decidir is False:
            issues.append(
                "el dueno no estaba cuando se decidio: confirmar que acepta antes de "
                "contarlo como compromiso"
            )
        return issues

    def days_late(self, today: date) -> int:
        return (today - self.due).days


@dataclass
class Assumption:
    """La entidad mas importante del sistema, y la que no tiene analogo en Serena.

    Es lo mas parecido a un test que falla: cuando `check_by` vence, la decision
    pasa sola a EN_RIESGO y aparece sola en la agenda. Es el mecanismo causal
    contra la reversion por ignorancia — no la memoria de alguien, un vencimiento
    con fecha.
    """

    id: str
    decision_id: str
    statement: str
    check_by: date
    source: str = "sin_fuente"
    status: str = "VIGENTE"
    meeting_id: str = ""

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.decision_id:
            issues.append("sin decision_id: un supuesto suelto no pone nada en riesgo")
        if len(_norm(self.statement)) < 8:
            issues.append("statement demasiado corto")
        if not isinstance(self.check_by, date):
            issues.append("check_by no es una fecha absoluta")
        if self.status not in ASSUMPTION_STATUS:
            issues.append(f"status invalido: {self.status}")
        return issues

    def advisories(self) -> list[str]:
        """No bloquean el registro pero se muestran. Mismo patron que
        `ValueCase.warnings()`: hay cosas que hay que decir sin impedir."""
        out = []
        if self.source == "sin_fuente":
            out.append(
                f"{self.id or 'supuesto'} sin fuente: es el candidato mas probable a "
                "caerse y nadie va a saber a quien preguntarle"
            )
        return out

    @property
    def pone_en_riesgo(self) -> bool:
        return self.status in ("VENCIDO", "VIOLADO")


@dataclass
class OpenQuestion:
    """Un simbolo no resuelto: build rojo.

    Analogo exacto de `GembaSession.unquantified()` — lo no decidido va a una
    cola con dueno y fecha. Es lo que alimenta el gate de agenda.
    """

    id: str
    question: str
    resolver: str
    resolve_by: date
    blocks: list[str] = field(default_factory=list)
    status: str = "ABIERTA"
    answer_ref: str = ""
    meeting_id: str = ""
    # Solicitud de reapertura de una decision existente.
    reopen_of: str = ""
    new_evidence: str = ""

    def validate(self, roster: tuple[str, ...] | None = None) -> list[str]:
        issues: list[str] = []
        if len(_norm(self.question)) < 8:
            issues.append("pregunta demasiado corta")
        if not self.resolver:
            issues.append("sin resolver: quien la responde, no quien la hizo")
        elif roster is not None and self.resolver not in roster:
            issues.append(f"resolver '{self.resolver}' fuera del roster {list(roster)}")
        if not isinstance(self.resolve_by, date):
            issues.append("resolve_by no es una fecha absoluta")
        if self.status not in QUESTION_STATUS:
            issues.append(f"status invalido: {self.status}")
        if self.reopen_of and not _has_number(self.new_evidence):
            issues.append(
                "solicitud de reapertura sin dato nuevo: para reabrir hay que traer un "
                "numero, no una opinion"
            )
        return issues

    @property
    def closable(self) -> tuple[bool, str]:
        """Condicion (b) del gate: enunciada como pregunta cerrable.

        No alcanza con terminar en '?': "¿como lo hacemos?" es una charla con
        signo de interrogacion. Se rechazan las aperturas que no admiten cierre.
        """
        q = _norm(self.question)
        if not q.endswith("?"):
            return False, "no esta enunciada como pregunta (falta '?')"
        body = q.lstrip("¿").strip()
        opener = next((o for o in NON_CLOSABLE_OPENERS if body.startswith(o)), None)
        if opener:
            return False, f"empieza con '{opener.strip()}': no admite cierre en la reunion"
        return True, ""


@dataclass
class Alias:
    """La entrada del indice de referencias. El unico activo que se acumula y
    lo unico que hace que el sistema **mejore** con el uso.

    Tambien es lo unico que puede envenenarse. Una sola confirmacion humana
    equivocada escribe `"lo del slotting" -> D-041`, y desde ahi todas las
    menciones futuras resuelven mal con EXTRACTED 1.0, sin volver a pasar por
    L2 ni por la cola. El error deja de ser detectable **justo porque se volvio
    deterministico**.

    De ahi las tres defensas que estan en los campos:

      - `scope` obligatorio y `valido_desde`/`valido_hasta`: nunca global,
        nunca eterno. "Lo del slotting" es D-034 en marzo y D-051 en junio
        porque el tema recurre — la colision no es un accidente, es el caso
        normal.
      - `estado` EN_DISPUTA: lo marca `tick()` cuando nace un simbolo nuevo que
        colisiona. Un alias en disputa no resuelve en L1.
      - `mentions_resueltas`: procedencia completa, para que `unalias()` pueda
        revertir todo lo que ese alias decidio.
    """

    surface_norm: str
    symbol_id: str
    scope: str
    valido_desde: date
    confirmado_por: str
    valido_hasta: date | None = None
    confirmado_en: str = ""
    mentions_resueltas: list[str] = field(default_factory=list)
    estado: str = "VIGENTE"

    def validate(self) -> list[str]:
        issues: list[str] = []
        if len(self.surface_norm) < 4:
            issues.append("forma de superficie demasiado corta: resolveria cualquier cosa")
        if not self.symbol_id:
            issues.append("sin simbolo destino")
        if not self.scope:
            issues.append(
                "alias sin scope: un alias global resuelve en contextos donde nadie lo "
                "confirmo, y ese es el camino directo al envenenamiento"
            )
        if not self.confirmado_por:
            issues.append("sin quien lo confirmo: sin procedencia no hay como auditarlo")
        if self.valido_hasta and self.valido_hasta < self.valido_desde:
            issues.append("vigencia invertida")
        if self.estado not in ALIAS_STATUS:
            issues.append(f"estado invalido: {self.estado}")
        return issues

    def vigente_en(self, when: date) -> bool:
        if self.estado != "VIGENTE":
            return False
        if when < self.valido_desde:
            return False
        return self.valido_hasta is None or when <= self.valido_hasta

    def cubre_scope(self, contexto: str) -> bool:
        """El alias resuelve si su scope contiene al contexto. Un alias de
        `pudahuel` sirve en `pudahuel/slotting`, pero uno de
        `pudahuel/slotting` no sirve en `quilicura`."""
        if not self.scope:
            return False
        return contexto == self.scope or contexto.startswith(self.scope + "/")


@dataclass
class Meeting:
    """El archivo fuente. El `roster` cumple el rol del scope lexico: es la
    lista cerrada contra la que se resuelven duenos de forma deterministica."""

    id: str
    date: date
    roster: tuple[str, ...]
    consent: Consent
    facilitator: str = ""
    transcript_ref: str = ""
    audio_ref: str = ""
    # Scope de la serie. Es el analogo del scope lexico: acota contra que alias
    # se resuelve. Sin el, un alias de un CD resolveria en otro.
    scope: str = ""
    transcript_sha256: str = ""

    def __post_init__(self):
        if self.consent is None:
            raise ValueError(
                "Meeting requiere `consent`. No es un flag de configuracion: es la "
                "unica pieza de cumplimiento que no se puede retrofitear, y un default "
                "silencioso hace imposible saber despues si alguien autorizo."
            )
        if isinstance(self.roster, list):
            self.roster = tuple(self.roster)
        if not self.roster:
            raise ValueError(
                "Meeting sin roster. El roster es el scope lexico del sistema: sin el "
                "no hay resolucion deterministica de duenos y todo lo demas se cae."
            )

    def validate(self) -> list[str]:
        issues = list(self.consent.validate())
        if not self.facilitator:
            issues.append("sin facilitador: nadie va a decir la frase-marcador")
        elif self.facilitator not in self.roster:
            issues.append(f"facilitador '{self.facilitator}' fuera del roster")
        if len(self.roster) > 9:
            issues.append(
                f"{len(self.roster)} personas: sobre 9 no es una reunion de decision, "
                "es una difusion. Considerar partirla"
            )
        if self.audio_ref and not self.consent.recording_allowed:
            issues.append("hay audio referenciado y el consentimiento no permite grabar")
        return issues
