"""H15 — el cierre del proyecto: entrega, destruccion y lo que se lleva el FDE.

Tres huecos que se pagan al final, cuando ya no se pueden arreglar.

**De quien es el registro.** Contiene datos comerciales del cliente —volumenes,
tarifas, proveedores— y probablemente esta cubierto por el NDA. Guardarlo en el
repo del FDE puede ser incumplimiento. La clausula de entrega se define en el
kickoff, no en la ultima semana, y esta es su ejecucion: el canal DECIDIDA se
entrega en formato legible, el HABLADA se destruye con constancia, y el FDE
conserva a lo sumo el lexico y los patrones anonimizados.

**Uso punitivo.** El dia que el registro de compromisos se usa en una evaluacion
de desempeno, la gente deja de declarar decisiones y el sistema muere en dos
semanas sin ninguna senal tecnica. No hay control tecnico posible: solo que la
forma de la salida no lo invite —agrupada por decision, nunca por persona— y que
la norma viaje escrita EN lo que se entrega, no en un anexo que nadie abre.

**El orden importa y es la garantia entera.** Se escribe la entrega, se verifica
que quedo escrita, y recien ahi se destruye. Al reves —destruir y despues fallar
al escribir— deja al cliente sin registro y sin habla, y de eso no se vuelve.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .lexicon import MARKERS
from .render import _NORMA, _redactor, render_html
from .schema import DEAD_DECISION_STATUS, LIVE_COMMITMENT_STATUS
from .store import DecideStore
from .transcript import TranscriptStore


def _markdown(store: DecideStore, today: date) -> str:
    """El registro en markdown, agrupado por decision.

    Va al lado del HTML y no en vez de el: el HTML es para leerlo, el markdown
    es para que el cliente pueda meterlo en su propio sistema sin depender de
    nosotros. Un solo formato deja al cliente atado a la herramienta del
    consultor, que es la mitad del problema que la clausula viene a evitar.
    """
    vivas = sorted(
        (d for d in store.decisions() if d.status not in DEAD_DECISION_STATUS),
        key=lambda d: (d.date_decided, d.id),
    )
    ids = {d.id for d in vivas}
    por_decision: dict[str, list] = {}
    for c in store.commitments():
        if c.decision_id in ids and c.status in LIVE_COMMITMENT_STATUS:
            por_decision.setdefault(c.decision_id, []).append(c)

    L = [
        f"# Registro de decisiones — entrega del {today.isoformat()}",
        "",
        f"> {_NORMA}",
        "",
        f"{len(vivas)} decision(es) vigentes. Lo revertido y lo superado se conserva "
        "en el registro pero no se lista aca.",
        "",
    ]
    for d in vivas:
        redactar = _redactor(store, d.owner)
        marca = "" if d.auditable else f" _({d.origen} — declarada, no auditada)_"
        L += [
            f"## {d.id} — {redactar(d.statement)}{marca}",
            "",
            f"- **Responsable:** {d.owner}",
            f"- **Decidida:** {d.date_decided.isoformat()} · estado {d.status}",
            f"- **Listo cuando:** {redactar(d.criteria)}",
            f"- **Por que:** {redactar(d.rationale)}",
        ]
        for a in store.assumptions():
            if a.decision_id == d.id and a.status != "VERIFICADO":
                L.append(
                    f"- **Supuesto [{a.status}]:** {redactar(a.statement)} — se revisa "
                    f"el {a.check_by.isoformat()}, fuente: {redactar(a.source)}"
                )
        cuelgan = sorted(por_decision.get(d.id, []), key=lambda c: c.due)
        if cuelgan:
            L += ["", "| compromiso | responsable | para | listo cuando |",
                  "|---|---|---|---|"]
            for c in cuelgan:
                corridas = (
                    f" (la fecha se corrio {c.slips_hacia_adelante} vez/veces)"
                    if c.slips_hacia_adelante else ""
                )
                L.append(
                    f"| {c.id} {_redactor(store, c.owner)(c.what)}{corridas} | {c.owner} | "
                    f"{c.due.isoformat()} | {_redactor(store, c.owner)(c.evidence_of_done)} |"
                )
        L.append("")
    return "\n".join(L)


def lo_que_conserva_el_fde(store: DecideStore) -> dict:
    """El lexico y los patrones, anonimizados. Nada del cliente.

    Volumenes, tarifas, proveedores, nombres y scopes son datos del cliente bajo
    NDA. Lo unico que sale del proyecto son **nuestros** marcadores verbales y
    conteos sin identificadores — que es lo que de verdad mejora el kit para el
    proyecto siguiente.

    Los alias NO entran: son el vocabulario interno del cliente ("la ola
    grande", "lo del corte"), y ese vocabulario nombra sus procesos.
    """
    return {
        "decisiones": len(store.decisions()),
        "compromisos": len(store.commitments()),
        "supuestos": len(store.assumptions()),
        "preguntas": len(store.questions()),
        "reuniones": len(store.meetings()),
        # Nuestros, no suyos: son el lexico del kit.
        "marcadores_del_lexico": sorted(MARKERS),
        "nota": (
            "Solo conteos y el lexico del kit. Ningun enunciado, ningun nombre, ningun "
            "scope, ningun alias y ningun identificador del registro: son datos del "
            "cliente y estan cubiertos por el NDA."
        ),
    }


def entregar(
    store: DecideStore,
    destino: str | Path,
    today: date,
    por: str,
    apply: bool = False,
) -> dict:
    """La clausula de entrega, ejecutada. Sin `apply` no destruye nada.

    `today` y `por` son argumentos porque los dos van a la constancia, y una
    constancia con la fecha del reloj de quien la corrio y sin firma no
    atestigua nada.
    """
    destino = Path(destino)

    # Antes de tocar nada: la cola. Cerrar con borradores vivos destruye el
    # habla de la que salieron y deja la cola apuntando a una fuente que ya no
    # existe. Es exactamente el hueco que no se puede arreglar despues.
    from .draft import DraftStore

    pendientes = {
        m.id: len(DraftStore(store.root, m.id).load())
        for m in store.meetings()
        if DraftStore(store.root, m.id).load()
    }

    sesiones = [
        {"meeting_id": m.id, "reunion_del": m.date.isoformat()}
        for m in store.meetings()
        if TranscriptStore(store.root, m.id).exists()
    ]
    out = {
        "destino": str(destino),
        "applied": False,
        "sesiones_con_habla": [s["meeting_id"] for s in sesiones],
        "cola_pendiente": pendientes,
        "conserva_el_fde": lo_que_conserva_el_fde(store),
    }
    if not apply:
        out["nota"] = (
            f"no se destruyo nada. Con apply=True se escribe la entrega en {destino} y "
            f"recien despues se destruye el canal HABLADA de {len(sesiones)} sesion(es). "
            "El orden es la garantia: destruir primero y fallar al escribir deja al "
            "cliente sin registro y sin habla."
        )
        return out

    if pendientes:
        raise ValueError(
            f"hay cola de borradores sin revisar: {pendientes}. Cerrar ahora destruye el "
            "habla de la que salieron y deja la cola apuntando a una fuente que ya no "
            "existe. Revisar con `decide review` primero, o vaciarla a conciencia."
        )

    # 1. Escribir. Si esto falla, el canal HABLADA sigue intacto.
    destino.mkdir(parents=True, exist_ok=True)
    html = destino / "registro.html"
    md = destino / "registro.md"
    html.write_text(render_html(store, "", today=today), encoding="utf-8")
    md.write_text(_markdown(store, today), encoding="utf-8")

    # 2. Verificar que quedo escrito de verdad. Un `write_text` que no levanta
    #    pero deja un archivo vacio —disco lleno, ruta rara— seria la peor
    #    version de este bug: la entrega existe, esta vacia, y el habla ya no.
    for p in (html, md):
        if not p.exists() or p.stat().st_size == 0:
            raise OSError(
                f"la entrega no quedo escrita en {p}: no se destruye nada. "
                "El canal HABLADA sigue donde estaba."
            )

    # 3. Recien ahora, destruir.
    destruidas = []
    for s in sesiones:
        ts = TranscriptStore(store.root, s["meeting_id"])
        sha, n = ts.sha256(), len(ts.load())
        ts.path.unlink()
        destruidas.append({**s, "enunciados_destruidos": n, "sha256_al_destruir": sha})

    constancia = {
        "fecha": today.isoformat(),
        "por": por,
        "que_se_entrego": [html.name, md.name],
        "sesiones_destruidas": destruidas,
        "nota": (
            "Cierre de proyecto. El canal DECIDIDA se entrega al cliente en HTML y "
            "markdown; el canal HABLADA se destruyo. Las citas congeladas en las anclas "
            "sobreviven porque se copiaron y no se enlazaron, asi que el registro "
            "entregado sigue siendo legible y auditable contra si mismo. El sha de cada "
            "sesion prueba QUE se destruyo sin conservarlo: coincide con el "
            "`transcript_sha256` de las anclas que la citaban."
        ),
        "conserva_el_fde": lo_que_conserva_el_fde(store),
    }
    (destino / "constancia-destruccion.json").write_text(
        json.dumps(constancia, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    out["applied"] = True
    out["destruidas"] = [d["meeting_id"] for d in destruidas]
    out["nota"] = (
        f"entregado en {destino} y destruido el habla de {len(destruidas)} sesion(es), "
        "en ese orden. La constancia queda con el destino, no con nosotros."
    )
    return out


__all__ = ["entregar", "lo_que_conserva_el_fde"]
