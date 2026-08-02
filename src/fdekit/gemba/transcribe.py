"""Audio del pasillo -> observaciones de gemba estructuradas.

El cuello de la herramienta 1 no es analizar observaciones: es capturarlas. En
el pasillo no se escribe. Grabar 20 minutos por turno, transcribir y extraer los
campos deja 15 observaciones estructuradas donde antes habia tres garabatos.

El modulo tiene dos capas separadas a proposito:

    transcribe()          necesita torch + transformers. Se instala aparte.
    draft_observations()  Python puro. Es donde vive la logica y donde estan
                          los tests.

Esa separacion importa: el kit corre en el notebook prestado de un CD sin GPU y
sin permisos de instalacion. Si el audio viene ya transcrito (de un telefono, de
un servicio externo, de un colega), `draft_observations` funciona igual y no
hace falta instalar nada.

ANTES DE GRABAR: transcribir a un operador es grabar a una persona. Consentimiento
explicito, decir para que es, y anonimizar antes de que el audio salga del sitio.
No es un tramite legal — es lo que decide si te vuelven a hablar en el segundo
turno. Usar `anonymize=` con los nombres que aparezcan.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .schema import Observation

DEFAULT_MODEL = "openai/whisper-large-v3-turbo"

# Vocabulario que Whisper no conoce y transcribe mal sin ayuda. Se le pasa como
# prompt inicial. Ampliarlo con los terminos del cliente en el kickoff: cada CD
# tiene su jerga y es lo primero que hay que anotar.
WAREHOUSE_VOCAB = [
    "SKU", "pallet", "picking", "packing", "ola", "hueco", "anden", "racks",
    "grua horquilla", "transpaleta", "WMS", "terminal RF", "pistoleo",
    "reposicion", "zunchado", "guia de despacho", "slotting", "cross docking",
]

SHIFT_HOURS = 8.0

# Lexico de desperdicio en el vocabulario real del piso, no en el de un manual.
# Se compara contra texto sin acentos y en minusculas.
WASTE_LEXICON: dict[str, tuple[str, ...]] = {
    "ESPERA": (
        "esperando", "espero", "esperar", "cola", "parado", "detenido", "sin hacer nada",
        "hasta que llegue", "se cuelga", "se demora el sistema", "lento el sistema",
        "no me llega", "quedo esperando",
    ),
    "MOVIMIENTO": (
        "buscar", "busco", "buscando", "caminar", "camino", "caminata", "voy hasta",
        "me agacho", "agacharme", "subir la escalera", "recorro", "de un lado a otro",
        "dar la vuelta", "cruzar el pasillo",
    ),
    "DEFECTO": (
        "error", "equivocado", "equivoca", "rehacer", "lo hago de nuevo", "no cierra",
        "no calza", "se rompe", "reclamo", "devuelto", "devolucion", "mal picking",
        "caja chica", "no corresponde", "sale malo",
    ),
    "SOBREPROCESO": (
        "dos veces", "doble", "otra vez lo mismo", "planilla aparte", "ademas anoto",
        "tambien lo anoto", "reviso de nuevo", "vuelvo a contar", "por si acaso",
    ),
    "TRANSPORTE": (
        "traslado", "trasladar", "llevar hasta", "mover el pallet", "llevo el pallet",
        "de bodega a", "hasta el anden",
    ),
    "INVENTARIO": (
        "acumulado", "apilado", "parado ahi", "se junta", "amontonado",
        "pallets esperando", "lleno de cajas",
    ),
    "SOBREPRODUCCION": (
        "antes de tiempo", "adelantado", "preparo de mas", "de mas", "por adelantado",
    ),
    "TALENTO": (
        "nadie pregunta", "ya avise", "yo le dije", "nadie escucha", "nadie me hace caso",
        "lo vengo diciendo",
    ),
}

WORD_NUMBERS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50, "sesenta": 60, "cien": 100,
}

_UNIT_SECONDS = {"segundo": 1, "seg": 1, "minuto": 60, "min": 60, "hora": 3600, "hr": 3600}


# --------------------------------------------------------------- normalizacion


def strip_accents(text: str) -> str:
    """Quita acentos. El operador dice 'día' y Whisper a veces escribe 'dia'."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm(text: str) -> str:
    return strip_accents(text).lower()


def _number(token: str) -> float | None:
    token = token.strip().replace(",", ".")
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return WORD_NUMBERS.get(_norm(token))


# ------------------------------------------------------------------- parsers

_NUM = r"(\d+(?:[.,]\d+)?|" + "|".join(WORD_NUMBERS) + r")"
_UNIT = r"(segundos?|seg|minutos?|min|horas?|hrs?)"

_RE_MEDIA_UNIT = re.compile(r"\bmedia\s+hora\b|\bmedio\s+minuto\b")
_RE_UNIT_Y_MEDIA = re.compile(rf"\b{_NUM}?\s*(hora|minuto)s?\s+y\s+medi[ao]\b")
_RE_DUR = re.compile(rf"\b{_NUM}\s*{_UNIT}\b")

