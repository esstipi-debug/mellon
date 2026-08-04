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
#
# CADA TERMINO VA EN LAS DOS PERSONAS. El lexico nacio escrito entero en primera
# ('camino', 'busco', 'espero', 'traslado'), asumiendo que el transcrito es el
# operador contando lo que le pasa. Pero `draft_observations` tambien recibe al
# FDE narrando a su propio telefono lo que VE, y ahi la forma es 'el picker
# camina'. Medido: de 36 formas de tercera persona, 26 no clasificaban, y
# MOVIMIENTO y TRANSPORTE —los dos desperdicios mas frecuentes en un CD— estaban
# en cobertura CERO. No fallaba: `draft_observations` descartaba el enunciado
# entero y devolvia una lista mas corta, sin decir nada.
#
# Al agregar un termino, agregarlo conjugado en las dos. Y no hace falta cubrir
# el plural aparte: 'esperan' contiene 'espera', y el match es por substring.
#
# UN TERMINO NOMBRA UNA ACCION O UN ESTADO, NUNCA UN MODIFICADOR. 'de mas'
# (cuanto) y 'por si acaso' (por que) estuvieron aca y hubo que sacarlos: un
# modificador se pega a cualquier verbo, asi que no puede identificar ningun
# desperdicio, y como el match es por substring tampoco respeta limites de
# palabra ('de mas' vivia dentro de "desde mas"). Los dos producian confianza
# 1.0 —o sea `ready`, o sea al Pareto sin revision humana— sobre frases que no
# hablaban de ningun desperdicio. La forma segura es anclar al verbo:
# 'prepara de mas', no 'de mas'.
#
# El mismo defecto sigue vivo en otras entradas heredadas y esta medido:
# 'parado' (ESPERA) matchea dentro de "preparado", "separado", "comparado" y
# "reparado" — "el pallet ya esta preparado en el anden" da ESPERA con
# confianza 1.0. 'cola' (ESPERA) matchea el adhesivo. 'error' (DEFECTO) matchea
# "margen de error". 'doble' y 'dos veces' (SOBREPROCESO) clasifican "el rack
# doble del pasillo 4" y "el camion vino dos veces hoy". Ninguno esta arreglado
# todavia: se listan aca porque estan medidos y porque el patron es el mismo.
WASTE_LEXICON: dict[str, tuple[str, ...]] = {
    "ESPERA": (
        "espera", "esperando", "espero", "esperar", "cola", "parado",
        "detenido", "sin hacer nada", "hasta que llegue", "se cuelga", "se demora",
        "se demora el sistema", "lento el sistema", "no me llega", "quedo esperando",
    ),
    "MOVIMIENTO": (
        "busca", "buscar", "busco", "buscando", "camina", "caminar", "camino",
        "caminata", "recorre", "recorro", "va hasta", "voy hasta", "me agacho",
        "se agacha", "agacharme", "subir la escalera", "de un lado a otro",
        "da la vuelta", "dar la vuelta", "cruza el pasillo", "cruzar el pasillo",
    ),
    "DEFECTO": (
        "error", "equivocado", "equivoca", "rehace", "rehacer", "lo hago de nuevo",
        "lo hace de nuevo", "no cierra", "no calza", "se rompe", "reclamo",
        "devuelve", "devuelto", "devolucion", "mal picking", "caja chica",
        "no corresponde", "sale malo",
    ),
    # Sin 'por si acaso': es un adverbial de motivo, no un desperdicio. Se pega
    # al verbo que venga y no identifica ninguno por si solo. "Reviso de nuevo
    # por si acaso" es sobreproceso por 'reviso de nuevo'; "dejo un pallet libre
    # por si acaso" no es sobreproceso de ninguna manera, y daba SOBREPROCESO
    # con confianza 1.0. Ningun test la cubria.
    "SOBREPROCESO": (
        "dos veces", "doble", "otra vez lo mismo", "planilla aparte", "ademas anoto",
        "ademas anota", "tambien lo anoto", "tambien lo anota", "reviso de nuevo",
        "revisa de nuevo", "vuelvo a contar", "vuelve a contar",
    ),
    "TRANSPORTE": (
        "traslada", "traslado", "trasladar", "llevar hasta", "lleva el pallet",
        "llevo el pallet", "mover el pallet", "mueve el pallet", "de bodega a",
        "hasta el anden",
    ),
    "INVENTARIO": (
        "acumulado", "se acumula", "apilado", "se apila", "amontonado", "se amontona",
        "parado ahi", "se junta", "pallets esperando", "lleno de cajas",
    ),
    # Sin 'de mas' suelta: dos palabras cortas no alcanzan para una keyword por
    # substring. Matcheaba dentro de "desde mas" ("des" + "de mas"), asi que
    # "lo trae desde mas alla del pasillo 9" daba SOBREPRODUCCION con confianza
    # 1.0; y aun bien delimitada, "de mas o menos" quiere decir
    # "aproximadamente". Las formas ancladas al verbo cubren lo que importa.
    "SOBREPRODUCCION": (
        "antes de tiempo", "adelanta", "adelantado", "prepara de mas",
        "preparo de mas", "por adelantado",
    ),
    # Sin 'le dijo': es discurso referido, no reclamo. Medido, daba TALENTO con
    # confianza 1.0 —o sea `ready`, o sea al Pareto sin que nadie lo mire— sobre
    # "el supervisor le dijo que fuera al anden 3". 'yo le dije' es alguien
    # afirmando que aviso; 'le dijo' es cualquiera contando cualquier cosa.
    "TALENTO": (
        "nadie pregunta", "nadie le pregunta", "ya avise", "yo le dije",
        "nadie escucha", "nadie me hace caso", "lo vengo diciendo", "lo viene diciendo",
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


def normalize(text: str) -> str:
    """La normalizacion canonica del kit: sin acentos, en minusculas, con
    espacios colapsados.

    Es una sola definicion a proposito. Habia dos `_norm` con el mismo nombre y
    semantica distinta —esta, y una en `decide/schema.py` que colapsaba espacios
    pero NO quitaba acentos— y la segunda producia un error invisible en las dos
    direcciones: `"quizas"` se rechazaba como decision pero `"quizás"` pasaba, y
    `"a mas tardar"` valia como criterio pero `"a más tardar"` no. Los tests no
    lo veian porque todas sus cadenas estaban sin acentos.
    """
    return " ".join(strip_accents(text).lower().split())


# Alias interno historico. Se conserva porque lo usan varios modulos y renombrar
# en todos no agrega nada.
_norm = normalize


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


def _evidence(t: str, kws: tuple[str, ...]) -> int:
    """Cuenta hallazgos distintos, no keywords distintas.

    El match es por substring y eso es deliberado: el castellano pega cliticos
    ('buscar' + 'lo', 'agachar' + 'me') y con limites de palabra `\\b` la frase
    "tengo que ir a buscarlo al otro pasillo" deja de ser MOVIMIENTO. El
    substring hace de lematizador pobre y hay que conservarlo.

    Lo que no se puede conservar es contar dos veces el mismo tramo de texto.
    Si el lexico tiene 'esperando' y 'espera', la frase "pallets esperando"
    dispara las dos por UNA aparicion y el tipo suma 2. Ese 2 inflado empata
    con los 2 hits reales de INVENTARIO y el desempate lo decide el orden de
    las claves de `WASTE_LEXICON`, que no es un criterio. Peor: la confianza es
    `(top - second) / top`, asi que un top inflado corre el umbral de 0.5 que
    decide si un humano tiene que confirmar.

    Una keyword contenida en otra que tambien matcheo es la misma evidencia
    vista dos veces, no dos evidencias. Se cuenta una sola.
    """
    hits = {kw for kw in kws if kw in t}
    return sum(1 for a in hits if not any(a in b for b in hits if b != a))


def _ranked(text: str) -> list[tuple[str, int]]:
    """Los 8 tipos ordenados por evidencia, de mas a menos."""
    t = _norm(text)
    scores = {waste: _evidence(t, kws) for waste, kws in WASTE_LEXICON.items()}
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def waste_candidates(text: str) -> tuple[str, ...]:
    """Los tipos que empatan en el tope. Vacio si no hay evidencia de ninguno.

    Uno solo es el caso normal. Dos o mas es un empate real, y hay que tratarlo
    como tal: `sorted` es estable, asi que devolver `ranked[0]` en un empate
    devuelve el tipo que este primero en `WASTE_LEXICON` — o sea, el que
    aparezca antes en el archivo. Verificado moviendo TRANSPORTE al principio
    del diccionario: "mueve el pallet dos veces" pasaba de SOBREPROCESO a
    TRANSPORTE sin que cambiara ni el texto ni el lexico.

    El empate no suele ser un defecto del lexico: mover un pallet dos veces ES
    transporte y ES reproceso. Lo que estaba mal no era empatar, era resolverlo
    en silencio y por un criterio que no es un criterio.
    """
    ranked = _ranked(text)
    top_n = ranked[0][1]
    if top_n == 0:
        return ()
    return tuple(w for w, n in ranked if n == top_n)


def classify_waste(text: str) -> tuple[str | None, float]:
    """Devuelve (tipo, confianza). Confianza = margen del ganador sobre el
    segundo, normalizado. Bajo 0.5 el humano tiene que confirmar — clasificar
    mal un desperdicio manda el Pareto a la basura.

    En un empate esto devuelve uno de los empatados y confianza 0.0. La
    confianza es honesta —no hay margen— pero el tipo es arbitrario: para saber
    contra que empato hay que usar `waste_candidates`. `draft_observations` la
    usa y pone `waste_type` en `missing`, que es lo que hace que un empate no
    se pueda colar al Pareto como si fuera una clasificacion.
    """
    ranked = _ranked(text)
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
    # Los tipos que empataron en el tope, cuando fue mas de uno. Vacio en el
    # caso normal. `observation.waste_type` lleva uno de estos por obligacion
    # del schema —que exige un tipo valido— pero cual de ellos es arbitrario,
    # y por eso `waste_type` va tambien en `missing`.
    tied_wastes: tuple[str, ...] = ()

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
            "tied_wastes": list(self.tied_wastes),
        }


# Bajo esto un fragmento no es un enunciado: es 'Si.', 'Ya.', un carraspeo que
# Whisper puntuo. Se descartan, pero se cuentan — ver `_cobertura`.
MIN_CARACTERES_ENUNCIADO = 12


def _split_crudo(text: str) -> list[str]:
    """Todos los fragmentos, incluidos los que no llegan al minimo.

    Existe separado de `split_utterances` porque la cobertura necesita el
    denominador: cuantos fragmentos habia ANTES de filtrar. Sin eso, el
    descarte por largo es un segundo agujero silencioso corriente arriba del
    que se esta tapando, y la aritmetica de `_cobertura` no cierra.
    """
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]


