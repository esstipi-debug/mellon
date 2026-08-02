"""Borradores y cola de revision. Clon estructural de `gemba/transcribe.py`.

El contrato es el mismo que ya esta testeado en el kit: un objeto que sostiene
la incertidumbre (`missing`, `confidence`, `ready`) hasta que un humano la
colapsa, y una cola ordenada para que la vuelta a preguntar sea una sola.

Lo que cambia respecto de gemba: los borradores **expiran**. Lo no revisado en
24 horas deja de existir. Sin expiracion se acumulan borradores sin revisar
hasta que nadie confia en el registro, y un registro en el que nadie confia es
peor que no tener registro.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .parse import (
    classify_marker,
    extract_rationale,
    extract_slots,
    parse_due_date,
    resolve_owner,
    split_statement,
)
from .schema import Assumption, Commitment, Decision, OpenQuestion

EXPIRA_EN_HORAS = 24
MIN_CONFIDENCE = 0.5


@dataclass
class DecisionDraft:
    """Candidato. Nunca entra solo al registro: lo revisa un humano.

    El kit no pretende que un modelo entienda la reunion. Pretende que no se
    pierda el hallazgo porque el escriba estaba participando.
    """

    kind: str  # decision | commitment | assumption | question
    fields: dict
    utterance: str
    confidence: float
    missing: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    start_s: float | None = None
    created_at: str = ""
    meeting_id: str = ""

    @property
    def ready(self) -> bool:
        return not self.missing and self.confidence >= MIN_CONFIDENCE

    def expired(self, now: datetime) -> bool:
        if not self.created_at:
            return False
        return now - datetime.fromisoformat(self.created_at) > timedelta(hours=EXPIRA_EN_HORAS)

    def to_dict(self) -> dict:
        d = {**self.__dict__}
        d["missing"] = list(self.missing)
        d["notes"] = list(self.notes)
        d["ready"] = self.ready
        return d

    @staticmethod
    def from_dict(d: dict) -> "DecisionDraft":
        d = {k: v for k, v in d.items() if k != "ready"}
        d["missing"] = tuple(d.get("missing", ()))
        d["notes"] = tuple(d.get("notes", ()))
        return DecisionDraft(**d)


# ----------------------------------------------------------------- parseo


def _mk_decision(rest: str, utt: str, roster, meeting_date: date) -> tuple[dict, list, list]:
    owner = resolve_owner(utt, roster)
    fecha = parse_due_date(utt, meeting_date)
    rationale = extract_rationale(utt)
    statement = split_statement(rest)

    campos = {
        "statement": statement,
        "owner": owner.value or "",
        "criteria": f"a mas tardar {fecha.value.isoformat()}" if fecha.value else "",
        "rationale": rationale,
        "date_decided": meeting_date.isoformat(),
        "slots": extract_slots(utt),
    }
    faltan = [k for k in ("statement", "owner", "criteria", "rationale") if not campos[k]]
    notas = [n for n in (owner.note, fecha.note) if n]
    return campos, faltan, notas


def _mk_commitment(rest: str, utt: str, roster, meeting_date: date) -> tuple[dict, list, list]:
    owner = resolve_owner(utt, roster)
    fecha = parse_due_date(utt, meeting_date)
    campos = {
        "what": split_statement(rest),
        "owner": owner.value or "",
        "due": fecha.value.isoformat() if fecha.value else "",
        "evidence_of_done": "",
        "decision_id": "",
    }
    faltan = [k for k in ("what", "owner", "due") if not campos[k]]
    # Nunca se infiere: sin evidencia verificable, "hecho" es una opinion, y sin
    # decision padre un compromiso es una tarea. Los dos los pone el humano.
    faltan += ["evidence_of_done", "decision_id"]
    notas = [n for n in (owner.note, fecha.note) if n]
    return campos, faltan, notas


def _mk_assumption(rest: str, utt: str, roster, meeting_date: date) -> tuple[dict, list, list]:
    fecha = parse_due_date(utt, meeting_date)
    campos = {
        "statement": split_statement(rest),
        "check_by": fecha.value.isoformat() if fecha.value else "",
        "source": "",
        "decision_id": "",
    }
    faltan = [k for k in ("statement", "check_by") if not campos[k]]
    faltan.append("decision_id")
    return campos, faltan, [fecha.note] if fecha.note else []


def _mk_question(rest: str, utt: str, roster, meeting_date: date) -> tuple[dict, list, list]:
    owner = resolve_owner(utt, roster)
    fecha = parse_due_date(utt, meeting_date)
    texto = split_statement(rest)
    campos = {
        "question": texto if texto.endswith("?") else f"{texto}?",
        "resolver": owner.value or "",
        "resolve_by": fecha.value.isoformat() if fecha.value else "",
    }
    faltan = [k for k in ("resolver", "resolve_by") if not campos[k]]
    notas = [n for n in (owner.note, fecha.note) if n]
    return campos, faltan, notas


_BUILDERS = {
    "decision": _mk_decision,
    "commitment": _mk_commitment,
    "assumption": _mk_assumption,
    "question": _mk_question,
}


def draft_decisions(
    text_or_segments,
    roster: tuple[str, ...],
    meeting_date: date,
    meeting_id: str = "",
    now: datetime | None = None,
) -> list[DecisionDraft]:
    """Convierte un transcripto en borradores. Acepta texto plano o segmentos.

    Clon estructural de `draft_observations`. Solo produce algo donde hay un
    marcador verbal: un enunciado sin marcador no genera nada, y eso es
    deliberado — el silencio del sistema mide la disciplina del facilitador, y
    esa es la metrica de supervivencia.
    """
    now = now or datetime.now().astimezone()
    stamp = now.isoformat()

    if isinstance(text_or_segments, str):
        items = [
            {"text": u.strip(), "start": None}
            for u in _split(text_or_segments)
            if len(u.strip()) > 12
        ]
    else:
        items = [
            {"text": s.get("text", "").strip(), "start": s.get("start")}
            for s in text_or_segments
            if len(s.get("text", "").strip()) > 12
        ]

    drafts: list[DecisionDraft] = []
    for it in items:
        utt = it["text"]
        hit = classify_marker(utt)
        if hit.kind is None:
            continue
        campos, faltan, notas = _BUILDERS[hit.kind](hit.rest, utt, roster, meeting_date)
        drafts.append(
            DecisionDraft(
                kind=hit.kind,
                fields=campos,
                utterance=utt,
                confidence=hit.confidence,
                missing=tuple(faltan),
                notes=tuple(notas),
                start_s=it["start"],
                created_at=stamp,
                meeting_id=meeting_id,
            )
        )
    return drafts


def _split(text: str) -> list[str]:
    import re

    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]


def review_queue(drafts: list[DecisionDraft]) -> list[DecisionDraft]:
    """Ordenada para que la vuelta a preguntar sea una sola: primero los que
    solo les falta un dato, despues por confianza descendente."""
    pend = [d for d in drafts if not d.ready]
    return sorted(pend, key=lambda d: (len(d.missing), -d.confidence))


def expire(drafts: list[DecisionDraft], now: datetime) -> tuple[list, list]:
    """Devuelve (vivos, expirados). Lo no revisado en 24 h no existe: nada de
    'el sistema lo capturo igual'."""
    vivos = [d for d in drafts if not d.expired(now)]
    return vivos, [d for d in drafts if d.expired(now)]


# ------------------------------------------------------------- persistencia


class DraftStore:
    """JSONL append-only por reunion. Mismo patron que `GembaSession`."""

    def __init__(self, root: str | Path, meeting_id: str):
        self.path = Path(root) / "drafts" / f"{meeting_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.meeting_id = meeting_id

    def append(self, drafts: list[DecisionDraft]) -> int:
        with self.path.open("a", encoding="utf-8") as fh:
            for d in drafts:
                fh.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")
        return len(drafts)

    def load(self) -> list[DecisionDraft]:
        if not self.path.exists():
            return []
        return [
            DecisionDraft.from_dict(json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def rewrite(self, drafts: list[DecisionDraft]) -> None:
        self.path.write_text(
            "\n".join(json.dumps(d.to_dict(), ensure_ascii=False) for d in drafts) + "\n",
            encoding="utf-8",
        )


# --------------------------------------------------------------- promocion


def to_entity(draft: DecisionDraft, meeting_id: str = ""):
    """Convierte un borrador listo en la entidad del registro.

    No valida: de eso se encarga el store, que es el unico lugar donde se
    decide si algo entra o no. Dos validadores es un validador que se
    desincroniza.
    """
    from .schema import parse_date

    f = draft.fields
    mid = meeting_id or draft.meeting_id
    if draft.kind == "decision":
        return Decision(
            id="", statement=f["statement"], owner=f["owner"],
            date_decided=parse_date(f["date_decided"]), criteria=f["criteria"],
            rationale=f["rationale"], meeting_id=mid, slots=f.get("slots", {}),
        )
    if draft.kind == "commitment":
        return Commitment(
            id="", decision_id=f["decision_id"], what=f["what"], owner=f["owner"],
            due=parse_date(f["due"]), evidence_of_done=f["evidence_of_done"], meeting_id=mid,
        )
    if draft.kind == "assumption":
        return Assumption(
            id="", decision_id=f["decision_id"], statement=f["statement"],
            check_by=parse_date(f["check_by"]), source=f.get("source") or "sin_fuente",
            meeting_id=mid,
        )
    return OpenQuestion(
        id="", question=f["question"], resolver=f["resolver"],
        resolve_by=parse_date(f["resolve_by"]), meeting_id=mid,
    )