_RE_VECES = re.compile(rf"\b{_NUM}\s*veces?\b(?:\s*(?:al|por|a la|en el)\s*(dia|turno|hora|jornada))?")
_RE_CADA = re.compile(rf"\bcada\s*{_NUM}\s*{_UNIT}\b")
_RE_OPERADORES = re.compile(rf"\b{_NUM}\s*(?:operarios?|pickers?|personas?|companeros?)\b")


def parse_duration_s(text: str) -> float | None:
    """Extrae una duracion en segundos. Reconoce 'media hora', 'hora y media',
    '2 minutos', 'treinta segundos'."""
    # "cada 10 minutos" es frecuencia, no duracion. Sin esta linea la misma
    # frase alimenta los dos campos y el impacto sale multiplicado por 40 — el
    # tipo de error que no falla, solo miente, y se lleva el Pareto entero.
    t = _RE_CADA.sub(" ", _norm(text))

    m = _RE_UNIT_Y_MEDIA.search(t)
    if m:
        base = _number(m.group(1)) if m.group(1) else 1.0
        unit = 3600 if m.group(2).startswith("hora") else 60
        return (base or 1.0) * unit + unit / 2

    if _RE_MEDIA_UNIT.search(t):
        return 1800.0 if "hora" in _RE_MEDIA_UNIT.search(t).group(0) else 30.0

    m = _RE_DUR.search(t)
    if m:
        n = _number(m.group(1))
        if n is None:
            return None
        unit = next(v for k, v in _UNIT_SECONDS.items() if m.group(2).startswith(k))
        return n * unit
    return None


def parse_frequency_per_shift(text: str, shift_hours: float = SHIFT_HOURS) -> float | None:
    """Extrae frecuencia por turno. Reconoce '20 veces al dia', 'tres veces por
    hora', 'cada 10 minutos'."""
    t = _norm(text)

    m = _RE_CADA.search(t)
    if m:
        n = _number(m.group(1))
        if n:
            unit = next(v for k, v in _UNIT_SECONDS.items() if m.group(2).startswith(k))
            interval = n * unit
            if interval > 0:
                return round(shift_hours * 3600 / interval, 1)

    m = _RE_VECES.search(t)
    if m:
        n = _number(m.group(1))
        if n is None:
            return None
        scope = m.group(2)
        if scope == "hora":
            return round(n * shift_hours, 1)
        return float(n)  # dia / turno / jornada / sin calificar -> por turno
    return None


def parse_operators(text: str) -> int:
    m = _RE_OPERADORES.search(_norm(text))
    if m:
        n = _number(m.group(1))
        if n:
            return int(n)
    return 1


def classify_waste(text: str) -> tuple[str | None, float]:
    """Devuelve (tipo, confianza). Confianza = margen del ganador sobre el
    segundo, normalizado. Bajo 0.5 el humano tiene que confirmar — clasificar
    mal un desperdicio manda el Pareto a la basura."""
    t = _norm(text)
    scores = {
        waste: sum(1 for kw in kws if kw in t) for waste, kws in WASTE_LEXICON.items()
    }
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top, top_n = ranked[0]
    if top_n == 0:
        return None, 0.0
    second_n = ranked[1][1]
    return top, round((top_n - second_n) / top_n, 2) if top_n else 0.0


# --------------------------------------------------------------------- drafts


@dataclass
class Draft:
    """Observacion candidata. Nunca entra sola a la sesion: la revisa un humano.

    El kit no pretende que un modelo entienda la operacion. Pretende que el FDE
    no pierda el hallazgo porque tenia las manos ocupadas.
    """

    observation: Observation
    utterance: str
    confidence: float
    missing: tuple[str, ...] = ()
    start_s: float | None = None

    @property
    def ready(self) -> bool:
        return not self.missing and self.confidence >= 0.5

    def to_dict(self) -> dict:
        return {
            **self.observation.to_dict(),
            "utterance": self.utterance,
            "confidence": self.confidence,
            "missing": list(self.missing),
            "start_s": self.start_s,
            "ready": self.ready,
        }


