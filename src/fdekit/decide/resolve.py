"""El resolutor: tres capas con cortocircuito, y la regla de empate.

Esta es la seccion donde el diseno se gana o se pierde.

Serena promete completitud porque el LSP se la garantiza: una referencia esta
*verificada por el compilador*. Nosotros no tenemos compilador. La regla que
gobierna todo lo demas:

    No prometemos resolver siempre. Prometemos no mentir nunca en silencio.

    L0  anclas duras       ID literal o herencia del punto de agenda   EXTRACTED
    L1  tabla de alias     match exacto, filtrado por scope y vigencia EXTRACTED
    L2  slots tipados      Jaccard de slots + proximidad de scope      INFERRED
        (no hay L3)

No hay BM25 ni embeddings, y no es por pereza: generan candidatos plausibles y
equivocados justo cuando todavia no hay nada que los desmienta, y esas
confirmaciones tempranas son las que envenenan la tabla para siempre. Ademas
meterian una dependencia que el `pyproject` no tiene.

Regla de empate, literal: si dos o mas candidatos empatan dentro del mismo nivel
de scope, el resultado es AMBIGUOUS y es un **error reportado**, no una
eleccion. Igual que un compilador ante una referencia ambigua. Un sistema que
adivina en silencio contamina el indice y es peor que no tener sistema.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from ..gemba.transcribe import _norm
from .parse import extract_slots
from .schema import TIER_AMBIGUOUS, TIER_EXTRACTED, TIER_INFERRED, Alias

# Un candidato de L2 necesita superar esto para existir. Bajo el umbral el
# resultado es "no se pudo resolver", que va a la cola y cuesta cinco segundos
# de humano — el modo de error barato y visible.
L2_MIN_SCORE = 0.35
# Dos candidatos dentro de este margen son un empate, no un ganador.
L2_TIE_MARGIN = 0.08

# El autor es opcional y va en el medio: `D-041`, `D041`, `D-JM-041`. Sin el
# grupo del medio, un registro multi-FDE pierde L0 entero — la capa mas barata y
# mas segura del resolutor, la unica deterministica al 100%.
_RE_ID = re.compile(r"\b([DCAQ])-?(?:([A-Za-z]{2,4})-)?(\d{1,4})\b", re.IGNORECASE)


@dataclass
class Resolution:
    symbol_id: str | None
    tier: str  # EXTRACTED | INFERRED | AMBIGUOUS
    layer: str  # L0 | L1 | L2 | -
    confidence: float = 0.0
    candidates: tuple[str, ...] = ()
    evidence: str = ""
    note: str = ""

    @property
    def resolved(self) -> bool:
        return self.symbol_id is not None

    @property
    def needs_human(self) -> bool:
        return self.tier != TIER_EXTRACTED

    def to_dict(self) -> dict:
        return {**self.__dict__, "candidates": list(self.candidates)}


# ----------------------------------------------------------- persistencia


class AliasStore:
    """Tabla de alias y bitacora de menciones.

    Los alias son fuente de verdad —los escribe un humano al confirmar— y van a
    git. Las menciones son bitacora de auditoria: append-only, para que un error
    de resolucion quede **escrito y reauditable** en vez de desaparecer dentro
    del indice.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.alias_path = self.root / "aliases.jsonl"
        self.mention_path = self.root / "mentions.jsonl"

    # --------------------------------------------------------------- alias

    def load(self) -> list[Alias]:
        if not self.alias_path.exists():
            return []
        out = []
        for line in self.alias_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            d["valido_desde"] = date.fromisoformat(d["valido_desde"])
            if d.get("valido_hasta"):
                d["valido_hasta"] = date.fromisoformat(d["valido_hasta"])
            out.append(Alias(**d))
        return out

    def _save_all(self, aliases: list[Alias]) -> None:
        def enc(a: Alias) -> str:
            d = {**a.__dict__}
            d["valido_desde"] = a.valido_desde.isoformat()
            d["valido_hasta"] = a.valido_hasta.isoformat() if a.valido_hasta else None
            return json.dumps(d, ensure_ascii=False)

        self.alias_path.write_text("\n".join(enc(a) for a in aliases) + "\n", encoding="utf-8")

    def add(self, alias: Alias, symbol) -> Alias:
        """El portal. Todo alias que existe entro por aca, y por eso el simbolo
        es obligatorio: sin el no hay forma de mirar sus slots.

        **Un simbolo con `slots` vacio no se puede aliasear.** `mark_disputed`
        sale temprano si el simbolo nuevo no tiene slots y `_l2` tampoco lo
        puede proponer, asi que L1 seria su unica via — y una via indisputable.
        El alias resolveria EXTRACTED 1,0 para siempre sin que el mecanismo que
        existe para cuestionarlo pueda alcanzarlo nunca.

        `save_all` quedo privado por esto mismo: un portal con una puerta de
        servicio al lado no es un portal.
        """
        if alias.symbol_id and symbol is not None and symbol.id != alias.symbol_id:
            raise ValueError(
                f"el alias apunta a {alias.symbol_id!r} y el simbolo es {symbol.id!r}"
            )
        if symbol is None or not getattr(symbol, "slots", None):
            raise ValueError(
                f"el simbolo {alias.symbol_id or '?'} no tiene slots: no se puede aliasear. "
                "Sin slots, `mark_disputed` no lo puede disputar y `_l2` no lo puede "
                "proponer, asi que L1 seria su unica via y esa via seria indisputable: "
                "el alias resolveria con confianza 1,0 para siempre y sin apelacion. "
                "Poblar `slots` con `extract_slots(statement + ' ' + criteria)` primero."
            )
        issues = alias.validate()
        if issues:
            raise ValueError(f"alias invalido:\n  - " + "\n  - ".join(issues))
        aliases = self.load()
        aliases.append(alias)
        self._save_all(aliases)
        return alias

    # ------------------------------------------------------------ menciones

    def log_mention(self, record: dict) -> None:
        with self.mention_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def mentions(self) -> list[dict]:
        if not self.mention_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.mention_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


