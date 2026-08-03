"""Parseo de habla espanola: fechas, duenos y marcadores.

Es el unico trabajo genuinamente nuevo de todo el sistema. Todo lo demas es
consulta sobre un registro o reuso de piezas del kit.

Tres reglas que gobiernan el modulo:

  1. **Nunca inferir un dueno.** Si nadie lo nombro, el campo va a `missing` y
     el escriba pregunta. Un dueno inventado es un compromiso que nadie acepto.
  2. **Un texto no alimenta dos campos.** "Para el viernes" es plazo; "lo vemos
     en dos semanas" es revision. Es la leccion de `_RE_CADA` en transcribe.py,
     donde la misma frase inflaba el impacto 40x.
  3. **La ambiguedad se reporta, no se resuelve.** "La otra semana" devuelve
     None con el motivo escrito, no una fecha plausible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

# Reuso deliberado de la normalizacion de gemba: una sola definicion de "que
# significa que dos textos son el mismo" en todo el kit.
from ..gemba.transcribe import WORD_NUMBERS, _norm, strip_accents
from .lexicon import (
    AMBIGUOUS_TIME,
    DUE_CUES,
    MARKERS,
    MONTHS,
    OWNER_CUES,
    OWNER_CUES_AFTER,
    OWNER_CUES_BEFORE,
    RATIONALE_CUES,
    REVIEW_CUES,
    SLOT_LEXICON,
    WEEKDAYS,
)

_NUM = r"(\d{1,3}|" + "|".join(WORD_NUMBERS) + r")"


@dataclass(frozen=True)
class DateHit:
    value: date | None
    role: str  # "due" | "review" | "unknown"
    confidence: float
    matched: str = ""
    note: str = ""


@dataclass(frozen=True)
class OwnerHit:
    value: str | None
    candidates: tuple[str, ...] = ()
    confidence: float = 0.0
    note: str = ""


@dataclass(frozen=True)
class MarkerHit:
    kind: str | None  # decision | question | assumption | commitment
    marker: str = ""
    confidence: float = 0.0
    rest: str = ""  # lo que sigue al marcador


# ------------------------------------------------------------------ fechas


def _next_weekday(base: date, target: int) -> date:
    delta = (target - base.weekday()) % 7
    return base + timedelta(days=delta or 7)


def _end_of_month(d: date) -> date:
    nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
    return nxt - timedelta(days=1)


def _day_in_scope(base: date, day: int, month: int | None = None) -> date | None:
    """Un dia suelto ('antes del 15') cae en este mes si todavia no paso, y en
    el siguiente si ya paso. Es la lectura que hace cualquier persona."""
    try:
        if month:
            cand = date(base.year, month, day)
            return cand if cand >= base else date(base.year + 1, month, day)
        cand = date(base.year, base.month, day)
        if cand >= base:
            return cand
        nm = date(base.year + (base.month == 12), (base.month % 12) + 1, 1)
        return date(nm.year, nm.month, day)
    except ValueError:
        return None


def _role_of(text: str, span_start: int) -> tuple[str, str]:
    """Mira los ~35 caracteres previos a la fecha para decidir si es plazo o
    revision. La ventana es corta a proposito: una pista lejana en la frase
    suele pertenecer a otra clausula."""
    ventana = text[max(0, span_start - 35) : span_start]
    for cue in REVIEW_CUES:
        if cue in ventana:
            return "review", cue
    for cue in DUE_CUES:
        if cue in ventana:
            return "due", cue
    return "unknown", ""


def _find_date(text: str, base: date) -> tuple[date | None, int, str, str]:
    """Devuelve (fecha, posicion, texto_matcheado, nota)."""
    patterns: list[tuple[str, callable]] = [
        (r"\b(\d{4})-(\d{2})-(\d{2})\b",
         lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
        (r"\b(\d{1,2})\s+de\s+(" + "|".join(MONTHS) + r")(?:\s+de\s+(\d{4}))?\b",
         lambda m: _day_in_scope(base, int(m[1]), MONTHS[m[2]])
         if not m[3] else date(int(m[3]), MONTHS[m[2]], int(m[1]))),
        (r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b",
         lambda m: _mk_dmy(m, base)),
        (r"\bpasado\s+manana\b", lambda m: base + timedelta(days=2)),
        (r"\bmanana\b", lambda m: base + timedelta(days=1)),
        (r"\bhoy\b", lambda m: base),
        (r"\bfin\s+de\s+mes\b", lambda m: _end_of_month(base)),
        (r"\bfin\s+de\s+(" + "|".join(MONTHS) + r")\b",
         lambda m: _end_of_month(date(base.year, MONTHS[m[1]], 1))),
        (r"\ben\s+" + _NUM + r"\s+(dias?|semanas?|mes(?:es)?)\b", lambda m: _in_n(m, base)),
        (r"\b(?:el|del)\s+(" + "|".join(WEEKDAYS) + r")\b",
         lambda m: _next_weekday(base, WEEKDAYS[m[1]])),
        (r"\b(?:el|del)\s+(\d{1,2})\b(?!\s*[/-])", lambda m: _day_in_scope(base, int(m[1]))),
    ]
    for pat, build in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        try:
            value = build(m)
        except (ValueError, KeyError, TypeError):
            return None, m.start(), m.group(0), "fecha mal formada"
        return value, m.start(), m.group(0), _nota_de_orden(m)
    return None, -1, "", ""


def _nota_de_orden(m) -> str:
    """Avisa cuando dia y mes son intercambiables.

    El kit lee dd/mm, que es lo correcto en Chile. Pero `3/6` es 3-jun o 6-mar
    segun de donde salga el texto, y **no hay senal en el string** para decidir.
    Un export de WhatsApp de un iPhone con region EE.UU. escribe M/D; el del
    telefono de al lado escribe D/M. Verificado contra exports reales: el mismo
    grupo produce los dos.

    `13/6` en cambio es inequivoco —13 no puede ser mes— y ahi no hay nada que
    avisar. La diferencia entre el caso decidible y el indecidible es
    exactamente lo que faltaba: los dos salian con confianza 0,95 y nota vacia.
    """
    try:
        a, b = int(m[1]), int(m[2])
    except (ValueError, IndexError, TypeError):
        return ""
    if a <= 12 and b <= 12 and a != b:
        return (
            f"'{m.group(0)}' es ambigua: se leyo dd/mm (dia {a}, mes {b}), pero si el "
            f"texto viene de una fuente en formato mm/dd seria dia {b}, mes {a}. "
            "Confirmar antes de promover."
        )
    return ""


def _mk_dmy(m, base: date) -> date | None:
    d, mo = int(m[1]), int(m[2])
    y = int(m[3]) if m[3] else base.year
    if y < 100:
        y += 2000
    try:
        cand = date(y, mo, d)
    except ValueError:
        return None
    return cand if m[3] or cand >= base else date(y + 1, mo, d)


def _in_n(m, base: date) -> date | None:
    n = m[1]
    n = float(n) if n.isdigit() else WORD_NUMBERS.get(n)
    if not n:
        return None
    unidad = m[2]
    if unidad.startswith("dia"):
        return base + timedelta(days=int(n))
    if unidad.startswith("semana"):
        return base + timedelta(weeks=int(n))
    total = base.month - 1 + int(n)
    return date(base.year + total // 12, total % 12 + 1, min(base.day, 28))


def parse_due_date(text: str, meeting_date: date) -> DateHit:
    """Extrae la fecha y decide si es plazo o revision.

    Devuelve `value=None` cuando la expresion es ambigua, con el motivo escrito.
    Preferimos un hueco explicito a una fecha inventada: el hueco cuesta cinco
    segundos de pregunta y la fecha inventada cuesta un compromiso que nadie
    puede decir que esta atrasado.
    """
    t = _norm(text)

    for frase, motivo in AMBIGUOUS_TIME.items():
        if frase in t:
            return DateHit(None, "unknown", 0.0, frase, motivo)

    value, pos, matched, note = _find_date(t, meeting_date)
    if value is None:
        return DateHit(None, "unknown", 0.0, matched, note or "sin fecha reconocible")

    role, cue = _role_of(t, pos)
    if role == "review":
        return DateHit(
            None, "review", 0.0, matched,
            f"'{cue} {matched}' es fecha de revision, no plazo: no se usa como vencimiento",
        )
    conf = 0.95 if role == "due" else 0.55
    motivos = [] if role == "due" else ["fecha sin preposicion de plazo"]
    if note:
        # Ambigua dd/mm contra mm/dd. Baja la confianza por debajo de
        # MIN_CONFIDENCE (0,5) para que el borrador NO salga `ready`: una fecha
        # que puede estar nueve meses corrida no se promueve sin que alguien la
        # mire, aunque venga con "antes del" adelante.
        conf = min(conf, 0.45)
        motivos.append(note)
    return DateHit(value, role, conf, matched, ". ".join(motivos))


# ------------------------------------------------------------------ duenos


def _roster_index(roster: tuple[str, ...]) -> dict:
    first: dict[str, list[str]] = {}
    full: dict[str, str] = {}
    last: dict[str, list[str]] = {}
    for person in roster:
        n = _norm(person)
        full[n] = person
        parts = n.split()
        first.setdefault(parts[0], []).append(person)
        if len(parts) > 1:
            last.setdefault(parts[-1], []).append(person)
    return {"first": first, "full": full, "last": last}


def resolve_owner(text: str, roster: tuple[str, ...]) -> OwnerHit:
    """Resuelve el dueno contra el roster, que es una lista cerrada.

    Convierte el problema mas caro del dominio (reconocimiento de entidades mas
    diarizacion) en un lookup contra seis nombres. Es el analogo del scope
    lexico de un compilador, y es la unica pieza de determinismo que se puede
    fabricar barata.

    Un nombre suelto en la frase NO alcanza: tiene que haber una pista de dueno
    ('dueno', 'lo resuelve', 'se encarga'). Sin esa regla, "reasignar la ruta de
    Fabian, dueno Marcela" convertiria a Fabian en dueno — un error de datos y,
    peor, un tercero mencionado convertido en obligado.
    """
    if not roster:
        return OwnerHit(None, (), 0.0, "sin roster: no hay contra que resolver")

    t = _norm(text)
    idx = _roster_index(roster)

    # Las pistas mandan SIEMPRE, tambien sobre los nombres completos. Un match
    # de nombre completo que corte antes de mirar la direccion vuelve a meter
    # justo el error que esta regla existe para evitar: en "reasignar la ruta de
    # Fabian Soto, dueno Marcela Perez" devolveria a Fabian —un tercero
    # mencionado— con confianza 1,0.
    antes = [(t.find(c), len(c)) for c in OWNER_CUES_BEFORE if c in t]
    despues = [t.find(c) for c in OWNER_CUES_AFTER if c in t]

    # Un solo indice de menciones, con nombre completo y de pila. El completo
    # gana en confianza porque no puede colisionar entre dos personas.
    hits: list[tuple[int, int, str, bool]] = []
    for n, person in idx["full"].items():
        for m in re.finditer(rf"\b{re.escape(n)}\b", t):
            hits.append((m.start(), m.end(), person, True))
    for name, people in idx["first"].items():
        for m in re.finditer(rf"\b{re.escape(name)}\b", t):
            # Si este pila ya quedo cubierto por un nombre completo en la misma
            # posicion, no se cuenta dos veces.
            if any(ini <= m.start() < fin for ini, fin, _, full in hits if full):
                continue
            for person in people:
                hits.append((m.start(), m.end(), person, False))

    if not hits:
        return OwnerHit(None, (), 0.0, "nadie del roster fue nombrado")

    if antes or despues:
        cerca = [
            (person, full)
            for ini, fin, person, full in hits
            if any(c + largo <= ini <= c + largo + 25 for c, largo in antes)
            or any(0 <= c - fin <= 3 for c in despues)
        ]
        candidatos = sorted({p for p, _ in cerca})
        if len(candidatos) == 1:
            completo = any(full for p, full in cerca if p == candidatos[0])
            return OwnerHit(candidatos[0], tuple(candidatos), 1.0 if completo else 0.9)
        if len(candidatos) > 1:
            return OwnerHit(
                None, tuple(candidatos), 0.0,
                f"dos personas del roster junto a la pista de dueno: {candidatos}",
            )
        # Hay pistas y hay nombres, pero ninguno cerca de una pista: el nombre
        # esta en otra clausula. Es el caso del tercero mencionado.

    nombrados = sorted({person for _, _, person, _ in hits})
    if len(nombrados) == 1:
        return OwnerHit(
            None, (nombrados[0],), 0.4,
            f"'{nombrados[0]}' aparece pero sin pista de dueno cerca: puede ser un tercero "
            "mencionado. Confirmar antes de asignarle un compromiso",
        )
    return OwnerHit(
        None, tuple(nombrados), 0.0,
        f"{len(nombrados)} personas nombradas sin pista de dueno: {nombrados}",
    )


# --------------------------------------------------------------- marcadores


def classify_marker(text: str) -> MarkerHit:
    """Detecta las formas verbales del lexico. Nada mas.

    Precision alta por construccion, recall bajo por construccion. Un enunciado
    sin marcador no produce nada, y eso es visible en la tasa de declaracion —
    la metrica de supervivencia del sistema.
    """
    t = _norm(text)
    mejor: MarkerHit | None = None
    for kind, marcadores in MARKERS.items():
        for marcador in marcadores:
            pos = t.find(marcador)
            if pos < 0:
                continue
            resto = text[pos + len(marcador) :].strip(" :,.-—")
            # Mas largo el marcador, mas especifico y mas confiable.
            conf = 0.75 + min(0.2, len(marcador) / 100)
            cand = MarkerHit(kind, marcador, round(conf, 2), resto)
            if mejor is None or len(marcador) > len(mejor.marker):
                mejor = cand
    return mejor or MarkerHit(None)


def extract_rationale(text: str) -> str:
    """El 'porque'. Sin rationale, `Decision.validate` rechaza — y con razon:
    en seis semanas nadie va a saber por que, y la decision se revierte."""
    t = strip_accents(text).lower()
    for cue in RATIONALE_CUES:
        pos = t.find(f" {cue} ")
        if pos >= 0:
            return text[pos + len(cue) + 2 :].strip(" .,")
    return ""


def extract_slots(text: str) -> dict[str, str]:
    """Slots tipados para la desambiguacion de fase 3.

    Devuelve el valor **canonico**, no la forma de superficie: "reslotear" y
    "slotting" tienen que producir el mismo slot o dos menciones del mismo
    proceso no se reconocerian como la misma cosa. La variante mas larga gana,
    para que 'cross docking' no se pierda dentro de una coincidencia parcial.
    """
    t = _norm(text)
    out: dict[str, str] = {}
    for slot, canonicos in SLOT_LEXICON.items():
        mejor: tuple[int, str] | None = None
        for canonico, variantes in canonicos.items():
            for v in variantes:
                if v in t and (mejor is None or len(v) > mejor[0]):
                    mejor = (len(v), canonico)
        if mejor:
            out[slot] = mejor[1]
    return out


def split_statement(rest: str) -> str:
    """Recorta el enunciado antes de la primera clausula de dueno, plazo o
    razon. Sin esto el `statement` se lleva la frase entera y deja de ser una
    oracion imperativa."""
    t = _norm(rest)
    cortes = [
        t.find(f" {c}") for c in (*OWNER_CUES, *RATIONALE_CUES, "para el", "antes del")
    ]
    cortes = [c for c in cortes if c > 0]
    return rest[: min(cortes)].strip(" .,;:") if cortes else rest.strip(" .,;:")
