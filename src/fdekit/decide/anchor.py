"""El puente entero, en un archivo corto.

`find_declaration` de Serena te lleva a la definicion. Aca la definicion se
**copia** al punto de uso en vez de enlazarse, y esa diferencia es deliberada:
la fuente tiene fecha de vencimiento. Un puntero a un recurso con politica de
retencion es un puntero colgante por diseno.

Lo que se congela: la cita literal (<=500 chars, pasada por `_redact`), el
`t_start`/`t_end` para poder ir a escuchar el minuto, y el `sha256` del
transcripto para poder decir despues si la fuente sigue siendo la misma.

El tope de 500 caracteres no es arbitrario: una cita larga no se revisa, y una
cita que no se revisa no cumple su unica funcion, que es dejar que un humano
verifique que el sistema entendio bien.
"""

from __future__ import annotations

from ..gemba.transcribe import _redact
from .schema import Anchor
from .transcript import TranscriptStore, Utterance, mmss

MAX_CITA = 500


def freeze(
    store: TranscriptStore,
    idx: int,
    anonymize: tuple[str, ...] = (),
    before: int = 0,
    after: int = 0,
) -> Anchor:
    """Congela la cita del enunciado `idx` (opcionalmente con vecinos).

    `anonymize` se aplica **contra el directorio completo de la cuenta**, no
    solo contra el roster de la sesion. El tercero mencionado —"el problema es
    que Fabian no da abasto"— no estuvo, no consintio, y su nombre quedaria en
    un registro versionado que sobrevive al proyecto.
    """
    utts = store.load()
    if not utts or idx < 0 or idx >= len(utts):
        raise IndexError(f"enunciado {idx} fuera del transcripto de {store.meeting_id}")

    ventana = utts[max(0, idx - before) : idx + after + 1]
    texto = " ".join(u.text for u in ventana).strip()
    texto = _redact(texto, anonymize)
    if len(texto) > MAX_CITA:
        texto = texto[: MAX_CITA - 1].rstrip() + "…"

    return Anchor(
        meeting_id=store.meeting_id,
        t_start=ventana[0].t_start,
        t_end=ventana[-1].t_end,
        cita_congelada=texto,
        transcript_sha256=store.sha256(),
        estado_fuente="VIVA",
    )


def verify(anchor: Anchor, store: TranscriptStore) -> tuple[bool, str]:
    """Sigue siendo la misma fuente?

    Tres respuestas posibles, y las tres importan: intacta, fuente cambiada
    (alguien reproceso el audio), o fuente borrada por retencion. En los tres
    casos la cita sigue sirviendo — esa es la gracia de haberla copiado — pero
    conviene saber en cual estamos antes de usarla como evidencia.
    """
    if not anchor.transcript_sha256:
        return False, "el ancla no guardo hash: no es verificable"
    if not store.exists():
        return False, "la fuente ya no existe (retencion): la cita sobrevive, el audio no"
    actual = store.sha256()
    if actual == anchor.transcript_sha256:
        return True, ""
    return False, f"la fuente cambio (hash {actual[:8]} != {anchor.transcript_sha256[:8]})"


def cite(anchor: Anchor) -> str:
    """La cita como se lee en una reunion."""
    if anchor.empty:
        return ""
    if anchor.t_start is None:
        return f'"{anchor.cita_congelada}" — {anchor.meeting_id}'
    return (
        f'"{anchor.cita_congelada}" — {anchor.meeting_id} '
        f"{mmss(anchor.t_start)}-{mmss(anchor.t_end)}"
    )


def find_utterance(store: TranscriptStore, needle: str) -> int:
    """Indice del primer enunciado que contiene el texto. Devuelve -1 si no lo
    encuentra: buscar el enunciado equivocado seria peor que no anclar."""
    from ..gemba.transcribe import _norm

    objetivo = _norm(needle)[:80]
    for u in store.load():
        if objetivo and objetivo in _norm(u.text):
            return u.idx
    return -1