# ------------------------------------------------------------- las 3 capas


def _l0(surface: str, agenda_symbol: str | None) -> Resolution | None:
    """Anclas duras. Deterministico, EXTRACTED, confianza 1,0."""
    m = _RE_ID.search(surface)
    if m:
        autor = f"{m.group(2).upper()}-" if m.group(2) else ""
        sid = f"{m.group(1).upper()}-{autor}{int(m.group(3)):03d}"
        return Resolution(sid, TIER_EXTRACTED, "L0", 1.0, (sid,), f"ID literal '{m.group(0)}'")
    if agenda_symbol:
        # Herencia del punto de agenda: el analogo del nombre totalmente
        # calificado. Si el punto declara que toca D-034, toda mencion no
        # resuelta dentro de ese punto lo hereda.
        return Resolution(
            agenda_symbol, TIER_EXTRACTED, "L0", 0.95, (agenda_symbol,),
            "heredado del punto de agenda",
        )
    return None


def _l1(surface: str, aliases: list[Alias], scope: str, when: date) -> Resolution | None:
    """Tabla de alias. Deterministico una vez aprendido.

    El filtro por scope y por vigencia no es un detalle: "lo del slotting" es
    D-034 en marzo y D-051 en junio porque el tema recurre. La colision en el
    tiempo es el caso normal, no el accidente.
    """
    norm = _norm(surface)
    hits = [
        a
        for a in aliases
        if a.surface_norm in norm and a.vigente_en(when) and a.cubre_scope(scope)
    ]
    if not hits:
        # Se informa si habia un alias que hubiera resuelto pero esta en
        # disputa o vencido: un silencio sin explicacion parece un descuido.
        bloqueados = [
            a for a in aliases if a.surface_norm in norm and not a.vigente_en(when)
        ]
        if bloqueados:
            a = bloqueados[0]
            return Resolution(
                None, TIER_AMBIGUOUS, "L1", 0.0, (a.symbol_id,),
                f"alias '{a.surface_norm}' existe pero esta {a.estado.lower()}",
                "cae a L2 y vuelve a la cola una vez",
            )
        return None

    destinos = sorted({a.symbol_id for a in hits})
    if len(destinos) > 1:
        return Resolution(
            None, TIER_AMBIGUOUS, "L1", 0.0, tuple(destinos),
            f"{len(destinos)} alias vigentes en el mismo scope apuntan a simbolos distintos",
        )
    mejor = max(hits, key=lambda a: len(a.surface_norm))
    return Resolution(
        mejor.symbol_id, TIER_EXTRACTED, "L1", 1.0, (mejor.symbol_id,),
        f"alias '{mejor.surface_norm}' confirmado por {mejor.confirmado_por}",
    )


def _jaccard(a: dict, b: dict) -> float:
    sa = {f"{k}={v}" for k, v in a.items()}
    sb = {f"{k}={v}" for k, v in b.items()}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _scope_proximity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return 0.6 if a.startswith(b + "/") or b.startswith(a + "/") else 0.0


