"""H4 — el arranque en frio. Cero entidades nuevas, dos operaciones.

El dia 1 el registro esta vacio y compite contra tres anos de historial: `why()`
y `referencing()` devuelven vacio justo en las cuatro semanas donde se juega la
adopcion, y las ~20 decisiones que YA gobiernan —tomadas antes de que el sistema
existiera— son exactamente las que se van a re-discutir. Sembrarlas es el mejor
retorno del proyecto entero.

Tambien es donde el registro tiene mas facil empezar a mentir, y por eso este
modulo es sobre todo una lista de cosas que **no** hace:

  - **No relaja `validate()`.** La tentacion es dejar entrar 30 filas declaradas
    de memoria con criterio flojo. Es la regla dura 1 de frente: un registro con
    huecos genera falsa confianza. Lo que no pasa sale NOMBRADO en el reporte,
    con el dueno de la reunion y el nombre exacto de lo que falta. Forzar la
    cuantificacion es el valor de los 90 minutos de la sesion, no un obstaculo.
  - **No usa `force` nunca.** `force` es un interruptor general —apaga roster,
    criterio, rationale, ancla y presupuesto de una sola vez— y no deja marca en
    el archivo. Una sembrada forzada es indistinguible de una auditada: no
    falla, miente. Hay un test que lee este archivo y falla si aparece.
  - **No abre la compuerta de volumen.** Las sembradas van con `origen=SIEMBRA`,
    y por lo tanto **no son `auditable`**: quedan fuera del Corpus. 30 sembradas
    + 20 reales no son las 50 de la regla 5. El incentivo queda apuntando en la
    direccion correcta: hacer pasar decisiones reales como sembradas para ganar
    techo empeora las propias metricas.
  - **No escribe menciones.** `resolucion_automatica_pct` es la metrica que
    tiene que subir sesion a sesion; sembrar menciones la arranca desde un piso
    que fabricamos nosotros. `mentions.jsonl` no se crea.
  - **No fabrica `Consent` ni roster.** La reunion de siembra tiene que estar ya
    registrada con `decide meeting`. El consentimiento es la unica pieza de
    cumplimiento que no se puede retrofitear; un placeholder la vuelve decorado.

Los `slots` se pueblan con `extract_slots(statement + " " + criteria)` y no es
cosmetico: sin slots, `mark_disputed` no puede disputar el alias NUNCA y `_l2`
no puede proponer el simbolo, asi que L1 seria su unica via — y una via
indisputable. 30 alias declarados de memoria resolviendo EXTRACTED 1,0 de forma
permanente es el envenenamiento del indice hecho procedimiento de instalacion.
La fila cuyo enunciado no produce ningun slot **no siembra su alias** y sale
nombrada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..gemba import normalize as _norm
from .parse import extract_slots
from .resolve import AliasStore
from .schema import Alias, Decision
from .store import DecideStore, ValidationError


@dataclass(frozen=True)
class FilaSiembra:
    """Una fila de la planilla de siembra. Las mismas columnas que exige
    `Decision.validate`, mas el alias con el que la sala llama a la decision.

    `alias` es opcional porque hay decisiones vigentes que nadie abrevia; lo que
    NO es opcional es el criterio ni el rationale. `date_decided` en None
    significa "se declaro en la sesion de siembra": la fecha de la reunion.
    """

    statement: str
    owner: str
    criteria: str
    rationale: str
    alias: str = ""
    scope: str = ""
    date_decided: date | None = None


@dataclass
class ReporteSiembra:
    """Lo que entro y —sobre todo— lo que no. Mismo contrato que `Coverage`:
    nombra primero lo que quedo afuera, porque una exclusion silenciosa es la
    misma mentira que un hueco."""

    escritas: list[str] = field(default_factory=list)
    rechazadas: list[tuple[str, list[str]]] = field(default_factory=list)
    alias_escritos: list[str] = field(default_factory=list)
    alias_rechazados: list[tuple[str, str]] = field(default_factory=list)

    @property
    def nota(self) -> str:
        partes = [
            f"{len(self.escritas)} decision(es) sembradas con origen SIEMBRA: "
            "NO son auditables y no cuentan para la compuerta de volumen."
        ]
        if self.rechazadas:
            partes.append(
                f"{len(self.rechazadas)} fila(s) NO entraron al registro y quedan para "
                "la sesion: la siembra no relaja la validacion, y una fila con huecos "
                "genera mas falsa confianza que una fila ausente."
            )
        if self.alias_rechazados:
            partes.append(
                f"{len(self.alias_rechazados)} alias NO se escribieron. Un alias que no "
                "se escribio en silencio hace que la sala crea que el sistema entiende "
                "una frase que no entiende."
            )
        return " ".join(partes)


def _sembrar_alias(
    astore: AliasStore,
    superficie: str,
    decision,
    scope: str,
    by: str,
    when: date,
    rep: ReporteSiembra,
) -> None:
    """Escribe un alias por el portal, o dice por que no.

    No pasa por `confirm()` a proposito: `confirm` escribe tambien la mencion, y
    la siembra no puede tocar `mentions.jsonl` sin fabricarle un piso a
    `resolucion_automatica_pct`.
    """
    surface_norm = _norm(superficie)
    if not surface_norm:
        return
    if not scope:
        rep.alias_rechazados.append((
            superficie,
            "sin scope, ni en la fila ni en la reunion: no existe el alias global. "
            "Resolveria en contextos donde nadie lo confirmo.",
        ))
        return

    # Colision: misma superficie y mismo scope apuntando a otro simbolo. Dejar
    # las dos deja `_l1` en AMBIGUOUS para esa frase **para siempre**: la frase
    # mas usada de la cuenta queda inservible y nadie sabe por que.
    for a in astore.load():
        if a.surface_norm == surface_norm and a.scope == scope and a.estado == "VIGENTE":
            if a.symbol_id != decision.id:
                rep.alias_rechazados.append((
                    superficie,
                    f"colision: '{surface_norm}' ya apunta a {a.symbol_id} en el scope "
                    f"'{scope}'. Dejar los dos deja la frase en AMBIGUOUS para siempre.",
                ))
            return

    try:
        astore.add(
            Alias(
                surface_norm=surface_norm,
                symbol_id=decision.id,
                scope=scope,
                valido_desde=when,
                confirmado_por=by,
            ),
            decision,
        )
    except ValueError as exc:
        rep.alias_rechazados.append((superficie, str(exc)))
        return
    rep.alias_escritos.append(surface_norm)


def seed_decisions(
    store: DecideStore,
    meeting_id: str,
    filas,
    by: str,
    today: date,
) -> ReporteSiembra:
    """Las 15-30 decisiones vigentes declaradas en la sesion de siembra.

    `today` es argumento (regla 4): esta funcion rechaza fechas futuras y no
    puede depender de que reloj tenga la maquina que la corre. La fecha por
    default de una fila es la de la reunion, no la de hoy: la sesion de siembra
    puede cargarse dias despues.
    """
    meeting = store.get_meeting(meeting_id)
    astore = AliasStore(store.root)
    rep = ReporteSiembra()

    for fila in filas:
        cuando = fila.date_decided or meeting.date
        if cuando > today:
            rep.rechazadas.append((
                fila.statement,
                [f"fecha futura ({cuando}): una decision vigente se tomo en el pasado"],
            ))
            continue

        scope = fila.scope or meeting.scope
        d = Decision(
            id="",
            statement=fila.statement,
            owner=fila.owner,
            date_decided=cuando,
            criteria=fila.criteria,
            rationale=fila.rationale,
            meeting_id=meeting_id,
            scope=scope,
            origen="SIEMBRA",
            # La linea que hace disputable el alias de manana.
            slots=extract_slots(f"{fila.statement} {fila.criteria}"),
        )
        try:
            store.add_decision(d)
        except (ValidationError, ValueError, KeyError) as exc:
            motivos = getattr(exc, "issues", None) or [str(exc)]
            rep.rechazadas.append((fila.statement, list(motivos)))
            continue

        rep.escritas.append(d.id)
        if fila.alias:
            _sembrar_alias(astore, fila.alias, d, scope, by, meeting.date, rep)

    return rep


def seed_aliases(
    store: DecideStore,
    meeting_id: str,
    entradas,
    by: str,
    today: date,
) -> ReporteSiembra:
    """El glosario precargado: alias de decisiones que **ya existen**.

    Es la otra mitad de H4 y no cuelga de una fila de siembra. `entradas` son
    tuplas `(superficie, symbol_id, scope)`; el scope vacio hereda el de la
    reunion, y si tampoco hay, la entrada se rechaza.
    """
    meeting = store.get_meeting(meeting_id)
    astore = AliasStore(store.root)
    rep = ReporteSiembra()

    for superficie, symbol_id, scope in entradas:
        try:
            simbolo = store.get(symbol_id)
        except (KeyError, ValidationError) as exc:
            rep.alias_rechazados.append((superficie, f"simbolo inexistente: {exc}"))
            continue
        _sembrar_alias(
            astore, superficie, simbolo, scope or meeting.scope, by, meeting.date, rep
        )

    return rep


__all__ = ["FilaSiembra", "ReporteSiembra", "seed_aliases", "seed_decisions"]
