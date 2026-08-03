"""Las siete entidades del canal DECIDIDA.

El techo es siete. Una entidad mas entra solo si hay una operacion que la lee y
un diagnostico que la usa.

Cada una expone `validate() -> list[str]`, no un booleano — mismo contrato que
`A3.validate` y `BaselineSpec.validate`: la lista vacia significa "listo", y la
lista con contenido es la conversacion que hay que tener. Un booleano obliga a
adivinar que falta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

# EN_CONFLICTO: una decision de fuera de la sala contradice a una VIGENTE.
# **Es suspension, no muerte**, y por eso NO entra a `DEAD_DECISION_STATUS`: sus
# compromisos no son zombis. Un zombi es gente ejecutando algo ya revertido; aca
# nadie revirtio nada todavia — se dejo de saber cual rige, que es distinto y se
# arregla mirandolo, no cancelandolo.
DECISION_STATUS = ("VIGENTE", "SUPERADA", "REVERTIDA", "EN_RIESGO", "EN_CONFLICTO")
# Como se cierra un conflicto. Las tres son decisiones humanas: ninguna se
# infiere. COEXISTEN existe porque la contradiccion suele ser aparente — dos
# decisiones sobre sitios o turnos distintos que se leyeron como una.
CONFLICT_RESOLUTIONS = ("GANA_SALA", "GANA_EXTERNA", "COEXISTEN")
COMMITMENT_STATUS = ("ABIERTO", "CUMPLIDO", "VENCIDO", "CANCELADO", "ZOMBI")
# VERIFICADO no esta en el diseno original. Se agrega porque sin el, un supuesto
# vencido no tiene forma de dejar de poner en riesgo a su decision, y la agenda
# arrastraria el mismo item para siempre.
ASSUMPTION_STATUS = ("VIGENTE", "VENCIDO", "VIOLADO", "VERIFICADO")
QUESTION_STATUS = ("ABIERTA", "RESUELTA", "EXPIRADA")
ANCHOR_SOURCE_STATE = ("VIVA", "CADUCADA")
ALIAS_STATUS = ("VIGENTE", "EN_DISPUTA", "RETIRADO")

# --------------------------------------------------- clase, canal y origen
#
# Los tres campos que contestan la pregunta transversal: **que cuenta como
# reunion de decision y que decision entra a las metricas de control.** Sin
# ellos, cada hueco agregaba su propio filtro en `volume_gate`,
# `circular_minutes` y `touches_to_decide` — tres reglas para una sola pregunta,
# escritas en cinco lugares, que se desincronizan el primer dia.

MEETING_CHANNEL = ("SINCRONICO", "ASINCRONICO")
MEETING_CLASS = ("COMITE", "UNO_A_UNO", "KICKOFF", "TERRENO", "HANDOVER", "INCIDENTE")
# De donde salio una decision. Solo REUNION es auditable: tiene roster, fecha y
# consentimiento detras.
DECISION_ORIGIN = ("REUNION", "SIEMBRA", "ACTA_HISTORICA", "CHAT", "PASILLO")

# Estado de captura de una sesion. **Se DERIVA de los hechos, no se escribe.**
# Escribirlo fue la primera idea y se cae sola: el flujo canonico sin audio
# (meeting -> draft -> review) no tiene donde escribir CAPTURADA, porque el
# unico que lo sabia era `transcribe`, que en ese flujo no corre. Y un default
# como NO_REGISTRADA reinterpreta como fallida cada sesion ya persistida.
CAPTURE_STATES = (
    "CAPTURADA",         # algo se promovio: la sesion dejo registro
    "COLA_NO_REVISADA",  # hay borradores y nadie los miro
    "SIN_RITUAL",        # hubo habla y no salio ni un borrador
    "SIN_REGISTRO",      # ni habla ni promociones: INDISTINGUIBLE, ver abajo
)
# Lo unico que SI se persiste: la falla que el sistema no puede ver solo.
# `ASR_DEGRADADO` esta aca y no en la derivacion porque **no existe confianza de
# ASR en ninguna capa del kit** — ni `Utterance` la tiene, ni Whisper la entrega
# por este camino. Derivarla del texto seria fabricar el numero plausible y
# falso que la regla 3 prohibe. La declara quien corrio el pipeline.
CAPTURE_FAILURES = ("ASR_DEGRADADO", "AUDIO_INUTILIZABLE", "PIPELINE_FALLO")


@dataclass(frozen=True)
class MeetingProfile:
    """Lo que una clase de reunion cambia. Tabla congelada, no entidad.

    `promotion_budget` solo puede BAJAR el techo de 7, nunca subirlo ni
    suspenderlo. El documento de huecos pide para INCIDENTE "presupuesto
    suspendido", que es la regla dura 7 de frente. Se resuelve al reves: un
    incidente que produce mas de siete DECISIONES fueron dos incidentes, o —lo
    habitual— lo que produjo fueron compromisos, que no tienen techo. Suspender
    el techo para el perfil donde mas presion hay es como el techo se muere en
    todos los demas.
    """

    clase: str
    promotion_budget: int
    gate_agenda: bool = True
    recording_allowed: bool = True
    nota: str = ""

    @property
    def es_serie_de_decision(self) -> bool:
        """Si esta clase aporta a las metricas de control.

        Se DERIVA del techo, no se declara. Un campo aparte
        (`cuenta_minutos_circulares`, que el diseno original proponia) se
        desincroniza del techo el primer dia y significa exactamente lo mismo.
        """
        return self.promotion_budget > 0


PROFILES = {
    p.clase: p
    for p in (
        MeetingProfile("COMITE", 7),
        MeetingProfile(
            "UNO_A_UNO", 7, recording_allowed=False,
            nota="nunca se graba: contenido sensible sobre terceros que no consintieron",
        ),
        MeetingProfile("KICKOFF", 7, nota="densidad maxima de supuestos y definiciones"),
        MeetingProfile(
            "TERRENO", 7, gate_agenda=False,
            nota="sin sala, sin agenda: el gate no aplica porque no hay que gatear",
        ),
        MeetingProfile(
            "HANDOVER", 0, gate_agenda=False,
            nota="cambio de turno: cero decisiones, mucho compromiso. Fuera del corpus de control",
        ),
        MeetingProfile(
            "INCIDENTE", 7, gate_agenda=False,
            nota="el gate se desactiva; el techo NO. Mas de 7 decisiones fueron dos incidentes",
        ),
    )
}


def profile_of(clase: str) -> MeetingProfile:
    if clase not in PROFILES:
        raise ValueError(f"clase de reunion desconocida: {clase!r}. Validas: {MEETING_CLASS}")
    return PROFILES[clase]


def _check_profile_ceilings() -> None:
    """Corre al importar. La regla 7 no se afloja por un default nuevo."""
    malos = [p.clase for p in PROFILES.values() if p.promotion_budget > 7]
    if malos:
        raise RuntimeError(
            f"perfiles con techo mayor a 7: {malos}. El presupuesto de decisiones por "
            "reunion es una regla dura del kit y un perfil no puede levantarlo. "
            "Va a haber presion permanente para hacerlo: no."
        )


_check_profile_ceilings()


# Una decision muerta ya no gobierna nada; lo que cuelga de ella es trabajo
# contra algo que no rige.
DEAD_DECISION_STATUS = ("REVERTIDA", "SUPERADA")
# Un compromiso "vivo" es el que todavia le pide algo a alguien. CUMPLIDO y
# CANCELADO no: ahi ya no hay nadie ejecutando.
LIVE_COMMITMENT_STATUS = ("ABIERTO", "VENCIDO", "ZOMBI")


def es_zombi(commitment, parent) -> bool:
    """Gente ejecutando algo que ya se revirtio. La definicion, una sola vez.

    Estaba escrita dos veces con alcances distintos: `tick` solo promovia desde
    ABIERTO y `metrics.orphans_and_zombies` contaba tambien los VENCIDO. Un
    compromiso que vencio **antes** de que su decision fuera superada se quedaba
    VENCIDO para siempre en el registro mientras el tablero lo reportaba zombi.
    Dos numeros para la misma pregunta es como el registro deja de creerse.

    `parent` es la decision de la que cuelga, o None si no existe.
    """
    return (
        parent is not None
        and parent.status in DEAD_DECISION_STATUS
        and commitment.status in LIVE_COMMITMENT_STATUS
    )


# El historial de una decision es la unica fuente de la fecha en que cambio de
# estado, y `eventlog` lo lee con esta expresion. El formato es un CONTRATO
# entre quien escribe y quien lee, y por eso los dos viven aca: estaban en
# archivos distintos, sostenidos por una convencion, y la convencion se rompio.
# `supersede` escribia "SUPERADA por D-002: motivo" —con el ID entre el estado y
# los dos puntos— y ninguna supersesion entraba al log. No fallaba: el log
# salia corto y perfectamente creible.
HIST_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+([A-Z_]+):")


def hist_line(stamp: str, estado: str, detalle: str) -> str:
    """La unica forma de escribir una linea de historial visible al event log.

    El estado va pegado a los dos puntos. Todo lo demas —IDs, motivos, el
    statement anterior— va DESPUES, porque es texto para humanos y el lector no
    lo mira. Una linea en minusculas es deliberadamente invisible: sirve para
    anotar sin generar un evento de ciclo de vida.
    """
    if not HIST_RE.match(f"{stamp} {estado}:"):
        raise ValueError(
            f"linea de historial invalida: estado={estado!r} sello={stamp!r}. "
            "El estado va en MAYUSCULAS sin espacios y el sello en YYYY-MM-DD; "
            "el detalle va despues de los dos puntos."
        )
    return f"{stamp} {estado}: {detalle}"

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
from ..gemba import normalize as _norm


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
    # Default REUNION porque es lo que era todo el corpus antes de que el campo
    # existiera. Lo que SI cambia de significado para lo ya persistido es
    # `auditable`, y esta anunciado en el docstring de abajo.
    origen: str = "REUNION"
    # Con quien esta en conflicto. Puntero, no lista: un conflicto es entre DOS
    # enunciados; tres en disputa son dos conflictos y hay que verlos por
    # separado, porque resolver uno cambia el otro.
    en_conflicto_con: str = ""

    @property
    def auditable(self) -> bool:
        """Si esta decision salio de una sesion con roster, fecha y consentimiento.

        Exige `meeting_id` ademas del origen, y esa es la parte que no era
        obvia: `decide add` sin `--meeting` es una ruta legitima y documentada
        —la decision de pasillo— pero por ahi no hay roster (`roster_of`
        devuelve None), no hay consentimiento, y el techo de 7 **ni se evalua**,
        porque `add_decision` lo envuelve en `if decision.meeting_id:`. Medido:
        doce llamadas con `meeting_id=""` y dueno fuera de todo roster se
        escriben las doce, y `volume_gate` las cuenta las doce.

        **Migracion:** una decision de pasillo ya persistida pasa a NO contar
        para la compuerta. Es lo correcto y baja el numero: hay que decirlo, no
        dejarlo pasar. `Corpus.nota()` lo publica.
        """
        return self.origen == "REUNION" and bool(self.meeting_id)

    def validate(self, roster: tuple[str, ...] | None = None) -> list[str]:
        issues: list[str] = []
        if self.origen not in DECISION_ORIGIN:
            issues.append(f"origen desconocido: {self.origen!r}. Validos: {DECISION_ORIGIN}")

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
    # ---- decision por inaccion (H5) ----------------------------------------
    # La mas frecuente en operaciones y la mas invisible: nadie decide, el status
    # quo sigue, y no queda objeto. Cuelga de `OpenQuestion` y no de una octava
    # entidad porque el docstring de esta clase ya dice lo que hace falta — "un
    # simbolo no resuelto: build rojo" — y una no-decision es exactamente eso,
    # con la diferencia de que ya se sabe que no se va a resolver sola.
    #
    # IDs de las reuniones en cuya agenda estuvo y que cerraron sin resolverla.
    # Se CUENTA, no se deriva de `status`: "segunda vez" es respecto de sesiones
    # distintas, y `EXPIRADA` solo dice que paso la fecha una vez.
    aplazada_en: list[str] = field(default_factory=list)
    costo_de_no_decidir: str = ""
    # La valvula de la regla 1: si el costo no se puede cuantificar, se dice
    # QUIEN lo va a averiguar y para cuando. Inventar un numero seria peor que
    # el hueco, y dejar el hueco callado seria peor que las dos cosas.
    costo_en_cola: str = ""

    @property
    def es_no_decision(self) -> bool:
        """Aplazada en dos sesiones distintas. Ahi deja de ser una pregunta
        pendiente y pasa a ser una decision: la de no decidir."""
        return len(set(self.aplazada_en)) >= 2

    def validate(self, roster: tuple[str, ...] | None = None) -> list[str]:
        issues: list[str] = []
        if self.es_no_decision and not (self.costo_de_no_decidir or self.costo_en_cola):
            issues.append(
                f"aplazada en {len(set(self.aplazada_en))} sesiones sin declarar el costo "
                "de seguir sin decidir. Es lo que convierte el silencio en un objeto: sin "
                "eso vuelve a ser un punto que se arrastra. Si no se puede cuantificar, "
                "`costo_en_cola` dice quien lo averigua y para cuando."
            )
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
    # Default COMITE/SINCRONICO a proposito: es lo que era TODO el corpus antes
    # de que estos campos existieran, asi que un .md ya persistido no cambia de
    # significado al cargarse. Cualquier otro default reinterpretaria el pasado.
    clase: str = "COMITE"
    canal: str = "SINCRONICO"
    # La UNICA parte del estado de captura que se persiste: la falla que el
    # sistema no puede observar solo. Todo lo demas se deriva.
    falla_captura: str = ""

    @property
    def es_serie_de_decision(self) -> bool:
        """Si esta sesion cuenta para las metricas de CONTROL.

        Una ventana de chat no es una reunion, y un cambio de turno con techo
        cero no aporta decisiones. Los dos inflan `volume_gate` —que cuenta
        `len(store.meetings())`— y abren la compuerta de la regla 5 sin una sola
        metrica real detras: quince dailies en tres semanas la satisfacen.

        Ojo con lo que este predicado NO decide: **el tiempo circular.** Gente
        sentada en una sala quema minutos-persona decida o no, asi que
        `circular_minutes` filtra por `canal`, no por esto. Medido: filtrar los
        dailies por aca borraba 2.400 minutos-persona de desperdicio real del
        unico numero en pesos del sistema.
        """
        return self.canal == "SINCRONICO" and profile_of(self.clase).es_serie_de_decision

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
        if self.clase not in MEETING_CLASS:
            issues.append(f"clase de reunion desconocida: {self.clase!r}. Validas: {MEETING_CLASS}")
        if self.canal not in MEETING_CHANNEL:
            issues.append(f"canal desconocido: {self.canal!r}. Validos: {MEETING_CHANNEL}")
        if self.falla_captura and self.falla_captura not in CAPTURE_FAILURES:
            issues.append(
                f"falla de captura desconocida: {self.falla_captura!r}. "
                f"Validas: {CAPTURE_FAILURES}"
            )
        if self.canal == "ASINCRONICO" and self.clase != "COMITE":
            issues.append(
                "una ventana asincronica no tiene clase de reunion: es una ventana de "
                "chat o de correo, no una sesion"
            )
        if (
            self.clase in MEETING_CLASS
            and not profile_of(self.clase).recording_allowed
            and self.consent.recording_allowed
        ):
            issues.append(
                f"la clase {self.clase} no admite grabacion ({profile_of(self.clase).nota}), "
                "y el consentimiento la permite"
            )
        # El facilitador existe para que ALGUIEN diga la frase-marcador en voz
        # alta. Exigirlo donde no hay ritual es pedir un dato inventado: en una
        # ventana de chat el marcador se escribe, y en un gemba walk o un cambio
        # de turno no hay quien facilite. Se deriva de lo que ya esta declarado
        # —canal y perfil— en vez de agregar un campo que se desincroniza.
        requiere_facilitador = (
            self.canal == "SINCRONICO"
            and self.clase in MEETING_CLASS
            and profile_of(self.clase).gate_agenda
        )
        if requiere_facilitador and not self.facilitator:
            issues.append("sin facilitador: nadie va a decir la frase-marcador")
        elif self.facilitator and self.facilitator not in self.roster:
            # Solo si HAY facilitador declarado. Sin este `and`, una ventana de
            # chat —que legitimamente no tiene— salia con "facilitador '' fuera
            # del roster", que es un mensaje sobre un campo que no aplica.
            issues.append(f"facilitador '{self.facilitator}' fuera del roster")
        if len(self.roster) > 9:
            issues.append(
                f"{len(self.roster)} personas: sobre 9 no es una reunion de decision, "
                "es una difusion. Considerar partirla"
            )
        if self.audio_ref and not self.consent.recording_allowed:
            issues.append("hay audio referenciado y el consentimiento no permite grabar")
        return issues