def _l2(surface: str, decisions: list, scope: str) -> Resolution:
    """Slots tipados. Heuristico, INFERRED.

    Mata el falso positivo mas caro y mas frecuente: dos decisiones de slotting
    en sitios distintos. Un embedding las confundiria; los slots no, porque
    `sitio` es parte de la firma.
    """
    slots = extract_slots(surface)
    if not slots:
        return Resolution(
            None, TIER_AMBIGUOUS, "L2", 0.0, (), "",
            "la mencion no tiene ningun slot reconocible: no hay con que discriminar",
        )

    puntajes: list[tuple[float, str]] = []
    for d in decisions:
        s = 0.7 * _jaccard(slots, d.slots or {}) + 0.3 * _scope_proximity(scope, d.scope)
        if s >= L2_MIN_SCORE:
            puntajes.append((round(s, 3), d.id))
    if not puntajes:
        return Resolution(None, TIER_AMBIGUOUS, "L2", 0.0, (), "",
                          "ningun simbolo supera el umbral de similitud de slots")

    puntajes.sort(reverse=True)
    mejor, sid = puntajes[0]
    empatados = [i for p, i in puntajes if mejor - p <= L2_TIE_MARGIN]
    if len(empatados) > 1:
        return Resolution(
            None, TIER_AMBIGUOUS, "L2", mejor, tuple(empatados),
            f"slots {slots}",
            f"{len(empatados)} candidatos empatados dentro del mismo scope: es un error "
            "reportado, no una eleccion",
        )
    return Resolution(sid, TIER_INFERRED, "L2", mejor, (sid,), f"slots {slots}")


def resolve(
    surface: str,
    store,
    meeting,
    agenda_symbol: str | None = None,
    alias_store: AliasStore | None = None,
) -> Resolution:
    """L0 -> L1 -> L2 con cortocircuito. Nunca adivina en silencio."""
    scope = meeting.scope or ""
    astore = alias_store or AliasStore(store.root)

    r = _l0(surface, agenda_symbol)
    if r:
        return r

    r = _l1(surface, astore.load(), scope, meeting.date)
    if r and r.resolved:
        return r
    bloqueo = r  # puede traer el motivo de por que L1 no resolvio

    r2 = _l2(surface, store.decisions(), scope)
    if not bloqueo:
        return r2
    if not r2.resolved:
        return Resolution(
            None, TIER_AMBIGUOUS, "L1", 0.0, bloqueo.candidates, bloqueo.evidence, bloqueo.note
        )
    # L2 resolvio, pero habia un alias que hubiera resuelto y esta bloqueado.
    # El motivo viaja con el resultado: un alias en disputa cae a L2 y **vuelve
    # a la cola una vez**, y el humano no puede decidir eso sin saber por que.
    return Resolution(
        r2.symbol_id, r2.tier, r2.layer, r2.confidence, r2.candidates,
        f"{bloqueo.evidence}; resuelto por L2: {r2.evidence}",
        f"{bloqueo.note} (L2 propone {r2.symbol_id})".strip(),
    )


# ------------------------------------------------------- deteccion de error


def slot_coherence(quote: str, symbol) -> tuple[bool, str]:
    """Chequeo de coherencia contra la cita congelada.

    El diseno enuncia la regla como "si la cita no comparte ningun slot, es
    sospechosa", y dice que eso atrapa el caso "mismo proceso, otro sitio". Las
    dos cosas no pueden ser ciertas a la vez: en ese caso la cita SI comparte
    un slot (el proceso), y la regla enunciada lo dejaria pasar — justo el caso
    que existe para atrapar.

    La regla implementada es la que cumple el proposito: **un choque en
    cualquier slot compartido es sospechoso**, aunque otros slots coincidan.
    "Slotting de Quilicura" contra un simbolo de Pudahuel comparte `proceso` y
    choca en `sitio`, y es exactamente donde un resolutor semantico se equivoca
    con mas confianza.
    """
    q = extract_slots(quote)
    s = symbol.slots or {}
    if not q or not s:
        return True, "sin slots para comparar: no se puede afirmar ni negar"

    choques = {k: (q[k], s[k]) for k in q if k in s and q[k] != s[k]}
    if choques:
        detalle = ", ".join(f"{k}: cita dice '{a}', {symbol.id} dice '{b}'"
                            for k, (a, b) in choques.items())
        return False, f"choque de slots — {detalle}"

    if any(k in s and q[k] == s[k] for k in q):
        return True, ""
    return False, f"la cita no comparte ningun slot con {symbol.id}"


# ------------------------------------------------- confirmacion y reproceso