def split_utterances(text: str) -> list[str]:
    """Parte el transcrito en enunciados. Whisper puntua razonablemente; cuando
    no, se corta por pausas largas marcadas con coma y conector."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 12]


def draft_observations(
    text_or_segments,
    area: str = "",
    activity: str = "",
    shift: str = "",
    observer: str = "",
    shift_hours: float = SHIFT_HOURS,
    anonymize: tuple[str, ...] = (),
) -> list[Draft]:
    """Convierte un transcrito en observaciones candidatas.

    Acepta texto plano o la lista de segmentos de `Transcript.segments`.
    `anonymize` reemplaza nombres propios antes de que nada se persista.
    """
    if isinstance(text_or_segments, str):
        items = [{"text": u, "start": None} for u in split_utterances(text_or_segments)]
    else:
        items = [
            {"text": s.get("text", "").strip(), "start": s.get("start")}
            for s in text_or_segments
            if len(s.get("text", "").strip()) > 12
        ]

    drafts: list[Draft] = []
    for it in items:
        utt = _redact(it["text"], anonymize)
        waste, conf = classify_waste(utt)
        if waste is None:
            continue

        dur = parse_duration_s(utt)
        freq = parse_frequency_per_shift(utt, shift_hours)

        missing = tuple(
            k for k, v in (("duration_s", dur), ("frequency_per_shift", freq)) if v is None
        )
        obs = Observation(
            area=area,
            activity=activity or utt[:60],
            waste_type=waste,
            description=utt,
            duration_s=dur,
            frequency_per_shift=freq,
            operators_affected=parse_operators(utt),
            shift=shift,
            observer=observer,
            operator_quote=utt,
        )
        drafts.append(Draft(obs, utt, conf, missing, it["start"]))
    return drafts


def _redact(text: str, names: tuple[str, ...]) -> str:
    for n in names:
        if n:
            text = re.sub(rf"\b{re.escape(n)}\b", "[NOMBRE]", text, flags=re.IGNORECASE)
    return text


def review_queue(drafts: list[Draft]) -> list[Draft]:
    """Los que necesitan que vuelvas al pasillo a preguntar. Ordenados para que
    la vuelta sea una sola: primero los que solo les falta un numero."""
    pend = [d for d in drafts if not d.ready]
    return sorted(pend, key=lambda d: (len(d.missing), -d.confidence))


# ---------------------------------------------------------------- whisper


@dataclass
class Transcript:
    text: str
    segments: list[dict] = field(default_factory=list)
    model: str = ""
    language: str = ""
    source: str = ""


def transcribe(
    audio_path: str | Path,
    model_id: str = DEFAULT_MODEL,
    language: str = "es",
    device: str | None = None,
    vocabulary: list[str] | None = None,
    chunk_length_s: int = 30,
) -> Transcript:
    """Transcribe un audio localmente con Whisper.

    Requiere el extra `audio`:  pip install "fde-field-kit[audio]"

    Local a proposito: el audio de un CD no sale del sitio. Ademas no hay wifi
    en los pasillos, asi que cualquier cosa que dependa de la nube se usa una
    vez y despues se vuelve a la libreta.
    """
    try:
        import torch
        from transformers import AutoProcessor, pipeline
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "transcribe() necesita torch + transformers.\n"
            '  pip install "fde-field-kit[audio]"\n'
            "Si el audio ya viene transcrito, usar draft_observations() directamente: "
            "no requiere ninguna dependencia extra."
        ) from exc

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(path)

    device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if str(device).startswith("cuda") else torch.float32

    asr = pipeline(
        "automatic-speech-recognition",
        model=model_id,
        torch_dtype=dtype,
        device=device,
        chunk_length_s=chunk_length_s,
    )

    gen_kwargs: dict = {"language": language, "task": "transcribe"}
    vocab = vocabulary if vocabulary is not None else WAREHOUSE_VOCAB
    if vocab:
        # El prompt inicial es lo que hace que 'hueco', 'ola' y 'pistoleo' se
        # transcriban como terminos de bodega y no como palabras sueltas.
        try:
            processor = AutoProcessor.from_pretrained(model_id)
            gen_kwargs["prompt_ids"] = processor.get_prompt_ids(
                ", ".join(vocab), return_tensors="pt"
            ).to(device)
            gen_kwargs["prompt_condition_type"] = "first-segment"
        except Exception:  # pragma: no cover - la transcripcion vale mas que el prompt
            pass

    raw = asr(str(path), return_timestamps=True, generate_kwargs=gen_kwargs)

    segments = [
        {
            "start": (c.get("timestamp") or (None, None))[0],
            "end": (c.get("timestamp") or (None, None))[1],
            "text": c.get("text", "").strip(),
        }
        for c in raw.get("chunks", [])
    ]
    return Transcript(
        text=raw.get("text", "").strip(),
        segments=segments,
        model=model_id,
        language=language,
        source=str(path),
    )


def transcribe_to_session(
    audio_path: str | Path,
    session,
    area: str = "",
    shift: str = "",
    anonymize: tuple[str, ...] = (),
    only_ready: bool = True,
    **kwargs,
) -> tuple[list[Draft], list[Draft]]:
    """Transcribe, arma los borradores y agrega a la sesion los que estan
    completos. Devuelve (agregados, pendientes de revision).

    `only_ready=True` por defecto: una observacion sin duracion ni frecuencia no
    entra al Pareto, y meterla igual solo ensucia el analisis con anecdotas.
    """
    tr = transcribe(audio_path, **kwargs)
    drafts = draft_observations(
        tr.segments or tr.text,
        area=area,
        shift=shift,
        observer=getattr(session, "observer", ""),
        anonymize=anonymize,
    )
    added = []
    for d in drafts:
        if d.ready or not only_ready:
            session.add(d.observation)
            added.append(d)
    return added, review_queue(drafts)
