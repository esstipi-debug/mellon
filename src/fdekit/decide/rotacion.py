"""H9 — el actor que no estuvo. Onboarding, rotacion y entrega al piso.

Tres personas concretas, ninguna con ruta en el diseno original, y las tres
consultas sobre datos que ya existen — cero entidades nuevas.

**El que se incorpora en la semana 10.** `onboarding_brief`. Es el unico
artefacto que un recien llegado va a leer entero, asi que es el unico lugar
donde vale la pena gastar el orden: por dependencia, no por fecha. Una lista
plana lo obliga a reconstruir solo por que existe cada decision, que es justo el
trabajo que el brief tiene que ahorrarle.

**El que se va.** `reassign_owner` y `duenos_huerfanos`. La rotacion de FDE y de
contraparte es la norma, no la excepcion: a los seis meses una fraccion alta del
registro apunta a gente que ya no esta, y sin barrido eso no se ve hasta que
alguien pregunta por algo y no hay a quien preguntarle.

**El ejecutor de piso.** `tarjeta_de_piso`. El supervisor de turno noche tiene
que ejecutar la decision, no estuvo en ninguna reunion y no lee correo durante
el turno. El output del sistema es markdown en git y el canal de entrega era un
hueco total. Tres lineas que caben en un mensaje o en la hoja de trabajo
estandar; si no cabe, no llega.
"""

from __future__ import annotations

from datetime import date

from .schema import DEAD_DECISION_STATUS, LIVE_COMMITMENT_STATUS
from .store import DecideStore, ValidationError


def _en_scope(obj, scope: str) -> bool:
    """Un scope contiene a sus hijos. `pudahuel` cubre `pudahuel/slotting`, pero
    `pudahuel/slotting` no cubre `quilicura`. Misma regla que `Alias.cubre_scope`
    — definirla dos veces es como se desincronizan."""
    s = getattr(obj, "scope", "") or ""
    if not scope:
        return True
    return s == scope or s.startswith(scope + "/")


def _orden_por_dependencia(decisiones) -> list:
    """Topologico estable: una decision va despues de aquellas de las que
    depende, y a igualdad de profundidad manda la fecha.

    Un ciclo no revienta ni se salta: las de profundidad indeterminada caen al
    final, que es un lugar visible. Reventar dejaria al recien llegado sin brief
    por un dato viejo mal enlazado.
    """
    por_id = {d.id: d for d in decisiones}
    profundidad: dict[str, int] = {}

    def prof(d, visitados: frozenset) -> int:
        if d.id in profundidad:
            return profundidad[d.id]
        if d.id in visitados:
            return 99  # ciclo: al final, y visible
        padres = [por_id[p] for p in d.depends_on if p in por_id]
        p = 0 if not padres else 1 + max(prof(x, visitados | {d.id}) for x in padres)
        profundidad[d.id] = p
        return p

    return sorted(decisiones, key=lambda d: (prof(d, frozenset()), d.date_decided, d.id))