def split_utterances(text: str) -> list[str]:
    """Parte el transcrito en enunciados. Whisper puntua razonablemente; cuando
    no, se corta por pausas largas marcadas con coma y conector."""
    return [p for p in _split_crudo(text) if len(p) > MIN_CARACTERES_ENUNCIADO]


def _cobertura(enunciados: int, muy_cortos: int, sin_desperdicio: list[str], borradores: int) -> dict:
    """Todo enunciado contado. La suma tiene que cerrar contra el total.

    Mismo patron y misma razon que `ChatLog.cobertura()` en `decide/chat.py`:
    la defensa contra el parser que dice "9 observaciones", el humano cree que
    son todas, y las 3 que se cayeron no dejan rastro.

    Las muestras salen YA anonimizadas —se toman despues de `_redact`— porque
    declarar el descarte textual abre un canal nuevo por donde el nombre de un
    operador sale del sitio.

    Nota sobre `decide/draft.py`, que tiene esta misma forma y NO declara nada:
    ahi el silencio es deliberado y correcto, porque el marcador verbal
    ('decidimos que') es un protocolo que el facilitador controla y puede
    aprender, y no capturar nada es el feedback que se lo ensena. Aca no hay
    protocolo: el operario habla como habla y nadie va a pedirle que conjugue
    distinto para que el lexico lo entienda. El silencio no ensena, solo pierde.
    """
    n_sin = len(sin_desperdicio)
    contados = borradores + n_sin + muy_cortos
    nota = f"{borradores} de {enunciados} enunciado(s) produjeron borrador"
    if n_sin:
        nota += f", **{n_sin} SIN CLASIFICAR**"
    if muy_cortos:
        nota += f", {muy_cortos} muy corto(s)"
    return {
        "enunciados": enunciados,
        "con_borrador": borradores,
        "sin_desperdicio": n_sin,
        "muy_cortos": muy_cortos,
        # Anonimizadas. Se cortan a 5: es una pista para volver al pasillo, no
        # una segunda copia del transcrito.
        "muestras_sin_desperdicio": sin_desperdicio[:5],
        "cuadra": contados == enunciados,
        "nota": nota + ".",
    }


