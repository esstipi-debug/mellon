"""Ingesta del canal asincronico: exports de WhatsApp y de Teams.

Es el canal donde se toma la mayoria de las decisiones operativas de un CD, y el
texto de chat es **mejor insumo que el habla**: sin ASR, sin diarizacion, con
autor resuelto y timestamp exacto. Desperdiciar esa ventaja alimentando la linea
cruda al parser de transcriptos seria absurdo — y ademas esta medido que rompe:
`_find_date` toma la PRIMERA fecha del texto, asi que la cabecera del mensaje
eclipsa el plazo real que viene despues ("antes del 30/9" no se ve nunca) y de
paso se convertia EN el plazo.

Por eso este modulo devuelve mensajes ESTRUCTURADOS y `draft_decisions` recibe
solo el cuerpo.

Tres reglas de diseno, las tres salidas de inspeccionar exports reales byte a
byte (seis archivos, 11.005 lineas) mas CLDR como fuente de los formatos por
locale:

  1. **Un solo detector de cabecera.** La continuacion multilinea se define por
     NEGACION de ese detector, nunca con una regex propia: dos regex que tienen
     que ser complementarias se desincronizan, y entonces las lineas caen en el
     medio y desaparecen. En un export iOS real las continuaciones son el 15,9%
     de las lineas (347 de 2.189): no es un caso borde.
  2. **El orden dia/mes se INFIERE del archivo entero**, no se supone. Linea a
     linea es indecidible —`3/6` es 3-jun o 6-mar segun la region del telefono
     que exporto— pero sobre el export completo casi siempre hay una fecha con
     un componente mayor a 12 que lo resuelve. Cuando no la hay, se dice.
  3. **Toda linea queda contada.** `ChatLog.cobertura()` cierra la aritmetica:
     mensajes + continuaciones + sistema + sin_parsear == total. El modo de falla
     que importa no es que el parser reviente: es que diga "148 mensajes" cuando
     habia 190 y nadie tenga como saberlo.

Lo que este modulo NO hace, a proposito: no crea decisiones. Produce mensajes;
`draft_decisions` produce borradores; un humano promueve. El canal asincronico
alimenta la cola de revision, no el registro.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

# Caracteres invisibles que iOS y Android meten en los exports. Sacarlos ANTES
# de cualquier match: son la causa numero uno de que una regex correcta no
# matchee nada y el parser devuelva cero mensajes sin un solo error.
#
#   U+200E LRM / U+200F RLM   iOS los pone al inicio de linea y despues de
#                             "Autor: " en adjuntos y mensajes de sistema
#   U+FEFF BOM                Windows
#   U+202A LRE / U+202C PDF   envuelven un autor que no esta en la libreta
#   U+00A0 / U+202F           espacios duros: U+202F es el que separa el
#                             meridiano desde CLDR 42 (oct-2022)
_INVISIBLES = dict.fromkeys(
    (0x200E, 0x200F, 0xFEFF, 0x202A, 0x202B, 0x202C, 0x2066, 0x2067, 0x2068, 0x2069), None
)
_ESPACIOS = {0x00A0: " ", 0x202F: " ", 0x2009: " "}

# El meridiano tiene al menos cuatro grafias segun locale y version de CLDR, y
# ninguna la elige el usuario: "pm", "PM", "p.m.", "p. m.".
_MERIDIANO = r"(?:[ap]\.?\s?m\.?)"

# EL detector de cabecera. Uno solo, y todo lo demas se define contra el.
#
# Cubre las dos familias verificadas en exports reales:
#   iOS      [D/M/YY, HH:MM:SS] Autor: texto      (con o sin segundos)
#   Android  D/M/YYYY, HH:MM p. m. - Autor: texto (con o sin meridiano)
# y los separadores de fecha "/", "-" y "." — es-CL usa GUIONES (dd-MM-yy).
_CABECERA = re.compile(
    r"^\[?"
    r"(?P<d1>\d{1,4})[/.\-](?P<d2>\d{1,2})[/.\-](?P<d3>\d{2,4})"
    r"[,]?\s+"
    r"(?P<hora>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)"
    r"(?:\s*(?P<meridiano>" + _MERIDIANO + r"))?"
    r"\s*(?:\]|-)\s*"
    r"(?:(?P<autor>[^:]{1,80}):\s)?"
    r"(?P<texto>.*)$",
    re.IGNORECASE,
)

# Deteccion de SOSPECHA de cabecera. Deliberadamente mas laxa que `_CABECERA`, y
# su unico trabajo es distinguir dos cosas que la negacion sola confunde:
#
#   - una continuacion de verdad ("antes del 30/9", el pie de una foto);
#   - una linea que INTENTA ser una cabecera en un formato que no cubrimos.
#
# Sin esto, la segunda se pega en silencio al mensaje anterior y la cobertura
# dice `cuadra=True`. Medido con "02/08/2026 14:35 B: texto" — sin coma y sin
# " - ", formatos que existen: se comio la linea entera sin un aviso.
#
# NO es la segunda regex que la investigacion advierte que se desincroniza: esa
# advertencia es sobre escribir un detector de CONTINUACION, que tendria que ser
# el complemento exacto del de cabecera. Este no afirma nunca que una linea SEA
# una cabecera — solo que no puede ser una continuacion, y por lo tanto que hay
# que reportarla.
_PARECE_CABECERA = re.compile(r"^\[?\s*\d{1,4}[/.\-]\d{1,2}[/.\-]\d{2,4}[\s,]")

# Lineas que NO son mensajes de nadie aunque tengan cabecera y autor. La de
# cifrado es la mas cara: en iOS 1:1 viene ATRIBUIDA a una persona real, asi que
# sin esto cada conteo por autor le suma un mensaje que nunca escribio.
_NO_ES_MENSAJE = (
    "los mensajes y las llamadas estan cifrados",
    "messages and calls are end-to-end encrypted",
    "se unio usando el enlace",
    "joined using this group",
    "cambio el asunto",
    "changed the subject",
    "cambio el icono",
    "changed this group",
    "salio del grupo",
    "anadio a",
    "elimino este mensaje",
    "this message was deleted",
    "se elimino este mensaje",
)
# Adjuntos sin texto propio: el mensaje existio pero su contenido no esta.
_ADJUNTOS = (
    "multimedia omitido", "media omitted", "imagen omitida", "image omitted",
    "video omitido", "video omitted", "audio omitido", "audio omitted",
    "sticker omitido", "sticker omitted", "gif omitido", "gif omitted",
    "archivo adjunto", "file attached", "documento omitido", "document omitted",
)


def _limpiar(linea: str) -> str:
    return linea.translate(_INVISIBLES).translate(_ESPACIOS).rstrip("\r\n").strip()


def _plano(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


@dataclass(frozen=True)
class ChatMessage:
    """Un mensaje. `linea` es el numero de linea del archivo, para poder volver
    al original — el analogo del `t_start` de un `Utterance`."""

    fecha: date
    hora: str
    autor: str
    texto: str
    linea: int

    @property
    def es_adjunto(self) -> bool:
        p = _plano(self.texto)
        return any(a in p for a in _ADJUNTOS)


@dataclass(frozen=True)
class ChatLog:
    """El export parseado, **con su aritmetica cerrada**."""

    mensajes: tuple[ChatMessage, ...]
    lineas_totales: int
    lineas_continuacion: int
    lineas_sistema: int
    lineas_sin_parsear: tuple[tuple[int, str], ...]
    dia_primero: bool
    orden_inferido_de: str

    @property
    def autores(self) -> tuple[str, ...]:
        """El roster de la ventana. Es el conjunto de quienes ESCRIBIERON: no hay
        lista de invitados en un grupo de WhatsApp, y derivarlo de los autores es
        lo unico que no inventa gente."""
        vistos: dict[str, None] = {}
        for m in self.mensajes:
            vistos.setdefault(m.autor, None)
        return tuple(vistos)

    def cobertura(self) -> dict:
        """Toda linea contada. La suma tiene que cerrar contra el total.

        Es la unica defensa contra el modo de falla que importa: el parser dice
        "148 mensajes", el humano cree que son todos, y las 42 que se cayeron no
        dejan rastro.
        """
        n_msg = len(self.mensajes)
        sin = len(self.lineas_sin_parsear)
        contadas = n_msg + self.lineas_continuacion + self.lineas_sistema + sin
        return {
            "lineas_totales": self.lineas_totales,
            "mensajes": n_msg,
            "continuaciones": self.lineas_continuacion,
            "sistema_o_adjunto": self.lineas_sistema,
            "sin_parsear": sin,
            "muestras_sin_parsear": self.lineas_sin_parsear[:5],
            "cuadra": contadas == self.lineas_totales,
            "orden_fecha": ("dia primero (dd/mm)" if self.dia_primero else "mes primero (mm/dd)"),
            "orden_inferido_de": self.orden_inferido_de,
            "nota": (
                f"{n_msg} mensaje(s) de {self.lineas_totales} linea(s). "
                f"{self.lineas_continuacion} continuacion(es), {self.lineas_sistema} de "
                f"sistema o adjunto"
                + (f", **{sin} SIN PARSEAR**" if sin else "")
                + f". Fechas leidas como {'dd/mm' if self.dia_primero else 'mm/dd'}: "
                + self.orden_inferido_de
            ),
        }


def _inferir_dia_primero(pares: list[tuple[int, int]]) -> tuple[bool, str]:
    """Decide el orden mirando el export ENTERO.

    Linea a linea es indecidible. Pero en un archivo de cientos de mensajes casi
    siempre hay una fecha con un componente mayor a 12 —un dia 13 o mas— y eso
    lo resuelve para todo el archivo. Cuando no la hay, se asume dd/mm (Chile) y
    **se dice que fue un supuesto**, que es la diferencia entre leer bien y
    tener suerte.
    """
    d1_grande = any(a > 12 for a, _ in pares)
    d2_grande = any(b > 12 for _, b in pares)
    if d1_grande and not d2_grande:
        return True, "inferido del archivo: hay una fecha con primer componente > 12"
    if d2_grande and not d1_grande:
        return False, "inferido del archivo: hay una fecha con segundo componente > 12"
    if d1_grande and d2_grande:
        return True, (
            "CONTRADICTORIO: hay fechas con el primer componente > 12 y otras con el "
            "segundo. El export mezcla dos formatos (pasa cuando se pegan exports de "
            "telefonos con regiones distintas). Se leyo dd/mm; revisar a mano."
        )
    return True, (
        "SUPUESTO, no inferido: ninguna fecha del archivo tiene un componente > 12, "
        "asi que el orden es indecidible. Se asumio dd/mm (Chile)."
    )


def parse_chat(texto: str, dia_primero: bool | None = None) -> ChatLog:
    """Export de chat -> mensajes estructurados.

    `dia_primero` fuerza el orden cuando se conoce la region del telefono que
    exporto. Si se omite se infiere del archivo entero.
    """
    lineas = texto.splitlines()
    crudos: list[dict] = []
    continuacion = 0
    sin_parsear: list[tuple[int, str]] = []

    for i, cruda in enumerate(lineas, 1):
        linea = _limpiar(cruda)
        if not linea:
            continuacion += 1  # una linea en blanco pertenece al mensaje anterior
            continue
        m = _CABECERA.match(linea)
        if not m:
            # Continuacion, POR NEGACION del unico detector. Salvo que la linea
            # PAREZCA una cabecera: ahi no es continuacion, es un formato que no
            # cubrimos, y pegarla al mensaje anterior seria comersela en
            # silencio con la cobertura diciendo que todo cuadra.
            if _PARECE_CABECERA.match(linea):
                sin_parsear.append((i, linea[:80]))
            elif crudos:
                crudos[-1]["texto"] += "\n" + linea
                continuacion += 1
            else:
                sin_parsear.append((i, linea[:80]))
            continue
        crudos.append({
            "d1": int(m["d1"]), "d2": int(m["d2"]), "d3": int(m["d3"]),
            "hora": m["hora"], "meridiano": (m["meridiano"] or "").lower(),
            "autor": (m["autor"] or "").strip(), "texto": m["texto"].strip(),
            "linea": i,
        })

    if dia_primero is None:
        dia_primero, origen = _inferir_dia_primero([(c["d1"], c["d2"]) for c in crudos])
    else:
        origen = f"declarado por quien llamo: {'dd/mm' if dia_primero else 'mm/dd'}"

    mensajes: list[ChatMessage] = []
    sistema = 0
    for c in crudos:
        d, mo = (c["d1"], c["d2"]) if dia_primero else (c["d2"], c["d1"])
        y = c["d3"] + 2000 if c["d3"] < 100 else c["d3"]
        try:
            fecha = date(y, mo, d)
        except ValueError:
            sin_parsear.append((c["linea"], f"fecha invalida: {c['d1']}/{c['d2']}/{c['d3']}"))
            continue

        p = _plano(c["texto"])
        # Sin autor -> es de sistema por construccion. Con autor tambien puede
        # serlo: iOS atribuye la notificacion de cifrado a una persona real.
        if not c["autor"] or any(s in p for s in _NO_ES_MENSAJE):
            sistema += 1
            continue
        if any(a in p for a in _ADJUNTOS) and len(p) < 60:
            sistema += 1  # adjunto sin texto propio: el mensaje existio, el contenido no
            continue

        mensajes.append(ChatMessage(
            fecha=fecha, hora=c["hora"], autor=c["autor"], texto=c["texto"], linea=c["linea"],
        ))

    return ChatLog(
        mensajes=tuple(mensajes),
        lineas_totales=len(lineas),
        lineas_continuacion=continuacion,
        lineas_sistema=sistema,
        lineas_sin_parsear=tuple(sin_parsear),
        dia_primero=dia_primero,
        orden_inferido_de=origen,
    )


def ingest_chat(store, texto: str, ventana_id: str, consent, today: date,
                dia_primero: bool | None = None, force: bool = False) -> dict:
    """Export de chat -> ventana registrada + borradores en la cola.

    NO crea decisiones. Produce mensajes, `draft_decisions` produce borradores y
    un humano promueve: el canal asincronico alimenta la cola de revision, no el
    registro. Es la regla de precedencia del diseno — la evidencia mas reciente
    gana DESPUES de que alguien la mire, no antes.

    Dos decisiones que no son obvias:

    **Se alimenta el CUERPO, no la linea.** La cabecera se queda afuera porque
    `_find_date` toma la primera fecha del texto: con la linea cruda, el
    timestamp del mensaje eclipsa el plazo real que viene despues ("antes del
    30/9" no se ve) y ademas se convertia EN el plazo. Medido.

    **El autor del mensaje NO es el dueno.** "Marcela: Rodrigo se compromete a
    mover 200 ubicaciones" tiene autor Marcela y dueno Rodrigo. Usar el autor
    como dueno seria el bug de un texto alimentando dos campos, otra vez, y en
    el campo que constituye la obligacion. El autor es procedencia, y va como
    nota del borrador.
    """
    from .draft import DraftStore, draft_decisions
    from .schema import Meeting

    log = parse_chat(texto, dia_primero=dia_primero)
    cob = log.cobertura()
    if not log.mensajes:
        return {"ventana": ventana_id, "mensajes": 0, "borradores": 0, "cobertura": cob}

    m = Meeting(
        id=ventana_id,
        date=min(x.fecha for x in log.mensajes),
        roster=log.autores,          # el roster de una ventana son quienes escribieron
        consent=consent,
        canal="ASINCRONICO",
        scope="",
    )
    store.add_meeting(m, force=force, overwrite=force)

    # Un item por mensaje, con el cuerpo limpio. `start=None` es honesto: un
    # chat no tiene offset de audio, y fingir uno haria que `mmss()` imprima un
    # minuto que no existe.
    items = [{"text": x.texto, "start": None} for x in log.mensajes]
    drafts = draft_decisions(items, roster=log.autores, meeting_date=m.date,
                             meeting_id=ventana_id)

    # Procedencia: quien lo escribio y en que linea del export. Sin esto, un
    # borrador de chat es indistinguible de uno de sala en la cola de revision.
    por_texto = {x.texto: x for x in log.mensajes}
    for d in drafts:
        origen = por_texto.get(d.utterance)
        if origen:
            d.notes = tuple(d.notes) + (
                f"de chat: {origen.autor}, {origen.fecha.isoformat()} {origen.hora} "
                f"(linea {origen.linea} del export)",
            )

    DraftStore(store.root, ventana_id).append(drafts)
    return {
        "ventana": ventana_id,
        "mensajes": len(log.mensajes),
        "borradores": len(drafts),
        "autores": log.autores,
        "cobertura": cob,
        "nota": (
            f"{len(drafts)} borrador(es) en la cola de revision de '{ventana_id}'. "
            "Ninguno entra al registro sin que un humano lo promueva: una decision "
            "de chat no supersede a una de sala por ser mas reciente."
        ),
    }