def onboarding_brief(store: DecideStore, scope: str, today: date) -> dict:
    """Que esta decidido, en que orden, que sigue vivo y que lo sostiene.

    `today` es argumento (regla 4): la edad de un supuesto es la mitad del dato.
    Un supuesto de hace cinco meses y uno de la semana pasada sostienen la misma
    decision con confianza muy distinta, y el recien llegado es exactamente el
    que no tiene forma de distinguirlos.
    """
    todas = store.decisions()
    vivas = [
        d for d in todas
        if d.status not in DEAD_DECISION_STATUS and _en_scope(d, scope)
    ]
    ids_vivas = {d.id for d in vivas}

    decisiones = [
        {
            "id": d.id,
            "statement": d.statement,
            "owner": d.owner,
            "status": d.status,
            "decidida": d.date_decided.isoformat(),
            "criteria": d.criteria,
            "rationale": d.rationale,
            "depende_de": [p for p in d.depends_on if p in ids_vivas],
            # Una sembrada y una decidida en sala no valen lo mismo, y el que
            # llega es justo el que no puede distinguirlas por contexto.
            "origen": d.origen,
            "auditable": d.auditable,
        }
        for d in _orden_por_dependencia(vivas)
    ]

    supuestos = [
        {
            "id": a.id,
            "statement": a.statement,
            "decision_id": a.decision_id,
            "status": a.status,
            "source": a.source,
            "check_by": a.check_by.isoformat(),
            "edad_dias": (today - _nacimiento(store, a)).days,
        }
        for a in store.assumptions()
        if a.status != "VERIFICADO" and a.decision_id in ids_vivas
    ]

    compromisos = [
        {
            "id": c.id, "what": c.what, "owner": c.owner,
            "due": c.due.isoformat(), "status": c.status,
            "decision_id": c.decision_id,
            "corridas": c.slips_hacia_adelante,
        }
        for c in store.commitments()
        if c.status in LIVE_COMMITMENT_STATUS and c.decision_id in ids_vivas
    ]

    fuera = sum(1 for d in todas if not _en_scope(d, scope))
    return {
        "scope": scope,
        "decisiones": decisiones,
        "supuestos": sorted(supuestos, key=lambda a: -a["edad_dias"]),
        "compromisos": sorted(compromisos, key=lambda c: c["due"]),
        "fuera_de_scope": fuera,
        "cobertura": {
            "decisiones_en_disco": len(todas),
            "decisiones_mostradas": len(decisiones),
            "no_auditables": sum(1 for d in decisiones if not d["auditable"]),
        },
        # Misma doctrina que `Coverage`: nombra primero lo que dejo afuera. Un
        # brief que se lee como completo y no lo es le da al recien llegado la
        # peor confianza posible — la fundada en un indice mudo.
        "nota": (
            f"Esto NO es todo lo que se decidio: son las {len(decisiones)} vigentes de "
            f"'{scope}' de las {len(todas)} en disco ({fuera} quedaron fuera por scope). "
            "Lo revertido y lo superado no aparece a proposito. Lo que no salio de una "
            "reunion registrada va marcado `auditable: false`: se declaro, no se audito."
        ),
    }


def _nacimiento(store: DecideStore, a) -> date:
    """La fecha de la decision que el supuesto sostiene.

    `Assumption` no tiene fecha de creacion, y agregarle una obligaria a
    registrarla en `_DATE_FIELDS` y a migrar lo persistido. La de su decision es
    la aproximacion honesta: el supuesto se declaro cuando se decidio.
    """
    try:
        return store.get(a.decision_id).date_decided
    except (KeyError, ValidationError):
        # Lectura degradada por archivo, como en `store.ilegibles`: un .md ilegible
        # no puede dejar sin brief al que llega.
        return a.check_by


def reassign_owner(
    store: DecideStore,
    sale: str,
    entra: str,
    today: date,
    apply: bool = False,
) -> dict:
    """Rotacion de dueno. Solo sobre lo VIVO.

    Lo muerto no se toca y esa es la mitad del contrato: un compromiso CUMPLIDO
    lo cumplio quien lo cumplio, y reasignarlo reescribe quien hizo el trabajo.
    Lo mismo una decision SUPERADA — la decidio quien la decidio.
    """
    rosters = {p for m in store.meetings() for p in m.roster}
    if entra not in rosters:
        raise ValueError(
            f"'{entra}' no esta en el roster de ninguna reunion registrada. El roster es "
            "el scope lexico del sistema: reasignar a un nombre que no existe cambia un "
            "dueno real por uno inventado, y todo lo que cuelga queda apuntando a nadie. "
            "Registrar primero la reunion donde entra."
        )

    reasignados, intactos = [], []
    for d in store.decisions():
        if d.owner != sale:
            continue
        if d.status in DEAD_DECISION_STATUS:
            intactos.append(d.id)
            continue
        reasignados.append(d.id)
        if apply:
            d.owner = entra
            # MINUSCULAS a proposito. `HIST_RE` convierte cualquier token en
            # mayusculas del historial en una actividad del event log: escribir
            # "REASIGNADA:" agregaria una actividad a `variants`, cambiaria
            # `touches_to_decide` y con eso correria la linea base congelada del
            # XmR, que la regla 6 prohibe mover. Y nadie lo veria: los numeros
            # siguen saliendo. `hist_line` no sirve aca justo por eso.
            d.historial_statements.append(
                f"{today.isoformat()} dueno reasignado de {sale} a {entra}"
            )
            store.save(d)

    for c in store.commitments():
        if c.owner != sale:
            continue
        if c.status not in LIVE_COMMITMENT_STATUS:
            intactos.append(c.id)
            continue
        reasignados.append(c.id)
        if apply:
            c.owner = entra
            store.save(c)

    for q in store.questions():
        if q.resolver != sale:
            continue
        if q.status != "ABIERTA":
            intactos.append(q.id)
            continue
        reasignados.append(q.id)
        if apply:
            q.resolver = entra
            store.save(q)

    return {
        "sale": sale,
        "entra": entra,
        "applied": apply,
        "reasignados": reasignados,
        "intactos": intactos,
        "nota": (
            f"{len(reasignados)} vivo(s) pasan a {entra}; {len(intactos)} quedaron "
            f"intactos porque ya estan cerrados y los cerro {sale}. "
            + ("" if apply else "No se toco nada: usar apply=True (CLI: --apply).")
        ),
    }