def draft_observations(
    text_or_segments,
    area: str = "",
    activity: str = "",
    shift: str = "",
    observer: str = "",
    shift_hours: float = SHIFT_HOURS,
    anonymize: tuple[str, ...] = (),
) -> tuple[list[Draft], dict]:
    """Convierte un transcrito en observaciones candidatas.

    Devuelve `(borradores, cobertura)`. La firma obliga a desempacar las dos
    cosas a proposito, igual que los `avisos` de `transcribe_to_session`: una
    cobertura que nadie lee es lo mismo que no tenerla, y este modulo ya tuvo
    ese problema. Antes esto devolvia solo la lista, y un enunciado que el
    lexico no entendia se descartaba sin dejar rastro.

    Acepta texto plano o la lista de segmentos de `Transcript.segments`.
    `anonymize` reemplaza nombres propios antes de que nada se persista — y eso
    incluye las muestras que salen en `cobertura`.
    """
    if isinstance(text_or_segments, str):
        crudos = [{"text": u, "start": None} for u in _split_crudo(text_or_segments)]
    else:
        crudos = [
            {"text": s.get("text", "").strip(), "start": s.get("start")}
            for s in text_or_segments
            if s.get("text", "").strip()
        ]

    items = [c for c in crudos if len(c["text"]) > MIN_CARACTERES_ENUNCIADO]
    # Contado, no derivado por resta. Con `len(crudos) - len(items)` la suma de
    # `_cobertura` cerraba SIEMPRE: cualquier enunciado que se perdiera por un
    # camino nuevo entraba callado a `muy_cortos` y `cuadra` seguia en True.
    # Verificado inyectando una fuga: el descuadre no se veia.
    muy_cortos = sum(1 for c in crudos if len(c["text"]) <= MIN_CARACTERES_ENUNCIADO)

    drafts: list[Draft] = []
    sin_desperdicio: list[str] = []
    for it in items:
        utt = _redact(it["text"], anonymize)
        waste, conf = classify_waste(utt)
        if waste is None:
            # Descartado, pero declarado. La alternativa era `continue` a secas.
            sin_desperdicio.append(utt)
            continue

        dur = parse_duration_s(utt)
        freq = parse_frequency_per_shift(utt, shift_hours)

        missing = tuple(
            k for k, v in (("duration_s", dur), ("frequency_per_shift", freq)) if v is None
        )
        # Un empate en el tope deja el tipo sin decidir, y `missing` ya es el
        # mecanismo del modulo para "esto lo tiene que poner un humano". Sin
        # esta linea el empate salia con `missing=()` y `review_queue`
        # —que ordena por `len(missing)` primero— lo ponia ANTES que un borrador
        # al que solo le faltaba la frecuencia: el mas dudoso encabezando la
        # cola con cara de completo.
        empatados = waste_candidates(utt)
        if len(empatados) > 1:
            missing = ("waste_type",) + missing
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
        drafts.append(
            Draft(
                obs,
                utt,
                conf,
                missing,
                it["start"],
                tied_wastes=empatados if len(empatados) > 1 else (),
            )
        )
    return drafts, _cobertura(len(crudos), muy_cortos, sin_desperdicio, len(drafts))


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
    # Lo que se degrado sin impedir la transcripcion. Vacio = nada que declarar.
    avisos: list[str] = field(default_factory=list)
    # None = no se pidio vocabulario; True = el prompt se aplico; False = se
    # pidio y fallo. Misma semantica de tres estados que `in_event_log`: el
    # `False` no se puede confundir con "no aplica".
    vocabulario_aplicado: bool | None = None


