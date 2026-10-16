"""Canalizacion de dudas post-video (3 vias), reconciliacion estilo Granola y ROI.

Conecta el flujo asincronico de Meeting-Killer OS (video condensado de 2 min
estilo Claude Design) con `fdekit.decide`:

  1. **Triaje epistemico en 3 vias (`triage_doubt`)**:
     - Filtra primero por la interseccion estricta de permisos (`acl_principals`)
       de todos los destinatarios antes de inspeccionar el texto. Un documento
       que un solo participante no puede ver jamas se cita ni se usa.
     - Via 1 (`VIA_1_CITA_DOCUMENTO`): la duda pregunta por un dato cubierto en
       el reporte base de 2-9 paginas -> responde con cita textual (0 min reunion).
     - Via 2 (`VIA_2_LAGUNA_DRI`): el dato no figura en el corpus permitido ->
       el sistema se abstiene de inventar y deriva al DRI en el hilo (0 min reunion).
     - Via 3 (`VIA_3_LLAMADA_QUIRURGICA`): desacuerdo de criterio/prioridad ->
       agenda llamada quirurgica de 15 min solo entre quien objeta y el DRI.

  2. **Reconciliacion estilo Granola (`reconcile_granola_session`)**:
     - Toma las dudas de Slack como esqueleto de notas previo y las cruza con el
       transcripto/segmentos de la llamada quirurgica de 15 min (capturada sin
       bot intruso).
     - Ninguna duda por la cual se convoco la llamada puede desaparecer en
       silencio: si el audio no produjo un borrador que la resuelva, se promueve
       explicitamente a `DecisionDraft(kind="question")` para que el cierre
       cuadre (`resueltas + abiertas_sin_respuesta == total_dudas`).

  3. **Contraste economico y Bloque de Foco Recuperado (`compute_interception_roi`)**:
     - Calcula el ahorro neto real (descontando el tiempo de ver el video y la
       llamada quirurgica si ocurrio) y el tiempo convertido en
       `Bloque de Foco Recuperado` en el calendario de cada invitado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from ..gemba.transcribe import _norm
from .draft import DecisionDraft, draft_decisions

VIA_1_CITA_DOCUMENTO = "VIA_1_CITA_DOCUMENTO"
VIA_2_LAGUNA_DRI = "VIA_2_LAGUNA_DRI"
VIA_3_LLAMADA_QUIRURGICA = "VIA_3_LLAMADA_QUIRURGICA"

_TRADEOFF_CUES = (
    "no estoy de acuerdo",
    "en desacuerdo",
    "prefiero",
    "mejor secuenciar",
    "en vez de",
    "en lugar de",
    "no conviene",
    "objeto",
    "bloqueo",
    "riesgo de hacer",
)

_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "al", "en", "con",
    "por", "para", "que", "cual", "como", "cuando", "donde", "quien", "se",
    "es", "son", "fue", "hay", "no", "si", "mas", "menos", "sobre", "este",
    "esta", "estos", "estas", "ese", "esa", "o", "y", "a", "ante", "bajo",
}


@dataclass(frozen=True)
class DocumentChunkACL:
    """Fragmento del reporte base (2-9 paginas) con lista de acceso explicita."""

    doc_id: str
    section_ref: str
    text: str
    acl_principals: frozenset[str]


@dataclass(frozen=True)
class DoubtItem:
    """Duda o comentario dejado en Slack tras ver el video de 2 minutos."""

    id: str
    author: str
    text: str


@dataclass(frozen=True)
class DoubtTriageResult:
    """Veredicto determinista del triaje de una duda."""

    doubt_id: str
    route: str
    exact_quote: str
    source_ref: str
    required_attendees: tuple[str, ...]
    meeting_minutes: int
    abstained: bool
    acl_filtered_out: int


def _content_tokens(text: str) -> set[str]:
    normed = _norm(text)
    words = re.findall(r"[a-z0-9]+", normed)
    return {w for w in words if len(w) >= 4 and w not in _STOPWORDS}


def filter_chunks_by_acl(
    chunks: list[DocumentChunkACL],
    recipient_ids: tuple[str, ...] | set[str],
) -> tuple[list[DocumentChunkACL], int]:
    """Filtra en memoria emulando el predicado SQL de interseccion de ACLs.

    Un chunk pasa solo si TODOS los destinatarios del hilo tienen permiso de
    lectura. Devuelve (chunks_permitidos, cantidad_excluida_por_acl).
    """
    required = set(recipient_ids)
    if not required:
        return [], len(chunks)
    allowed: list[DocumentChunkACL] = []
    excluded = 0
    for ch in chunks:
        if required.issubset(ch.acl_principals):
            allowed.append(ch)
        else:
            excluded += 1
    return allowed, excluded


def triage_doubt(
    doubt: DoubtItem,
    chunks: list[DocumentChunkACL],
    recipient_ids: tuple[str, ...] | set[str],
    dri_user_id: str,
) -> DoubtTriageResult:
    """Clasifica una duda en una de las 3 vias sin fugas de ACL ni alucinacion."""
    allowed_chunks, excluded_count = filter_chunks_by_acl(chunks, recipient_ids)
    norm_text = _norm(doubt.text)

    # 1. Desacuerdo de criterio / trade-off -> Via 3 (Llamada Quirurgica 15 min)
    if any(cue in norm_text for cue in _TRADEOFF_CUES):
        attendees = tuple(sorted({doubt.author, dri_user_id}))
        return DoubtTriageResult(
            doubt_id=doubt.id,
            route=VIA_3_LLAMADA_QUIRURGICA,
            exact_quote="",
            source_ref="",
            required_attendees=attendees,
            meeting_minutes=15,
            abstained=False,
            acl_filtered_out=excluded_count,
        )

    # 2. Busqueda factual sobre los chunks permitidos por ACL -> Via 1
    q_tokens = _content_tokens(doubt.text)
    best_chunk: DocumentChunkACL | None = None
    best_overlap = 0
    for ch in allowed_chunks:
        overlap = len(q_tokens & _content_tokens(ch.text))
        if overlap > best_overlap:
            best_overlap = overlap
            best_chunk = ch

    if best_chunk is not None and best_overlap >= 2:
        return DoubtTriageResult(
            doubt_id=doubt.id,
            route=VIA_1_CITA_DOCUMENTO,
            exact_quote=best_chunk.text.strip(),
            source_ref=f"{best_chunk.doc_id}:{best_chunk.section_ref}",
            required_attendees=(),
            meeting_minutes=0,
            abstained=False,
            acl_filtered_out=excluded_count,
        )

    # 3. Laguna en el reporte base -> Via 2 (Abstencion honesta + ping al DRI)
    return DoubtTriageResult(
        doubt_id=doubt.id,
        route=VIA_2_LAGUNA_DRI,
        exact_quote="",
        source_ref="",
        required_attendees=(dri_user_id,),
        meeting_minutes=0,
        abstained=True,
        acl_filtered_out=excluded_count,
    )


@dataclass(frozen=True)
class GranolaReconciliation:
    """Resultado de cruzar el esqueleto de dudas de Slack con el audio de 15m."""

    meeting_id: str
    drafts: tuple[DecisionDraft, ...]
    resolved_doubt_ids: tuple[str, ...]
    unanswered_doubt_ids: tuple[str, ...]
    total_skeleton_doubts: int

    def cobertura(self) -> dict:
        """Cierra la aritmetica de la llamada quirurgica.

        Toda duda que motivo la llamada o quedo resuelta por un borrador del
        audio o fue promovida a OpenQuestion explicita. Ninguna desaparece.
        """
        resueltas = len(self.resolved_doubt_ids)
        abiertas = len(self.unanswered_doubt_ids)
        total = self.total_skeleton_doubts
        return {
            "total_dudas_agenda": total,
            "resueltas_en_audio": resueltas,
            "promovidas_a_pregunta_abierta": abiertas,
            "total_borradores": len(self.drafts),
            "cuadra": (resueltas + abiertas) == total,
        }


def reconcile_granola_session(
    skeleton_doubts: list[DoubtItem],
    text_or_segments,
    roster: tuple[str, ...],
    meeting_date: date,
    meeting_id: str = "",
    now: datetime | None = None,
) -> GranolaReconciliation:
    """Cruza las notas de dudas de Slack (esqueleto Granola) con el transcripto.

    Si una duda de la agenda fue abordada en los borradores extraidos del audio,
    se anota en `notes` del borrador que resuelve `doubt.id`. Si una duda de la
    agenda NO recibio respuesta en el audio, se crea un `DecisionDraft` de tipo
    `question` para que quede en la cola de revision y nunca se pierda en silencio.
    """
    now = now or datetime.now().astimezone()
    stamp = now.isoformat()
    extracted = draft_decisions(
        text_or_segments=text_or_segments,
        roster=roster,
        meeting_date=meeting_date,
        meeting_id=meeting_id,
        now=now,
    )

    final_drafts: list[DecisionDraft] = []
    resolved_ids: list[str] = []
    unanswered_ids: list[str] = []

    used_draft_indices: set[int] = set()

    for doubt in skeleton_doubts:
        d_tokens = _content_tokens(doubt.text)
        matched_idx: int | None = None
        best_score = 0
        for idx, dr in enumerate(extracted):
            score = len(d_tokens & _content_tokens(dr.utterance))
            if score > best_score:
                best_score = score
                matched_idx = idx

        if matched_idx is not None and best_score >= 1:
            resolved_ids.append(doubt.id)
            used_draft_indices.add(matched_idx)
            orig = extracted[matched_idx]
            tagged = DecisionDraft(
                kind=orig.kind,
                fields=orig.fields,
                utterance=orig.utterance,
                confidence=orig.confidence,
                missing=orig.missing,
                notes=(*orig.notes, f"resuelve_duda:{doubt.id}"),
                start_s=orig.start_s,
                created_at=orig.created_at,
                meeting_id=orig.meeting_id,
                origen=orig.origen,
                expira_en_horas=orig.expira_en_horas,
            )
            final_drafts.append(tagged)
        else:
            unanswered_ids.append(doubt.id)
            q_text = doubt.text.strip()
            if not q_text.endswith("?"):
                q_text = f"{q_text}?"
            final_drafts.append(
                DecisionDraft(
                    kind="question",
                    fields={
                        "question": q_text,
                        "resolver": doubt.author if doubt.author in roster else "",
                        "resolve_by": "",
                    },
                    utterance=doubt.text,
                    confidence=0.8,
                    missing=("resolve_by",) if doubt.author in roster else ("resolver", "resolve_by"),
                    notes=(
                        f"duda_agenda_sin_respuesta:{doubt.id}",
                        "promovida automaticamente para no perderla en silencio",
                    ),
                    start_s=None,
                    created_at=stamp,
                    meeting_id=meeting_id,
                )
            )

    for idx, dr in enumerate(extracted):
        if idx not in used_draft_indices:
            final_drafts.append(dr)

    return GranolaReconciliation(
        meeting_id=meeting_id,
        drafts=tuple(final_drafts),
        resolved_doubt_ids=tuple(resolved_ids),
        unanswered_doubt_ids=tuple(unanswered_ids),
        total_skeleton_doubts=len(skeleton_doubts),
    )


def compute_interception_roi(
    attendees_count: int,
    scheduled_hours: float,
    hourly_rate_usd: float = 20.0,
    video_minutes: float = 2.0,
    vote_overhead_minutes: float = 1.0,
    consumption_ratios: tuple[float, ...] | None = None,
    surgical_call_attendees: int = 0,
    surgical_call_minutes: float = 15.0,
    ai_synthesis_cost_usd: float = 0.15,
) -> dict:
    """Calcula el ahorro neto honesto y el Bloque de Foco Recuperado.

    Descuenta el tiempo real consumido viendo el video, el minuto de votacion,
    la llamada quirurgica (si ocurrio) y el costo de IA. Ademas calcula cuantos
    minutos del evento original se bloquean en el calendario como
    `Bloque de Foco Recuperado` (reservando los primeros 5 min para el video).
    """
    if attendees_count <= 0 or scheduled_hours <= 0 or hourly_rate_usd < 0:
        raise ValueError("attendees_count y scheduled_hours deben ser positivos")

    ratios = (
        consumption_ratios
        if consumption_ratios is not None
        else tuple(1.0 for _ in range(attendees_count))
    )
    if len(ratios) != attendees_count:
        raise ValueError("consumption_ratios debe tener un valor por asistente")

    gross_sync_hours = attendees_count * scheduled_hours
    gross_sync_cost_usd = gross_sync_hours * hourly_rate_usd

    video_hours_total = sum(
        (video_minutes / 60.0) * max(0.0, min(1.0, r)) for r in ratios
    )
    vote_hours_total = sum(
        (vote_overhead_minutes / 60.0) * (1.0 if r > 0 else 0.0) for r in ratios
    )
    surgical_hours_total = (
        (surgical_call_attendees * surgical_call_minutes) / 60.0
        if surgical_call_attendees > 0
        else 0.0
    )

    total_async_hours = video_hours_total + vote_hours_total + surgical_hours_total
    total_async_cost_usd = (total_async_hours * hourly_rate_usd) + ai_synthesis_cost_usd

    net_saved_hours = gross_sync_hours - total_async_hours
    net_saved_usd = gross_sync_cost_usd - total_async_cost_usd

    scheduled_minutes = int(round(scheduled_hours * 60))
    async_slot_minutes = min(5, scheduled_minutes)
    defended_focus_minutes_per_person = max(0, scheduled_minutes - async_slot_minutes)

    cuadra = (
        abs((total_async_hours + net_saved_hours) - gross_sync_hours) < 1e-9
        and (async_slot_minutes + defended_focus_minutes_per_person) == scheduled_minutes
    )

    return {
        "attendees_count": attendees_count,
        "scheduled_hours": scheduled_hours,
        "hourly_rate_usd": hourly_rate_usd,
        "gross_sync_hours": round(gross_sync_hours, 4),
        "gross_sync_cost_usd": round(gross_sync_cost_usd, 2),
        "total_async_hours": round(total_async_hours, 4),
        "total_async_cost_usd": round(total_async_cost_usd, 2),
        "net_saved_hours": round(net_saved_hours, 4),
        "net_saved_usd": round(net_saved_usd, 2),
        "savings_ratio": round(net_saved_usd / gross_sync_cost_usd, 4) if gross_sync_cost_usd > 0 else 0.0,
        "async_slot_minutes": async_slot_minutes,
        "defended_focus_minutes_per_person": defended_focus_minutes_per_person,
        "cuadra": cuadra,
    }