def duenos_huerfanos(store: DecideStore, activos, today: date) -> dict:
    """Lo vivo que apunta a gente que ya no esta.

    El barrido de offboarding. Sin el, a los seis meses una fraccion alta del
    registro apunta a personas que se fueron y el registro se vuelve ruido —
    y no hay ninguna senal tecnica de que eso paso, porque cada fila sigue
    siendo valida por separado.
    """
    activos = set(activos)
    huerfanos: dict[str, list[str]] = {}

    def marcar(persona: str, ident: str) -> None:
        if persona and persona not in activos:
            huerfanos.setdefault(persona, []).append(ident)

    for d in store.decisions():
        if d.status not in DEAD_DECISION_STATUS:
            marcar(d.owner, d.id)
    for c in store.commitments():
        if c.status in LIVE_COMMITMENT_STATUS:
            marcar(c.owner, c.id)
    for q in store.questions():
        if q.status == "ABIERTA":
            marcar(q.resolver, q.id)

    total = sum(len(v) for v in huerfanos.values())
    return {
        "activos": sorted(activos),
        "huerfanos": {k: sorted(v) for k, v in sorted(huerfanos.items())},
        "total": total,
        "nota": (
            f"{total} objeto(s) vivos apuntan a {len(huerfanos)} persona(s) fuera de la "
            "lista de activos. Cada uno es una pregunta que nadie va a poder contestar. "
            "Cerrar con `reassign_owner`, o cancelarlos explicitamente."
            if total else
            "Nada vivo apunta a gente fuera de la lista."
        ),
    }


def tarjeta_de_piso(store: DecideStore, commitment_id: str) -> str:
    """Tres lineas para el que ejecuta y no estuvo en la reunion.

    Cabe en un WhatsApp o en el encabezado de la hoja de trabajo estandar. El
    limite de tres lineas no es estetico: el supervisor de turno noche lo lee
    entre dos tareas, y lo que no cabe en la pantalla del telefono no se lee.

    **Solo nombra al dueno** (H14). La tarjeta sale del sistema hacia un canal
    sin ningun control —el telefono personal de alguien, una hoja impresa que
    queda en un pizarron— asi que es exactamente el punto donde un tercero
    mencionado deja de ser reversible. El dueno es la unica persona nombrable
    porque su nombre es constitutivo de la obligacion; cualquier otro es un dato
    personal de alguien que no consintio.
    """
    c = store.get(commitment_id)
    try:
        d = store.get(c.decision_id)
        porque = d.rationale or d.statement
    except (KeyError, ValidationError):
        d, porque = None, ""

    # Redaccion contra el directorio completo, no contra el roster de la sesion:
    # el tercero mencionado suele ser justo el que no estuvo.
    nombres = {p for m in store.meetings() for p in m.roster} - {c.owner}
    for n in sorted(nombres, key=len, reverse=True):
        porque = porque.replace(n, "[NOMBRE]")

    corridas = (
        f" ({c.slips_hacia_adelante}a vez que se corre)" if c.slips_hacia_adelante else ""
    )
    return "\n".join([
        f"{c.id} — {c.owner}: {c.what}",
        f"Para el {c.due.isoformat()}{corridas}. Listo cuando: {c.evidence_of_done}.",
        f"Por que: {porque[:120]}" if porque else "Por que: (sin decision asociada)",
    ])


__all__ = [
    "duenos_huerfanos",
    "onboarding_brief",
    "reassign_owner",
    "tarjeta_de_piso",
]