def _prompt_kwargs(
    model_id: str,
    vocab: list[str],
    device,
    loader=None,
) -> tuple[dict, str, bool | None]:
    """Arma el prompt inicial de Whisper. Devuelve (kwargs, aviso, aplicado).

    Capa separada de `transcribe()` para poder testear el camino degradado sin
    bajar un modelo: cargar el processor es lo unico que puede fallar aca, y es
    justo lo que hay que probar.

    El prompt no es cosmetico. Medido con whisper-tiny sobre
    `tests/data/audio_muestra.wav`: sin el, 'anden' sale 'Andem' y 'pallet' sale
    'paillet'. Por eso vale seguir sin el —una transcripcion peor sirve mas que
    ninguna— y por eso hay que DECIR que se siguio sin el. Regla dura 3.
    """
    if not vocab:
        return {}, "", None

    if loader is None:
        from transformers import AutoProcessor

        loader = AutoProcessor.from_pretrained

    try:
        processor = loader(model_id)
        prompt_ids = processor.get_prompt_ids(", ".join(vocab), return_tensors="pt")
        kwargs = {
            "prompt_ids": prompt_ids.to(device),
            "prompt_condition_type": "first-segment",
        }
    except Exception as exc:  # el modelo puede no traer processor, o no haber red
        aviso = (
            f"El vocabulario de bodega ({len(vocab)} terminos) NO se aplico: "
            f"{type(exc).__name__}: {exc}. La transcripcion sigue, pero los "
            "terminos del rubro salen peor ('anden' -> 'Andem'). "
            "Revisar antes de usarla para extraer observaciones."
        )
        return {}, aviso, False

    return kwargs, "", True


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
    # El prompt inicial es lo que hace que 'hueco', 'ola' y 'pistoleo' se
    # transcriban como terminos de bodega y no como palabras sueltas.
    prompt, aviso, vocab_aplicado = _prompt_kwargs(
        model_id, vocab, device, loader=AutoProcessor.from_pretrained
    )
    gen_kwargs.update(prompt)

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
        avisos=[aviso] if aviso else [],
        vocabulario_aplicado=vocab_aplicado,
    )


