"""El canal HABLADA: log de enunciados con tiempo, y su hash.

Propiedades opuestas a las del canal DECIDIDA, y por eso vive aparte:

    DECIDIDA   bajo volumen, alta densidad, direccionable, versionable,
               con dueno y estado, diffeable.        -> es codigo fuente, va a git
    HABLADA    alto volumen, baja densidad, no direccionable, efimera,
               sin dueno, irrepetible.               -> es un log de ejecucion

`Utterance` NO es una entidad navegable, a proposito. Es un ancla. La navegacion
va siempre DECIDIDA -> HABLADA, nunca al reves. Hacer navegable la transcripcion
produce miles de nodos vagos que nadie consulta dos veces, y multiplica por diez
la superficie donde el sistema puede resolver mal.

Retencion: el canal HABLADA tiene fecha de vencimiento y el DECIDIDA no. Por eso
la cita se **copia** al momento de confirmar y no se enlaza — un puntero a un
recurso con politica de retencion es un puntero colgante por diseno.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .schema import profile_of


@dataclass
class Utterance:
    idx: int
    text: str
    t_start: float | None = None
    t_end: float | None = None
    speaker_hint: str = ""

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def mmss(seconds: float | None) -> str:
    """El formato con el que se cita en una reunion. `why()` lo devuelve para
    que alguien pueda ir a escuchar el minuto exacto."""
    if seconds is None:
        return "--:--"
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


class RecordingNotAllowed(PermissionError):
    """El canal HABLADA se niega a escribir. No es un warning: escribir habla
    textual sin base para hacerlo no se puede deshacer, y en un registro
    versionado sobrevive al proyecto."""


class TranscriptStore:
    """JSONL append-only por reunion, mas el hash del contenido.

    El hash es lo que permite decir, seis meses despues, si la cita congelada
    todavia corresponde a la fuente o si la fuente cambio. Sin eso, una cita es
    una afirmacion sin respaldo.
    """

    def __init__(self, root: str | Path, meeting_id: str):
        self.root = Path(root)
        self.meeting_id = meeting_id
        self.path = self.root / "hablada" / f"{meeting_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- escritura

    def meeting(self):
        """La reunion de la que este transcripto es el canal HABLADA.

        Se lee del disco en vez de recibirse por parametro **a proposito**. Un
        guardia que depende de que el llamador pase el dato se esquiva sin
        querer: el chequeo de `recording_allowed` vivia en `cli.py:248`, dentro
        del `else` de `if a.text`, asi que la rama `--text` y todo `cmd_draft`
        escribian habla textual sin preguntar nada. Reproducido con un 1:1 de
        desempeno sobre un tercero.
        """
        from .store import DecideStore

        try:
            return DecideStore(self.root).get_meeting(self.meeting_id)
        except Exception:
            return None

    def _guard(self) -> None:
        """El unico porton de escritura del canal HABLADA.

        `ingest_text` e `ingest_segments` pasan los dos por `write`, asi que
        alcanza con cerrar aca. Una ruta nueva que escriba habla tiene que pasar
        por el mismo lugar o no escribe.
        """
        m = self.meeting()
        if m is None:
            raise RecordingNotAllowed(
                f"no hay reunion registrada con id '{self.meeting_id}': no existe "
                "consentimiento contra el cual escribir habla textual. Registrar la "
                "reunion primero (`decide meeting`)."
            )
        perfil = profile_of(m.clase)
        if not perfil.recording_allowed:
            raise RecordingNotAllowed(
                f"la clase {m.clase} no admite canal HABLADA: {perfil.nota}. "
                "El registro DECIDIDA de esta sesion se escribe a mano con "
                "`decide add`, despues de la reunion."
            )
        if not m.consent.recording_allowed:
            raise RecordingNotAllowed(
                f"la reunion '{self.meeting_id}' no tiene consentimiento para grabar "
                f"(base declarada: {m.consent.basis or 'ninguna'}). Es la unica pieza "
                "de cumplimiento que no se puede retrofitear."
            )

    def write(self, utterances: list[Utterance], force: bool = False) -> str:
        if not force:
            self._guard()
        self.path.write_text(
            "\n".join(json.dumps(u.to_dict(), ensure_ascii=False) for u in utterances) + "\n",
            encoding="utf-8",
        )
        return self.sha256()

    def ingest_text(self, text: str, force: bool = False) -> list[Utterance]:
        """Texto plano (transcript nativo de Teams/Meet). Sin timestamps: el
        ancla va a quedar sin `mm:ss` y eso se dice, no se finge.

        `force` saltea el guardia de consentimiento. Existe para dos casos
        legitimos —un test del parseo, y un archivo escrito antes de que el
        guardia existiera— y es explicito a proposito: el bug era justamente que
        esta ruta escribia habla textual sin que nadie tuviera que pedirlo.
        """
        import re

        partes = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
        utts = [Utterance(idx=i, text=p) for i, p in enumerate(partes)]
        self.write(utts, force=force)
        return utts

    def ingest_segments(self, segments: list[dict], force: bool = False) -> list[Utterance]:
        """Segmentos de Whisper: traen `start`/`end`, asi que el ancla si queda
        con minuto. Ver `ingest_text` sobre `force`."""
        utts = [
            Utterance(
                idx=i,
                text=(s.get("text") or "").strip(),
                t_start=s.get("start"),
                t_end=s.get("end"),
            )
            for i, s in enumerate(segments)
            if (s.get("text") or "").strip()
        ]
        self.write(utts, force=force)
        return utts

    # -------------------------------------------------------------- lectura

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> list[Utterance]:
        if not self.path.exists():
            return []
        return [
            Utterance(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def sha256(self) -> str:
        if not self.path.exists():
            return ""
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def window(self, idx: int, before: int = 1, after: int = 1) -> list[Utterance]:
        """Vecindad de un enunciado. Presupuesto acotado: el agente nunca carga
        el transcripto entero — resuelve el simbolo y trae solo lo que lo
        referencia. Un transcripto de 60 min son ~9k tokens y una serie de 20
        reuniones son ~180k: inmanejable de otra forma."""
        utts = self.load()
        lo = max(0, idx - before)
        return utts[lo : idx + after + 1]

    # ------------------------------------------------------------ retencion

    @property
    def lapida(self) -> Path:
        """La constancia de destruccion. Versionada, a diferencia del habla."""
        return self.root / "hablada" / f"{self.meeting_id}.purgado.json"

    def purge(self, today: date, retention_days: int, desde: date) -> bool:
        """Borra el canal HABLADA vencido y deja constancia. El DECIDIDA no se
        toca: sobrevive porque la cita fue copiada, no enlazada.

        En Chile la Ley 21.719 rige desde el 1-dic-2026 y exige politica de
        retencion declarada.

        `desde` es **obligatorio** y es la fecha de la reunion. Antes se usaba el
        `mtime` del archivo, y eso hacia que la politica no venciera nunca: un
        `git clone` o un `checkout` reescriben los mtimes con la fecha del
        checkout. Reproducido — una reunion de enero de 2025 con retencion de 90
        dias, consultada en agosto de 2026, devolvia `False`. El reloj de la
        retencion es cuando ocurrio la conversacion, no cuando alguien toco el
        archivo.

        La lapida atestigua la **destruccion de algo que existia**. Si no habia
        transcripto no hay nada que atestiguar, y devolver True ahi tenia dos
        consecuencias malas: `tick` marcaba como purgada cada sesion vencida que
        nunca tuvo audio —cientos de lapidas vacias que esconden las de verdad—
        y reportaba cambios donde no los hubo.

        La pregunta "esto se purgo o nunca se grabo" la contesta la EXISTENCIA
        de la lapida, que es justamente lo que se pierde si se escribe siempre.
        """
        if not self.path.exists():
            return False
        if today - desde <= timedelta(days=retention_days):
            return False

        sha = self.sha256()
        n = len(self.load())
        self.path.unlink()
        self.lapida.parent.mkdir(parents=True, exist_ok=True)
        self.lapida.write_text(
            json.dumps(
                {
                    "meeting_id": self.meeting_id,
                    "purgado_el": today.isoformat(),
                    "reunion_del": desde.isoformat(),
                    "retencion_dias": retention_days,
                    "enunciados_destruidos": n,
                    # Prueba de QUE se destruyo sin conservarlo: coincide con el
                    # `transcript_sha256` de las anclas que lo citaban.
                    "sha256_al_purgar": sha,
                    "nota": (
                        "canal HABLADA destruido por politica de retencion. Las citas "
                        "congeladas en las anclas sobreviven porque se copiaron, no se "
                        "enlazaron; sus `estado_fuente` pasan a CADUCADA."
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return True


def transcripto_para_participantes(store, meeting_id: str) -> str:
    """El transcripto legible, para los que estuvieron (H16).

    Es el artefacto que convierte la conversacion de consentimiento de
    "queremos grabarlos" en "el transcripto queda disponible para todos". Nadie
    en el estudio de diseno menciono al participante con discapacidad auditiva,
    ni al remoto con mal audio, ni al no-hispanohablante del equipo global; para
    los tres esto es **la diferencia entre participar y asistir**.

    Cuesta cero tecnicamente y es probablemente el argumento mas fuerte que
    tiene el proyecto para que le dejen grabar. Pero solo cuenta si de verdad se
    puede ejercer: sin esta funcion, "disponible para los participantes" es una
    frase del kickoff que nadie puede reclamar.

    **No es una puerta trasera al consentimiento.** Si la sesion no autorizo
    grabar, no hay transcripto que entregar y decirlo es la respuesta correcta.
    """
    m = store.get_meeting(meeting_id)
    if not m.consent.recording_allowed:
        raise ValueError(
            f"la sesion {meeting_id} no autorizo grabar (consent.recording_allowed es "
            "False): no hay transcripto que entregar. La accesibilidad no es una puerta "
            "trasera al consentimiento."
        )

    ts = TranscriptStore(store.root, meeting_id)
    dias = m.consent.retention_days
    cab = [
        f"# Transcripto — {meeting_id} ({m.date.isoformat()})",
        "",
        "Se entrega por **accesibilidad**: para quien no escucho bien, para quien no "
        "pudo estar y para quien sigue la reunion en su segunda lengua. Es de todos "
        "los que estuvieron, no del consultor.",
        "",
        f"Participantes: {', '.join(m.roster)}.",
    ]
    if dias is not None:
        cab += [
            "",
            f"**Se destruye a los {dias} dias de la sesion**, por politica de retencion. "
            "Guardar una copia aparte rompe esa politica en silencio: lo que hay que "
            "conservar se promueve al registro de decisiones, que no vence.",
        ]

    if not ts.exists():
        motivo = (
            "El canal HABLADA de esta sesion **ya fue destruido** por politica de "
            "retencion. No es una falla: es la politica funcionando. Lo que se decidio "
            "sobrevive en el registro, porque las citas se copiaron y no se enlazaron."
            if ts.lapida.exists() else
            "No hay transcripto para esta sesion: no se grabo, o el pipeline no corrio."
        )
        return "\n".join([*cab, "", "---", "", motivo, ""])

    L = [*cab, "", "---", ""]
    for u in ts.load():
        L.append(f"**{mmss(u.t_start)}** {u.text}")
    return "\n".join(L) + "\n"


def transcribe_meeting(
    audio_path: str | Path,
    root: str | Path,
    meeting_id: str,
    vocabulary: list[str] | None = None,
    **kwargs,
) -> tuple[list[Utterance], str]:
    """Audio -> canal HABLADA, con Whisper local.

    Requiere el extra `audio`. Reusa `fdekit.gemba.transcribe.transcribe()` — la
    misma pieza que ya transcribe entrevistas de pasillo — y le suma el
    vocabulario de decisiones al prompt inicial.

    Honestidad de costo: una hora de audio de sala en CPU con `large-v3-turbo`
    son 25-45 minutos reales, no 5. Y la calidad en sala (4-8 personas, microfono
    a distancia, gente que se pisa) es sustancialmente peor que la del pasillo
    para el que se calibro `fdekit.gemba`. Implicancia de diseno: el transcripto
    sirve para anclaje y busqueda, **no para citar textual sin revision** — por
    eso la cita congelada la lee un humano al ratificar.
    """
    from ..gemba.transcribe import WAREHOUSE_VOCAB, transcribe
    from .lexicon import DECISION_VOCAB

    vocab = vocabulary if vocabulary is not None else [*DECISION_VOCAB, *WAREHOUSE_VOCAB]
    tr = transcribe(audio_path, vocabulary=vocab, **kwargs)

    store = TranscriptStore(root, meeting_id)
    utts = store.ingest_segments(tr.segments) if tr.segments else store.ingest_text(tr.text)
    return utts, store.sha256()