def confirm(
    astore: AliasStore,
    surface: str,
    symbol,
    scope: str,
    by: str,
    when: date,
    resolution: Resolution | None = None,
    meeting_id: str = "",
) -> Alias:
    """El humano colapsa la incertidumbre. Se escribe el alias **y** la mencion.

    La mencion guarda la capa que resolvio, la confianza y los candidatos
    descartados, para que el error quede escrito y reauditable en vez de
    desaparecer dentro del indice.

    `symbol` es el objeto, no su id. Antes era el id y eso permitia confirmar
    contra un simbolo inexistente —o contra uno sin slots, que es peor porque
    si existe y resuelve— y el portal de `add` no tenia como mirarlo. La
    mencion **se escribe despues del alias**: si el portal rechaza, la bitacora
    no queda con el rastro de un alias que no existe.
    """
    symbol_id = symbol.id
    alias = Alias(
        surface_norm=_norm(surface),
        symbol_id=symbol_id,
        scope=scope,
        valido_desde=when,
        confirmado_por=by,
        confirmado_en=datetime.now().astimezone().isoformat(),
    )
    astore.add(alias, symbol)

    mention_id = f"M-{len(astore.mentions()) + 1:04d}"
    astore.log_mention(
        {
            "id": mention_id,
            "surface": surface,
            "surface_norm": alias.surface_norm,
            "symbol_id": symbol_id,
            "scope": scope,
            "meeting_id": meeting_id,
            "capa_resolutora": resolution.layer if resolution else "humano",
            "tier": resolution.tier if resolution else TIER_EXTRACTED,
            "confidence": resolution.confidence if resolution else 1.0,
            "candidatos_descartados": [
                c for c in (resolution.candidates if resolution else ()) if c != symbol_id
            ],
            "confirmado_por": by,
            "confirmado_en": alias.confirmado_en,
            "estado": "VIGENTE",
        }
    )

    aliases = astore.load()
    for a in aliases:
        if a.surface_norm == alias.surface_norm and a.symbol_id == symbol_id:
            a.mentions_resueltas.append(mention_id)
    astore._save_all(aliases)
    return alias


def unalias(astore: AliasStore, surface: str, reason: str, when: date) -> dict:
    """`safe_delete` sobre el indice. Retira el alias Y reprocesa lo que decidio.

    Es la operacion que ningun enfoque del estudio original tenia, y sin ella el
    determinismo que se gana es **determinismo del error**: una confirmacion
    humana equivocada quedaria resolviendo mal con EXTRACTED 1,0 para siempre,
    sin volver a pasar por la cola.
    """
    norm = _norm(surface)
    aliases = astore.load()
    afectados = [a for a in aliases if a.surface_norm == norm and a.estado != "RETIRADO"]
    if not afectados:
        return {"retirados": 0, "menciones_a_recola": [], "motivo": "no habia alias vigente"}

    revertidas: list[str] = []
    for a in afectados:
        a.estado = "RETIRADO"
        a.valido_hasta = when
        revertidas.extend(a.mentions_resueltas)
    astore._save_all(aliases)

    # Las menciones que ese alias resolvio vuelven a la cola: no se borran, se
    # marcan. Borrarlas perderia la evidencia de que el sistema se equivoco.
    for m in astore.mentions():
        if m["id"] in revertidas:
            astore.log_mention(
                {**m, "estado": "REVERTIDA", "revertida_por": f"unalias: {reason}",
                 "revertida_en": when.isoformat()}
            )
    return {
        "retirados": len(afectados),
        "menciones_a_recola": revertidas,
        "motivo": reason,
        "nota": (
            f"{len(revertidas)} mencion(es) vuelven a la cola. El error queda escrito, "
            "no borrado."
        ),
    }


def mark_disputed(astore: AliasStore, nueva, decisions: list) -> list[str]:
    """Resolucion de colision **por creacion, no por uso**.

    Cuando nace un simbolo con el mismo scope y slots solapados que uno viejo,
    los alias del viejo que colisionan pasan a EN_DISPUTA. Un alias en disputa
    no resuelve en L1: cae a L2 y vuelve a la cola una vez, y el humano decide
    si se cierra la vigencia del viejo.

    Detectarlo al crear y no al usar es lo que evita que el primer uso despues
    de la colision resuelva mal con confianza 1,0.
    """
    if not nueva.slots:
        return []
    viejos = {
        d.id
        for d in decisions
        if d.id != nueva.id
        and _scope_proximity(d.scope, nueva.scope) > 0
        and _jaccard(d.slots or {}, nueva.slots) > 0
    }
    if not viejos:
        return []

    aliases = astore.load()
    marcados = []
    for a in aliases:
        if a.symbol_id in viejos and a.estado == "VIGENTE":
            a.estado = "EN_DISPUTA"
            marcados.append(a.surface_norm)
    if marcados:
        astore._save_all(aliases)
    return marcados