def transcribe_to_session(
    audio_path: str | Path,
    session,
    area: str = "",
    shift: str = "",
    anonymize: tuple[str, ...] = (),
    only_ready: bool = True,
    **kwargs,
) -> tuple[list[Draft], list[Draft], list[str], dict]:
    """Transcribe, arma los borradores y agrega a la sesion los que estan
    completos. Devuelve (agregados, pendientes de revision, avisos, cobertura).

    `only_ready=True` por defecto: una observacion sin duracion ni frecuencia no
    entra al Pareto, y meterla igual solo ensucia el analisis con anecdotas.

    Los `avisos` vienen del `Transcript` y hay que mostrarlos: si el vocabulario
    no se aplico, TODOS estos borradores salieron de un texto degradado. Que la
    firma obligue a desempacarlos es a proposito — un `tr.avisos` que nadie lee
    es lo mismo que no tenerlo.

    La `cobertura` esta por la misma razon y hay que mostrarla igual: dice
    cuantos enunciados del audio NO produjeron nada. Sin ella, "se agregaron 9
    observaciones" se lee como "el audio tenia 9 observaciones", que es una
    afirmacion que esta funcion no puede hacer.
    """
    tr = transcribe(audio_path, **kwargs)
    drafts, cobertura = draft_observations(
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
    return added, review_queue(drafts), list(tr.avisos), cobertura
