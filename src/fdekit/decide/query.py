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

from .schema import Assumption, Commitment, Decision, OpenQuestion
from .store import DecideStore

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
    advisories: list = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (
            self.overdue_commitments
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

    ag = Agenda(meeting_id=meeting_id, meeting_date=meeting.date, roster=roster)

    ag.overdue_commitments = sorted(
        [
            (c, c.days_late(today))
            for c in commitments
            if c.status in ("ABIERTO", "VENCIDO", "ZOMBI") and c.due < today
        ],
        key=lambda t: -t[1],
    )

    for a in assumptions:
        if not a.pone_en_riesgo:
            continue
        d = decisions.get(a.decision_id)
        if d and d.status in ("VIGENTE", "EN_RIESGO"):
            ag.at_risk_decisions.append((d, a))

    for q in questions:
        if q.status == "EXPIRADA":
            ag.expired_questions.append((q, (today - q.resolve_by).days))
            continue
        if q.status != "ABIERTA":
            continue
        if q.reopen_of:
            ag.reopen_requests.append(q)
            continue
        passes, reason, action = _gate(q, roster, questions)
        if passes:
            ag.open_questions.append(q)
        else:
            ag.gate_rejections.append({"id": q.id, "reason": reason, "action": action})

    for a in assumptions:
        ag.advisories.extend(a.advisories())
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
        "nota_cita": (
            "sin cita: la decision se registro sin canal HABLADA (a mano o desde texto "
            "sin timestamps)"
            if d.anchor.empty
            else ""
        ),
    }


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
    commits = [c for c in implementations(store, decision_id) if c.status in ("ABIERTO", "VENCIDO", "ZOMBI")]
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

    stamp = (today or nueva.date_decided).isoformat()
    vieja.status = "SUPERADA"
    vieja.superseded_by = new_id
    vieja.version += 1
    # El statement viejo queda aca, consultable, y NO como alias: un alias con
    # el statement de la decision superada fabricaria colisiones a proposito.
    vieja.historial_statements.append(f"{stamp} SUPERADA por {new_id}: {reason}")
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
        if c.status in ("ABIERTO", "VENCIDO", "ZOMBI"):
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
        d.historial_statements.append(f"{stamp} REVERTIDA: {reason}")
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
    }

    decisions = {d.id: d for d in store.decisions()}
    dirty_decisions: set[str] = set()

    for c in store.commitments():
        new = None
        parent = decisions.get(c.decision_id)
        if c.status == "ABIERTO" and parent and parent.status in ("REVERTIDA", "SUPERADA"):
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
    changes["sin_cambios"] = not any(
        changes[k]
        for k in (
            "commitments_vencidos",
            "supuestos_vencidos",
            "decisiones_en_riesgo",
            "zombis",
            "alias_en_disputa",
        )
    )
    return changes
