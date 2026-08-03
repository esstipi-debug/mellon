"""Las consultas de fase 1. Ninguna usa un modelo: son consultas puras.

`agenda()` es la operacion de mayor retorno de todo el sistema, y no porque
arme una agenda mejor: porque puede devolver vacio. Cuando no hay compromisos
vencidos, ni supuestos caidos, ni preguntas con dueno, imprime "proponer
cancelar". Todo lo demas del sistema optimiza una reunion que quizas no debia
existir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .schema import (
    CONFLICT_RESOLUTIONS,
    LIVE_COMMITMENT_STATUS,
    MAX_SLIPS,
    Assumption,
    Commitment,
    Decision,
    OpenQuestion,
    es_zombi,
    hist_line,
    profile_of,
)
from ..gemba import normalize as _norm_txt
from .store import DecideStore, ValidationError

# --------------------------------------------------------------- cobertura


@dataclass(frozen=True)
class Coverage:
    """Honestidad del indice. Acompana a `referencing()` SIEMPRE.

    Serena puede prometer que `find_referencing_symbols` devuelve todo, porque
    abajo tiene un compilador. Nosotros no. Heredar la interfaz de esa promesa
    sin heredar la garantia —y callarlo— es el error mas grave que puede
    cometer este diseno: la gente revierte con confianza fundada en un indice
    mudo.
    """

    explicit_links: int
    resolved_mentions: int = 0
    ambiguous_mentions: int = 0
    unresolved_mentions: int = 0
    phase: int = 1

    @property
    def is_complete(self) -> bool:
        return False  # nunca, y por eso se muestra

    def note(self) -> str:
        if self.phase == 1:
            return (
                "fase 1: el indice contiene SOLO enlaces puestos a mano "
                f"({self.explicit_links}). No hay resolucion automatica de menciones, "
                "asi que una referencia que nadie enlazo no aparece aca. No tratar "
                "este resultado como exhaustivo."
            )
        total = self.resolved_mentions + self.ambiguous_mentions + self.unresolved_mentions
        pct = self.resolved_mentions / total * 100 if total else 0.0
        return (
            f"{self.explicit_links} enlaces manuales + {self.resolved_mentions} menciones "
            f"resueltas de {total} ({pct:.0f}%). {self.ambiguous_mentions} ambiguas, "
            f"{self.unresolved_mentions} sin resolver."
        )


# ----------------------------------------------------------------- agenda


@dataclass
class Agenda:
    meeting_id: str
    meeting_date: date
    roster: tuple[str, ...]
    # Primero de todo: mientras hay un conflicto abierto no se sabe cual
    # decision rige, y cualquier otro punto se discute sobre arena.
    conflicts: list = field(default_factory=list)
    overdue_commitments: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)
    at_risk_decisions: list = field(default_factory=list)
    reopen_requests: list = field(default_factory=list)
    # Preguntas que vencieron sin respuesta. Tienen bloque propio porque son el
    # bucle hecho visible: un tema que se declaro pendiente, se le puso dueno y
    # fecha, y la fecha paso sin que nadie lo resolviera. Si desaparecieran al
    # expirar, el sistema recomendaria cancelar una reunion que justamente
    # tenia algo que resolver — y el bucle seguiria corriendo invisible.
    expired_questions: list = field(default_factory=list)
    gate_rejections: list = field(default_factory=list)
    # Puntos que entraron con el gate apagado por el perfil de la reunion. El
    # perfil relaja el proceso, no la contabilidad: sin este bloque, la agenda
    # de un INCIDENTE seria indistinguible de una donde el gate no rechazo nada.
    gate_bypassed: list = field(default_factory=list)
    advisories: list = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (
            self.conflicts
            or self.overdue_commitments
            or self.open_questions
            or self.at_risk_decisions
            or self.reopen_requests
            or self.expired_questions
        )

    @property
    def verdict(self) -> str:
        return "proponer cancelar" if self.is_empty else "reunion justificada"

    def to_markdown(self) -> str:
        L = [f"# Agenda — {self.meeting_id} ({self.meeting_date.isoformat()})", ""]
        L.append(f"**Veredicto: {self.verdict.upper()}**")
        L.append("")
        if self.is_empty:
            L += [
                "Sin compromisos vencidos, sin supuestos caidos, sin preguntas con dueno",
                "y sin solicitudes de reapertura. **No hay nada que decidir.**",
                "",
                "Si igual hay que juntarse, que sea por algo que no es decidir — y que",
                "dure lo que dura eso.",
                "",
            ]

        if self.conflicts:
            L += [
                "## CONFLICTO ABIERTO — primero esto",
                "",
                "Una decision de fuera de la sala contradice a una vigente. Hasta que se",
                "resuelva, **lo que rige es lo que se decidio en la sala** — pero nadie",
                "puede citar ninguna de las dos como cerrada.",
                "",
                "| pregunta | externa | contra | la resuelve | antes de |",
                "|---|---|---|---|---|",
            ]
            for q, ext in self.conflicts:
                L.append(f"| {q.id} | {ext.id} ({ext.origen}) | {ext.en_conflicto_con} | "
                         f"{q.resolver} | {q.resolve_by.isoformat()} |")
            L.append("")

        if self.overdue_commitments:
            L += ["## Compromisos vencidos", "", "| id | dueno | que | vencio hace | implementa |", "|---|---|---|---:|---|"]
            for c, late in self.overdue_commitments:
                L.append(f"| {c.id} | {c.owner} | {c.what} | {late} d | {c.decision_id} |")
            L.append("")

        if self.at_risk_decisions:
            L += ["## Decisiones en riesgo por supuesto caido", "", "| decision | supuesto | vencio | fuente |", "|---|---|---|---|"]
            for d, a in self.at_risk_decisions:
                L.append(f"| {d.id} — {d.statement} | {a.id} {a.statement} | {a.check_by.isoformat()} | {a.source} |")
            L.append("")

        if self.open_questions:
            L += ["## Preguntas abiertas que pasan el gate", "", "| id | pregunta | la resuelve | antes de | bloquea |", "|---|---|---|---|---|"]
            for q in self.open_questions:
                L.append(f"| {q.id} | {q.question} | {q.resolver} | {q.resolve_by.isoformat()} | {', '.join(q.blocks) or '-'} |")
            L.append("")

        if self.expired_questions:
            L += [
                "## Preguntas que vencieron sin respuesta",
                "",
                "Se declararon pendientes, se les puso dueno y fecha, y la fecha paso.",
                "Cada fila de aca es una vuelta del bucle que el registro existe para cortar.",
                "",
                "| id | pregunta | la debia | vencio hace |",
                "|---|---|---|---:|",
            ]
            for q, dias in self.expired_questions:
                L.append(f"| {q.id} | {q.question} | {q.resolver} | {dias} d |")
            L.append("")

        if self.reopen_requests:
            L += ["## Solicitudes de reapertura", "", "| id | reabre | dato nuevo | pide |", "|---|---|---|---|"]
            for q in self.reopen_requests:
                L.append(f"| {q.id} | {q.reopen_of} | {q.new_evidence} | {q.resolver} |")
            L.append("")

        if self.gate_rejections:
            L += [
                "## No entran a la agenda (gate)",
                "",
                "El gate es la unica operacion que ataca la causa y no el efecto: si falta",
                "el dato que bloquea, no se agenda el tema — se agenda obtener el dato.",
                "",
                "| id | motivo | accion |",
                "|---|---|---|",
            ]
            for r in self.gate_rejections:
                L.append(f"| {r['id']} | {r['reason']} | {r['action']} |")
            L.append("")

        if self.gate_bypassed:
            L += [
                "## Entraron con el gate APAGADO",
                "",
                "El perfil de esta reunion desactiva el gate. Estos puntos no cumplen las",
                "tres condiciones y entran igual — se listan porque relajar el proceso no",
                "es lo mismo que dejar de contar.",
                "",
                "| id | que le falta |",
                "|---|---|",
            ]
            for r in self.gate_bypassed:
                L.append(f"| {r['id']} | {r['reason']} |")
            L.append("")

        if self.advisories:
            L += ["## Avisos", ""] + [f"- {a}" for a in self.advisories] + [""]
        return "\n".join(L)


def _blocked_on(q: OpenQuestion, questions: list[OpenQuestion]) -> list[str]:
    """Preguntas que tienen que resolverse antes que esta. Se deriva de `blocks`
    en vez de duplicar el dato en los dos sentidos: dos campos que dicen lo
    mismo se desincronizan."""
    return [o.id for o in questions if q.id in o.blocks and o.status == "ABIERTA"]


def _gate(q: OpenQuestion, roster: tuple[str, ...], questions: list[OpenQuestion]) -> tuple[bool, str, str]:
    """Las tres condiciones. Devuelve (pasa, motivo, accion_sugerida)."""
    if q.resolver not in roster:
        return (
            False,
            f"su resolver ('{q.resolver or 'nadie'}') no esta en el roster",
            "invitarlo o reasignar la pregunta a alguien que si este",
        )
    ok, why_not = q.closable
    if not ok:
        return False, why_not, "reformular como pregunta cerrable (si/no o elegir una opcion)"
    blockers = _blocked_on(q, questions)
    if blockers:
        return (
            False,
            f"bloqueada por {', '.join(blockers)}",
            f"agendar la obtencion del dato: {blockers[0]}, con dueno y fecha",
        )
    return True, "", ""


def agenda(store: DecideStore, meeting_id: str, today: date | None = None) -> Agenda:
    """Consulta pura sobre el estado del registro. Sin IA."""
    meeting = store.get_meeting(meeting_id)
    today = today or meeting.date
    roster = meeting.roster

    decisions = {d.id: d for d in store.decisions()}
    commitments = store.commitments()
    assumptions = store.assumptions()
    questions = store.questions()

    perfil = profile_of(meeting.clase)
    ag = Agenda(meeting_id=meeting_id, meeting_date=meeting.date, roster=roster)

    ag.overdue_commitments = sorted(
        [
            (c, c.days_late(today))
            for c in commitments
            if c.status in LIVE_COMMITMENT_STATUS and c.due < today
        ],
        key=lambda t: -t[1],
    )

    for a in assumptions:
        if not a.pone_en_riesgo:
            continue
        d = decisions.get(a.decision_id)
        if d and d.status in ("VIGENTE", "EN_RIESGO"):
            ag.at_risk_decisions.append((d, a))

    en_conflicto = {d.id: d for d in decisions.values() if d.status == "EN_CONFLICTO"}
    for q in questions:
        if q.status == "ABIERTA" and any(b in en_conflicto for b in q.blocks):
            ext = next(en_conflicto[b] for b in q.blocks if b in en_conflicto)
            ag.conflicts.append((q, ext))
            continue
        if q.status == "EXPIRADA":
            ag.expired_questions.append((q, (today - q.resolve_by).days))
            continue
        if q.status != "ABIERTA":
            continue
        if q.reopen_of:
            ag.reopen_requests.append(q)
            continue
        passes, reason, action = _gate(q, roster, questions)
        if passes or not perfil.gate_agenda:
            ag.open_questions.append(q)
            if not passes:
                # Entro con el gate apagado. Se anota: una agenda de INCIDENTE
                # identica a una donde el gate no rechazo nada es la regla 3
                # rota — el perfil relaja el proceso, no la contabilidad.
                ag.gate_bypassed.append({"id": q.id, "reason": reason, "action": action})
        else:
            ag.gate_rejections.append({"id": q.id, "reason": reason, "action": action})

    for a in assumptions:
        ag.advisories.extend(a.advisories())
    if not perfil.gate_agenda:
        ag.advisories.append(
            f"gate de agenda DESACTIVADO por la clase {meeting.clase}: {perfil.nota}. "
            f"{len(ag.gate_bypassed)} punto(s) entraron sin cumplir las tres condiciones."
            if ag.gate_bypassed else
            f"gate de agenda desactivado por la clase {meeting.clase}; no hizo falta."
        )
    zombies = [c for c in commitments if c.status == "ZOMBI"]
    if zombies:
        ag.advisories.append(
            f"{len(zombies)} compromiso(s) zombi: {', '.join(c.id for c in zombies)} — "
            "gente ejecutando algo que ya se revirtio"
        )
    return ag


# ----------------------------------------------------- navegacion semantica


def why(store: DecideStore, decision_id: str) -> dict:
    """`find_declaration` extendido: por que se decidio esto.

    En fase 1 devuelve el rationale tipeado y los supuestos con su estado. La
    cita literal del audio con `mm:ss` llega en fase 3 — hasta entonces
    `cita` es None y se dice, no se finge.
    """
    d = store.get(decision_id)
    sup = [a for a in store.assumptions() if a.decision_id == decision_id]
    return {
        "id": d.id,
        "statement": d.statement,
        "owner": d.owner,
        "status": d.status,
        "date_decided": d.date_decided.isoformat(),
        "criteria": d.criteria,
        "rationale": d.rationale,
        "meeting_id": d.meeting_id,
        "assumptions": [
            {"id": a.id, "statement": a.statement, "status": a.status,
             "check_by": a.check_by.isoformat(), "source": a.source}
            for a in sup
        ],
        # Si esta superada, decirlo y decir cual rige. Es la friccion que nombra
        # el diseno: "las dos personas citando versiones distintas".
        "superseded_by": d.superseded_by or None,
        "vigente_hoy": (
            None if not d.superseded_by else head_of(store, decision_id).get("head")
        ),
        "cita": None if d.anchor.empty else d.anchor.cita_congelada,
        "cita_formateada": _cita(d),
        "minuto": None if d.anchor.empty else _mmss(d.anchor.t_start),
        "fuente": _estado_fuente(store, d),
        # La procedencia, en la cara del que consulta. Sin esto, una sembrada
        # devolvia exactamente el mismo objeto que una decidida en una reunion
        # real, con una nota que afirma que "se registro sin canal HABLADA" — lo
        # que hace concluir que existio una sesion donde eso se decidio. Para
        # una decision declarada de memoria en el kickoff, eso es falso.
        "origen": d.origen,
        "auditable": d.auditable,
        "nota_origen": _nota_origen(d),
        # Lo que hay que decir sin impedir. Hoy: el numero del criterio que no
        # aparece en la cita. Un aviso que no se muestra en ningun lado es un
        # campo muerto, y `why()` es la superficie que mira el que va a citar
        # esta decision en una reunion.
        "advertencias": d.advisories(),
        "nota_cita": (
            "sin cita: la decision se registro sin canal HABLADA (a mano o desde texto "
            "sin timestamps)"
            if d.anchor.empty and d.auditable
            else ""
        ),
    }


# Que significa cada origen para el que consulta. El texto es la superficie: un
# campo validado que nadie lee no protege de nada.
_NOTAS_ORIGEN = {
    "SIEMBRA": (
        "declarada de memoria en la sesion de siembra: NO salio de una reunion "
        "registrada por el sistema y no es auditable. La fecha es aproximada"
    ),
    "ACTA_HISTORICA": (
        "rescatada de un acta anterior al sistema: hay texto de origen, pero no hay "
        "roster ni consentimiento detras y no es auditable"
    ),
    "CHAT": (
        "salio de una ventana de chat, no de una sesion: sin roster y sin ritual de "
        "cierre, y por lo tanto no es auditable"
    ),
    "PASILLO": (
        "registrada sin reunion: no hay roster contra el cual validar al dueno, y por "
        "lo tanto no es auditable"
    ),
}


def _nota_origen(d) -> str:
    if d.auditable:
        return ""
    return _NOTAS_ORIGEN.get(
        d.origen, f"origen {d.origen}: no es auditable"
    ) if d.origen != "REUNION" else (
        "registrada sin reunion: no hay roster contra el cual validar al dueno, y por "
        "lo tanto no es auditable"
    )


def _cita(d) -> str:
    from .anchor import cite

    return cite(d.anchor)


def _mmss(t):
    from .transcript import mmss

    return mmss(t)


def _estado_fuente(store: DecideStore, d) -> str:
    """Si la fuente sigue viva, si cambio, o si caduco por retencion.

    En los tres casos la cita sirve —esa es la gracia de haberla copiado— pero
    conviene saber en cual estamos antes de usarla como evidencia."""
    if d.anchor.empty:
        return "sin ancla"
    from .anchor import verify
    from .transcript import TranscriptStore

    ok, motivo = verify(d.anchor, TranscriptStore(store.root, d.anchor.meeting_id))
    return "intacta" if ok else motivo


def implementations(store: DecideStore, decision_id: str) -> list[Commitment]:
    """`find_implementations`. Relacion 1:N real, no una metafora."""
    return [c for c in store.commitments() if c.decision_id == decision_id]


def referencing(store: DecideStore, decision_id: str, depth: int = 1) -> dict:
    """`find_referencing_symbols`: todo lo que cuelga de una decision.

    Devuelve SIEMPRE `Coverage`, nunca un numero desnudo.
    """
    store.get(decision_id)  # falla si no existe
    decisions = store.decisions()
    questions = store.questions()

    depends = [d for d in decisions if decision_id in d.depends_on]
    supersedes = [d for d in decisions if decision_id in d.supersedes]
    commits = [
        c for c in implementations(store, decision_id)
        if c.status in LIVE_COMMITMENT_STATUS
    ]
    sup = [a for a in store.assumptions() if a.decision_id == decision_id and a.status != "VERIFICADO"]
    blocked = [q for q in questions if decision_id in q.blocks and q.status == "ABIERTA"]
    reopen = [q for q in questions if q.reopen_of == decision_id and q.status == "ABIERTA"]

    seen = {d.id for d in depends}
    if depth > 1:
        frontier = list(depends)
        for _ in range(depth - 1):
            nxt = []
            for d in frontier:
                for e in decisions:
                    if d.id in e.depends_on and e.id not in seen:
                        seen.add(e.id)
                        nxt.append(e)
            depends.extend(nxt)
            frontier = nxt

    explicit = len(depends) + len(supersedes) + len(commits) + len(sup) + len(blocked) + len(reopen)
    cov = _coverage(store, explicit)
    return {
        "id": decision_id,
        "depends_on_this": [{"id": d.id, "statement": d.statement, "status": d.status} for d in depends],
        "supersedes_this": [{"id": d.id, "statement": d.statement} for d in supersedes],
        "open_commitments": [
            {"id": c.id, "what": c.what, "owner": c.owner, "due": c.due.isoformat(), "status": c.status}
            for c in commits
        ],
        "live_assumptions": [
            {"id": a.id, "statement": a.statement, "status": a.status, "check_by": a.check_by.isoformat()}
            for a in sup
        ],
        "blocked_questions": [{"id": q.id, "question": q.question} for q in blocked],
        "reopen_requests": [{"id": q.id, "new_evidence": q.new_evidence} for q in reopen],
        "total_referencias": explicit,
        "coverage": cov.note(),
        "coverage_completa": cov.is_complete,
    }


def _coverage(store: DecideStore, explicit: int) -> Coverage:
    """Cobertura real del indice, no una constante.

    Tenia la fase clavada en 1, asi que `refs` seguia diciendo "no hay
    resolucion automatica de menciones" aunque el resolutor existiera y llevara
    menciones confirmadas. El modulo cuya doctrina es *no mentir nunca en
    silencio* estaba subreportando su propia cobertura — que es la misma falla,
    en la direccion opuesta.
    """
    from .resolve import AliasStore

    astore = AliasStore(store.root)
    if not astore.mention_path.exists():
        return Coverage(explicit_links=explicit, phase=1)

    ms = [m for m in astore.mentions() if m.get("estado") != "REVERTIDA"]
    resueltas = sum(1 for m in ms if m.get("tier") == "EXTRACTED")
    ambiguas = sum(1 for m in ms if m.get("tier") == "AMBIGUOUS")
    return Coverage(
        explicit_links=explicit,
        resolved_mentions=resueltas,
        ambiguous_mentions=ambiguas,
        unresolved_mentions=len(ms) - resueltas - ambiguas,
        phase=3,
    )


def head_of(store: DecideStore, decision_id: str, max_saltos: int = 50) -> dict:
    """Sigue la cadena de `superseded_by` hasta la decision que rige hoy.

    Es lo que ataca la friccion que nombra el diseno: "las dos personas citando
    versiones distintas". Con la cadena escrita, cual esta vigente deja de ser
    una discusion y pasa a ser una consulta.
    """
    cadena = [decision_id]
    actual = store.get(decision_id)
    vistos = {decision_id}
    for _ in range(max_saltos):
        if not actual.superseded_by:
            break
        if actual.superseded_by in vistos:
            return {
                "id": decision_id,
                "head": None,
                "cadena": cadena,
                "error": f"ciclo de supersesion detectado en {actual.superseded_by}",
            }
        vistos.add(actual.superseded_by)
        cadena.append(actual.superseded_by)
        actual = store.get(actual.superseded_by)
    return {
        "id": decision_id,
        "head": actual.id,
        "vigente": actual.id != decision_id,
        "cadena": cadena,
        "saltos": len(cadena) - 1,
        "statement_vigente": actual.statement,
        "status_vigente": actual.status,
    }


class ConflictoAbierto(ValueError):
    """Se intento superar una decision que esta en conflicto sin resolverlo."""


def declare_conflict(
    store: DecideStore,
    externa_id: str,
    vigente_id: str,
    reason: str = "",
    resolver: str = "",
    resolve_by: date | None = None,
    today: date | None = None,
    apply: bool = False,
) -> dict:
    """Una decision de fuera de la sala contradice a una VIGENTE.

    Es la regla de precedencia del diseno, y su punto entero: **la evidencia mas
    reciente NO gana sola**. Sin esto, el canal asincronico corrompe el canal
    decidido en vez de alimentarlo — un mensaje de WhatsApp a las 22:00 daria
    vuelta una decision de comite sin que nadie la mire.

    Lo declara una PERSONA. Detectarlo en automatico por solapamiento de slots
    seria un heuristico decidiendo que dos enunciados se contradicen, y la regla
    3 lo prohibe: empate = AMBIGUOUS reportado, jamas una eleccion. Pero lo que
    si se hace es que declararlo sea barato y que el resultado no quede en
    limbo: el resolver sale del REGISTRO —es el dueno de la decision
    disputada— y la fecha limite es obligatoria.

    `EN_CONFLICTO` es **suspension, no muerte**. Los compromisos que cuelgan de
    la decision de sala NO se tocan: se enumeran para triage, misma doctrina que
    `supersede`. Cancelarlos seria decidir el conflicto a favor de la externa
    por la puerta de atras.
    """
    externa, vigente = store.get(externa_id), store.get(vigente_id)
    triage = [
        {"tipo": "compromiso", "id": c.id, "dueno": c.owner, "que": c.what,
         "accion": "sigue corriendo: el conflicto suspende la decision, no la mata. "
                   "Si el trabajo debe parar, es una decision aparte y se escribe."}
        for c in implementations(store, vigente_id)
        if c.status in LIVE_COMMITMENT_STATUS
    ]
    out = {
        "externa": externa_id, "vigente": vigente_id,
        "triage": triage, "referencias_a_resolver": len(triage), "applied": False,
    }
    if not apply:
        out["nota"] = (
            "no se toco nada. Con --apply, la externa queda EN_CONFLICTO y se abre "
            "una pregunta que bloquea a la vigente y entra primera en la agenda."
        )
        return out

    if not reason:
        raise ValueError(
            "declarar un conflicto exige un motivo: es lo que va a leer quien lo "
            "resuelva, y sin eso la discusion arranca de cero"
        )
    if vigente.status == "EN_CONFLICTO" or externa.status == "EN_CONFLICTO":
        raise ConflictoAbierto(
            f"ya hay un conflicto abierto sobre {vigente_id if vigente.status == 'EN_CONFLICTO' else externa_id}. "
            "Un conflicto es entre DOS enunciados; tres en disputa son dos conflictos y "
            "hay que verlos por separado, porque resolver uno cambia el otro."
        )

    stamp = (today or externa.date_decided).isoformat()
    # El resolver sale del registro: es el dueno de lo que se esta
    # contradiciendo, el unico actor que el sistema puede nombrar sin inventar.
    quien = resolver or vigente.owner
    q = OpenQuestion(
        id="", question=f"cual rige: {vigente_id} (sala) o {externa_id} ({externa.origen})?",
        resolver=quien,
        resolve_by=resolve_by or (today or externa.date_decided),
        blocks=[vigente_id, externa_id],
        meeting_id=externa.meeting_id,
        new_evidence=reason,
    )
    store.add_question(q, force=True)

    externa.status = "EN_CONFLICTO"
    externa.en_conflicto_con = vigente_id
    externa.historial_statements.append(
        hist_line(stamp, "EN_CONFLICTO", f"contradice a {vigente_id}: {reason}"))
    store.save(externa)

    out.update({
        "applied": True, "question": q.id, "resolver": quien,
        "nota": (
            f"{externa_id} quedo EN_CONFLICTO con {vigente_id}. {vigente_id} sigue "
            f"VIGENTE: hasta que alguien resuelva, lo que rige es lo que se decidio en "
            f"la sala. Las {len(triage)} referencia(s) de arriba siguen corriendo."
        ),
    })
    return out


def resolve_conflicto(
    store: DecideStore,
    question_id: str,
    resolucion: str,
    reason: str = "",
    resuelto_por: str = "",
    today: date | None = None,
    apply: bool = False,
) -> dict:
    """Cierra un conflicto. Tres salidas, las tres humanas.

        GANA_SALA     la externa se REVIERTE. Lo de la sala sigue rigiendo.
        GANA_EXTERNA  la externa supersede a la de sala, por la puerta de
                      adelante: pasa por `supersede`, con su triage.
        COEXISTEN     no habia contradiccion. Suele ser el caso: dos decisiones
                      sobre sitios o turnos distintos que se leyeron como una.

    Ninguna se infiere. `COEXISTEN` existe porque la contradiccion aparente es
    mas frecuente que la real, y sin esa salida la gente resuelve cualquier cosa
    con tal de destrabar.
    """
    if resolucion not in CONFLICT_RESOLUTIONS:
        raise ValueError(f"resolucion invalida: {resolucion!r}. Validas: {CONFLICT_RESOLUTIONS}")
    q = store.get(question_id)
    externas = [store.get(i) for i in q.blocks if store.get(i).status == "EN_CONFLICTO"]
    if not externas:
        raise ValueError(f"{question_id} no bloquea ninguna decision EN_CONFLICTO")
    externa = externas[0]
    vigente_id = externa.en_conflicto_con

    out = {"question": question_id, "resolucion": resolucion, "externa": externa.id,
           "vigente": vigente_id, "applied": False}
    if not apply:
        out["nota"] = "no se toco nada."
        return out
    if not reason:
        raise ValueError("resolver un conflicto exige un motivo: es lo que explica la eleccion")

    stamp = (today or q.resolve_by).isoformat()
    if resolucion == "GANA_EXTERNA":
        # Por la puerta de adelante: primero sale del conflicto, despues se
        # supersede con su triage completo. Cambiar el estado a mano aca seria
        # saltearse la enumeracion de referencias que `supersede` existe para dar.
        externa.status = "VIGENTE"
        externa.en_conflicto_con = ""
        externa.historial_statements.append(
            hist_line(stamp, "VIGENTE", f"conflicto resuelto a su favor: {reason}"))
        store.save(externa)
        out["supersede"] = supersede(store, vigente_id, externa.id, reason=reason,
                                     today=today, apply=True)
    else:
        externa.status = "REVERTIDA" if resolucion == "GANA_SALA" else "VIGENTE"
        externa.en_conflicto_con = ""
        externa.historial_statements.append(hist_line(
            stamp, externa.status,
            f"conflicto con {vigente_id} resuelto como {resolucion}: {reason}"))
        store.save(externa)

    q.status = "RESUELTA"
    q.answer_ref = f"{resolucion} por {resuelto_por or q.resolver}: {reason}"
    store.save(q)
    out.update({"applied": True, "estado_externa": externa.status})
    return out


def supersede(
    store: DecideStore,
    old_id: str,
    new_id: str,
    reason: str = "",
    today: date | None = None,
    apply: bool = False,
) -> dict:
    """`rename`. Marca SUPERADA, escribe punteros en ambos sentidos, y **lista
    las referencias que ahora apuntan a una decision superada** para que se
    resuelvan explicitamente.

    No borra nada. **No propaga.** Y esa es la parte importante: en codigo,
    renombrar arregla las referencias; aca, cambiar el alcance de una decision
    **no arregla los compromisos, los invalida**. Lo maximo honesto es
    enumerarlos y forzar triage humano. Prometer propagacion automatica se
    descubre la primera vez que se usa y quema la confianza en todo el sistema.

    Tampoco escribe un alias con el statement viejo: fabricaria colisiones a
    proposito. El statement viejo queda en `historial_statements`, que es
    consultable pero **no es indice de resolucion**.

    Sin `apply` es solo el reporte de triage y no toca nada.
    """
    if old_id == new_id:
        raise ValueError("una decision no se puede superar a si misma")

    vieja, nueva = store.get(old_id), store.get(new_id)

    if nueva.status in ("SUPERADA", "REVERTIDA"):
        raise ValueError(
            f"{new_id} esta {nueva.status}: no puede reemplazar a nadie. "
            "Superar con una decision muerta deja la cadena apuntando a la nada."
        )
    if vieja.status == "SUPERADA":
        h = head_of(store, old_id)
        raise ValueError(
            f"{old_id} ya fue superada por {vieja.superseded_by}. La que rige hoy es "
            f"{h.get('head')}: superar esa, no una version vieja de la cadena."
        )
    cadena_nueva = head_of(store, new_id)
    if old_id in cadena_nueva.get("cadena", []):
        raise ValueError(
            f"ciclo: {new_id} ya cuelga de {old_id} ({' -> '.join(cadena_nueva['cadena'])})"
        )

    ref = referencing(store, old_id)
    triage: list[dict] = []

    for c in ref["open_commitments"]:
        triage.append({
            "tipo": "compromiso", "id": c["id"], "que": f"{c['owner']}: {c['what']}",
            "accion": (
                f"reasignar a {new_id} o cancelar. Cambiar el alcance de la decision "
                "NO arregla el compromiso: lo invalida"
            ),
        })
    for a in ref["live_assumptions"]:
        triage.append({
            "tipo": "supuesto", "id": a["id"], "que": a["statement"],
            "accion": f"re-colgar de {new_id} si sigue sosteniendola, o marcarlo VIOLADO",
        })
    for d in ref["depends_on_this"]:
        triage.append({
            "tipo": "decision_dependiente", "id": d["id"], "que": d["statement"],
            "accion": f"revisar si su premisa sigue en pie con {new_id}",
        })
    for q in ref["blocked_questions"]:
        triage.append({
            "tipo": "pregunta", "id": q["id"], "que": q["question"],
            "accion": f"re-apuntar a {new_id} o cerrarla",
        })

    from .resolve import AliasStore

    astore = AliasStore(store.root)
    aliases = [
        a.surface_norm
        for a in astore.load()
        if a.symbol_id == old_id and a.estado == "VIGENTE"
    ]
    for surface in aliases:
        triage.append({
            "tipo": "alias", "id": surface, "que": f"'{surface}' -> {old_id}",
            "accion": (
                "decidir a mano si sigue significando la decision vieja (caso normal: "
                f"si) o si hay que cerrar su vigencia y confirmarlo contra {new_id}"
            ),
        })

    out = {
        "old": old_id,
        "new": new_id,
        "applied": False,
        "referencias_a_resolver": len(triage),
        "triage": triage,
        "nota_no_propaga": (
            "supersede no reasigna nada. En codigo renombrar arregla las referencias; "
            "aca cambiar el alcance las invalida, y lo unico honesto es enumerarlas."
        ),
    }

    if not apply:
        out["nota"] = "reporte de triage: no se toco nada. Usar --apply para escribir."
        return out

    if not reason:
        raise ValueError(
            "superar exige un motivo: una decision que cambia de estado sin motivo "
            "escrito no se puede explicar seis semanas despues"
        )
    # Un conflicto abierto es precisamente "no se sabe cual rige". Superar una
    # de las dos mientras eso esta abierto decide el conflicto de costado, sin
    # que nadie lo haya resuelto ni quede escrito por que.
    for d, papel in ((vieja, old_id), (nueva, new_id)):
        if d.status == "EN_CONFLICTO":
            raise ConflictoAbierto(
                f"{papel} esta EN_CONFLICTO con {d.en_conflicto_con}. Resolver el "
                "conflicto primero (`resolve_conflicto`): superar mientras esta abierto "
                "lo decide de costado y sin dejar escrito por que."
            )

    stamp = (today or nueva.date_decided).isoformat()
    vieja.status = "SUPERADA"
    vieja.superseded_by = new_id
    vieja.version += 1
    # El statement viejo queda aca, consultable, y NO como alias: un alias con
    # el statement de la decision superada fabricaria colisiones a proposito.
    #
    # El ID de la nueva va DESPUES de los dos puntos. Ponerlo entre el estado y
    # los dos puntos —como estaba— hacia que `eventlog` no reconociera la linea
    # y que ninguna supersesion apareciera en el log de ciclo de vida.
    vieja.historial_statements.append(hist_line(stamp, "SUPERADA", f"por {new_id} - {reason}"))
    # En minusculas a proposito: es una anotacion para humanos, no un evento.
    vieja.historial_statements.append(f"{stamp} statement al momento de superar: {vieja.statement}")
    store.save(vieja)

    if old_id not in nueva.supersedes:
        nueva.supersedes.append(old_id)
    nueva.historial_statements.append(f"{stamp} supera a {old_id}: {reason}")
    store.save(nueva)

    out["applied"] = True
    out["nota"] = (
        f"{old_id} quedo SUPERADA por {new_id}. Las {len(triage)} referencia(s) de arriba "
        "siguen apuntando a la vieja: resolverlas a mano. `tick()` va a marcar ZOMBI a los "
        "compromisos abiertos que queden colgando."
    )
    return out


def safe_close(
    store: DecideStore,
    decision_id: str,
    apply: bool = False,
    reason: str = "",
    today: date | None = None,
) -> dict:
    """`safe_delete`. Cierra solo si nada cuelga. Si algo cuelga, FALLA y lo lista.

    El cierre administrativo de decisiones que en la practica siguen abiertas es
    el momento exacto en que el registro empieza a mentir y la gente deja de
    consultarlo.

    Sin `apply` es solo el guardia: responde "¿se puede retirar?" y no toca nada.
    Con `apply` marca REVERTIDA y **exige un motivo**, que queda en el historial.
    Una decision que cambia de estado sin motivo escrito es una decision que
    dentro de seis semanas nadie va a poder explicar — que es exactamente el
    problema que el registro existe para resolver.
    """
    d = store.get(decision_id)
    blockers: list[str] = []

    for c in implementations(store, decision_id):
        if c.status in LIVE_COMMITMENT_STATUS:
            blockers.append(f"{c.id} compromiso {c.status.lower()} de {c.owner} ({c.what})")
    for a in store.assumptions():
        if a.decision_id == decision_id and a.status in ("VIGENTE", "VENCIDO"):
            blockers.append(f"{a.id} supuesto {a.status.lower()} sin verificar ({a.statement})")
    for q in store.questions():
        if q.status == "ABIERTA" and decision_id in q.blocks:
            blockers.append(f"{q.id} pregunta abierta que depende de esta ({q.question})")

    if blockers:
        return {
            "id": decision_id,
            "closed": False,
            "blockers": blockers,
            "reason": (
                f"{decision_id} no se puede cerrar: {len(blockers)} cosa(s) todavia cuelgan. "
                "Cerrarla igual seria el momento en que el registro empieza a mentir."
            ),
        }

    if apply:
        if not reason:
            raise ValueError(
                "cerrar con --apply exige un motivo: una decision que cambia de estado "
                "sin motivo escrito no se puede explicar seis semanas despues"
            )
        stamp = (today or d.date_decided).isoformat()
        d.historial_statements.append(hist_line(stamp, "REVERTIDA", reason))
        d.status = "REVERTIDA"
        d.version += 1
        store.save(d)

    return {
        "id": decision_id,
        "closed": True,
        "applied": bool(apply),
        "status": d.status,
        "blockers": [],
        "reason": "sin dependencias vivas",
    }


# ------------------------------------------------------------------- tick


def slip(
    store: DecideStore,
    commitment_id: str,
    nueva_fecha: date,
    motivo: str,
    por: str,
    today: date,
) -> dict:
    """Correr la fecha de un compromiso, en el registro y no por chat.

    El hueco que cierra es el mas letal de todos y no es tecnico: dueno y
    solicitante acuerdan una fecha nueva por fuera, el tablero sigue mostrando
    VENCIDO, y a la tercera vez el dueno concluye que el registro esta mal y
    deja de mirarlo. Desde ahi el tablero de vencidos es ruido que todos
    ignoran, **sin ninguna senal tecnica de que eso paso**.

    Por eso esta operacion es deliberadamente barata —una linea, sin aprobacion
    previa, desde el telefono— y por eso NO se puede rechazar la cuarta corrida:
    renegociar tiene que seguir siendo mas barato que incumplir en silencio, o
    la gente elige el silencio. Lo que hace el limite es **abrir la pregunta**,
    que es distinto de cerrar la puerta.

    `today` es argumento (regla 4): decide si la fecha nueva ya paso.
    """
    c = store.get(commitment_id)

    if len(_norm_txt(motivo)) < 8:
        raise ValueError(
            "correr una fecha exige un motivo. Sin el, en seis semanas la unica "
            "lectura posible del historial es 'no se hizo', que es la lectura que "
            "hace que el dueno deje de declarar."
        )
    if c.status not in LIVE_COMMITMENT_STATUS:
        raise ValueError(
            f"{commitment_id} esta {c.status}: no se le corre la fecha a un compromiso "
            "que ya no le pide nada a nadie. Revivirlo por la fecha seria decidir por "
            "la puerta de atras que vuelve a estar abierto."
        )
    if nueva_fecha < today:
        raise ValueError(
            f"la fecha nueva ({nueva_fecha}) esta en el pasado. Eso no es renegociar: "
            "deja el compromiso vencido de nacimiento y con un motivo escrito al lado "
            "que lo hace ver atendido."
        )

    c.slips = list(c.slips) + [{
        "de": c.due.isoformat(),
        "a": nueva_fecha.isoformat(),
        "motivo": motivo,
        "por": por,
        "cuando": today.isoformat(),
    }]
    c.due = nueva_fecha
    # Vuelve a ABIERTO: si renegociar dejara el compromiso en VENCIDO, el
    # tablero seguiria mintiendo y no habriamos cerrado nada. ZOMBI no se toca —
    # ahi el problema no es la fecha, es que la decision de arriba se revirtio.
    if c.status == "VENCIDO":
        c.status = "ABIERTO"
    store.save(c)

    out = {
        "id": commitment_id,
        "applied": True,
        "de": c.slips[-1]["de"],
        "a": c.slips[-1]["a"],
        "corridas_hacia_adelante": c.slips_hacia_adelante,
        "escalado": None,
    }
    if c.es_no_decision:
        out["escalado"] = _escalar_no_decision(store, c, today)
        out["nota"] = (
            f"{commitment_id} lleva {c.slips_hacia_adelante} corridas hacia adelante. "
            "Eso ya no es un atraso: es una decision que no se tomo. La fecha se "
            "corrio igual —el silencio es peor— y quedo abierta la pregunta."
        )
    return out


def _escalar_no_decision(store: DecideStore, c, today: date) -> str:
    """Abre UNA pregunta por compromiso, no una por corrida.

    Idempotente como `tick`: una pregunta nueva en cada slip a partir del
    tercero llenaria la agenda con la misma pregunta y la volveria invisible
    por repeticion, que es el efecto contrario al buscado.
    """
    marca = f"[{c.id}]"
    previa = next((q for q in store.questions() if marca in q.question), None)
    if previa is not None:
        return previa.id

    # El resolver es el dueno de la DECISION, no el del compromiso: el que
    # corrio la fecha tres veces ya dijo lo que podia decir, y pedirle a el que
    # resuelva es pedirle que se autoescale.
    try:
        resolver = store.get(c.decision_id).owner
    except (KeyError, ValidationError):
        resolver = c.owner

    q = OpenQuestion(
        id="",
        question=(
            f"{marca} se corrio la fecha {c.slips_hacia_adelante} veces: "
            f"¿va a pasar, cambia de dueno, o se cancela?"
        ),
        resolver=resolver,
        resolve_by=c.due,
        blocks=[c.decision_id] if c.decision_id else [],
        meeting_id=c.meeting_id,
        costo_de_no_decidir=(
            f"el compromiso lleva {c.slips_hacia_adelante} corridas y su decision "
            f"({c.decision_id or 'sin decision'}) sigue contando con el"
        ),
    )
    # `force`: la pregunta se abre igual aunque el dueno de la decision haya
    # salido del roster de esa reunion. Es la clase de dato que no puede quedar
    # sin escribir porque un roster quedo viejo — justo el caso de H9.
    store.add_question(q, force=True)
    return q.id


def tick(store: DecideStore, today: date, apply: bool = True) -> dict:
    """Los `diagnostics` del LSP. Vence lo vencible y cierra el lazo solo.

    `today` es un argumento y no `date.today()` a proposito: una funcion que lee
    el reloj no se puede testear, y esta es la que decide si una decision entra
    a la agenda de manana.

    Idempotente: correrlo dos veces el mismo dia no cambia nada la segunda vez.
    """
    changes = {
        "commitments_vencidos": [],
        "supuestos_vencidos": [],
        "decisiones_en_riesgo": [],
        "zombis": [],
        "alias_en_disputa": [],
        "hablada_purgada": [],
        "hablada_sin_politica": [],
    }

    decisions = {d.id: d for d in store.decisions()}
    dirty_decisions: set[str] = set()

    for c in store.commitments():
        new = None
        parent = decisions.get(c.decision_id)
        # `es_zombi` incluye los VENCIDO, no solo los ABIERTO. Un compromiso que
        # vencio antes de que su decision muriera se quedaba VENCIDO para
        # siempre aca mientras el tablero lo contaba zombi.
        if es_zombi(c, parent):
            new = "ZOMBI"
            changes["zombis"].append(c.id)
        elif c.status == "ABIERTO" and c.due < today:
            new = "VENCIDO"
            changes["commitments_vencidos"].append(c.id)
        if new and new != c.status:
            c.status = new
            if apply:
                store.save(c)

    for a in store.assumptions():
        if a.status == "VIGENTE" and a.check_by < today:
            a.status = "VENCIDO"
            changes["supuestos_vencidos"].append(a.id)
            if apply:
                store.save(a)
        if a.pone_en_riesgo and a.decision_id in decisions:
            dirty_decisions.add(a.decision_id)

    for q in store.questions():
        if q.status == "ABIERTA" and q.resolve_by < today:
            q.status = "EXPIRADA"
            if apply:
                store.save(q)

    for did in dirty_decisions:
        d = decisions[did]
        if d.status == "VIGENTE":
            d.status = "EN_RIESGO"
            changes["decisiones_en_riesgo"].append(d.id)
            if apply:
                store.save(d)

    # Retencion del canal HABLADA. Va aca porque `tick` es la unica funcion que
    # ya corre sola y ya recibe `today` — una politica de retencion sin ejecutor
    # es una declaracion, no una politica, y `TranscriptStore.purge()` tenia
    # CERO llamadores en todo el paquete. En Chile la Ley 21.719 rige desde el
    # 1-dic-2026.
    from .store import ValidationError
    from .transcript import TranscriptStore

    try:
        reuniones = store.meetings()
    except (ValidationError, KeyError) as exc:
        # No se puede barrer lo que no se puede enumerar. Se REPORTA en vez de
        # saltearse: una politica de retencion que no corrio y no avisa es peor
        # que ninguna, porque queda documentada como si hubiera corrido. El
        # resto de `tick` sigue — vencer un compromiso no depende de esto.
        reuniones = []
        # Los issues, no la primera linea: la primera linea es "Meeting
        # invalido:" y el nombre del archivo esta abajo, que es lo unico que
        # sirve para arreglarlo.
        changes["hablada_no_barrida"] = "; ".join(getattr(exc, "issues", [str(exc)]))

    for m in reuniones:
        dias = m.consent.retention_days
        if dias is None:
            # Sin politica declarada no se borra nada: borrar por un default
            # seria destruir evidencia que nadie autorizo destruir. Se reporta.
            if (store.root / "hablada" / f"{m.id}.jsonl").exists():
                changes["hablada_sin_politica"].append(m.id)
            continue
        ts = TranscriptStore(store.root, m.id)
        if not apply:
            # Espejo exacto del run real: se pregunta sin escribir.
            if ts.path.exists() and (today - m.date).days > dias:
                changes["hablada_purgada"].append(m.id)
            continue
        if ts.purge(today, dias, desde=m.date):
            changes["hablada_purgada"].append(m.id)
            # El ancla deja de prometer una fuente viva. `CADUCADA` estaba
            # declarado en el schema y no lo escribia nadie: `why()` mostraba
            # `estado_fuente: VIVA` sobre un transcripto que ya no existe.
            for d in decisions.values():
                if d.anchor and d.anchor.meeting_id == m.id and d.anchor.estado_fuente != "CADUCADA":
                    d.anchor.estado_fuente = "CADUCADA"
                    store.save(d)

    # Colision de alias, detectada POR CREACION y no por uso. Solo se disputan
    # los alias de simbolos ANTERIORES: si se disputaran en ambas direcciones,
    # una colision mataria tambien el alias bueno del simbolo viejo.
    if apply:
        from .resolve import AliasStore, mark_disputed

        astore = AliasStore(store.root)
        if astore.alias_path.exists():
            ordenadas = sorted(decisions.values(), key=lambda d: d.id)
            for i, nueva in enumerate(ordenadas):
                marcados = mark_disputed(astore, nueva, ordenadas[:i])
                changes["alias_en_disputa"].extend(marcados)

    changes["fecha"] = today.isoformat()
    # La lista se deriva de las claves que son listas de cambios, en vez de
    # enumerarse a mano: enumerarla a mano es como el barrido de retencion
    # quedo afuera y `tick` reportaba `sin_cambios: True` despues de DESTRUIR un
    # transcripto y escribir su lapida. Un operador que corre `tick`, lee "sin
    # cambios" y no se entera de que se destruyo habla textual es el peor caso
    # de una politica con peso legal (Ley 21.719).
    #
    # `hablada_sin_politica` NO cuenta: es un aviso sobre algo que NO se toco.
    # `hablada_no_barrida` tampoco: es un string, no una lista de cambios.
    _AVISOS = ("hablada_sin_politica", "hablada_no_barrida", "fecha")
    changes["sin_cambios"] = not any(
        v for k, v in changes.items()
        if k not in _AVISOS and isinstance(v, list)
    )
    return changes


def close_meeting(
    store: DecideStore,
    meeting_id: str,
    today: date,
    apply: bool = False,
) -> dict:
    """Cierra una sesion y **cuenta los aplazamientos**.

    Es lo que hace posible `NO_DECISION`, y por eso existe como operacion
    explicita en vez de inferirse: "aplazada por segunda vez" es respecto de
    SESIONES DISTINTAS que terminaron sin resolverla, y eso solo lo sabe quien
    cierra la sesion. `tick` no puede: la fecha de vencimiento pasando una vez
    no es un aplazamiento, es una fecha vencida.

    A la segunda sesion, la pregunta deja de ser un punto pendiente y pasa a ser
    una decision: la de no decidir. El status quo continua, y eso tiene un costo
    que hay que escribir — es lo que convierte el silencio en un objeto. La
    validacion de `OpenQuestion` lo exige a partir del segundo aplazamiento.
    """
    store.get_meeting(meeting_id)  # levanta si no existe
    ag = agenda(store, meeting_id, today=today)
    abiertas = [q for q in ag.open_questions] + [q for q, _ in ag.expired_questions]

    aplazadas, nuevas_no_decision = [], []
    for q in abiertas:
        if meeting_id in q.aplazada_en:
            continue  # cerrar dos veces la misma sesion no cuenta dos veces
        if apply:
            q.aplazada_en = list(q.aplazada_en) + [meeting_id]
            # `force`: la validacion que exige el costo es justamente la que
            # queremos disparar en la AGENDA, no bloquear el cierre de la sesion.
            # Bloquearlo dejaria la sesion sin cerrar y el conteo sin avanzar,
            # que es como el aplazamiento se vuelve invisible otra vez.
            store.save(q, force=True)
        aplazadas.append(q.id)
        if len(set(list(q.aplazada_en) + ([] if apply else [meeting_id]))) >= 2:
            nuevas_no_decision.append(q.id)

    return {
        "meeting": meeting_id,
        "aplazadas": aplazadas,
        "no_decision": nuevas_no_decision,
        "applied": apply,
        "nota": (
            f"{len(nuevas_no_decision)} pregunta(s) quedaron aplazadas por segunda vez: "
            "dejan de ser un punto pendiente y pasan a ser una decision, la de no "
            "decidir. Hay que escribir el costo de seguir sin decidir, o quien lo "
            "averigua y para cuando."
            if nuevas_no_decision
            else f"{len(aplazadas)} pregunta(s) aplazada(s) por primera vez."
        ),
    }
