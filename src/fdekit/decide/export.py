"""Export a graphify. Unidireccional, y con tres prohibiciones.

    1. **Nunca fuente de verdad.** El grafo es una vista derivada; el registro
       en git es el original. Si el grafo y el registro discrepan, gana el
       registro.
    2. **Nunca motor de extraccion.** Las aristas de aca salen de enlaces
       declarados o de alias confirmados por un humano. graphify visualiza y
       descubre lo emergente; no resuelve.
    3. **Nunca corrido sobre el transcripto crudo.** Hacer navegable la
       transcripcion produce miles de nodos vagos, ninguno direccionable, y
       multiplica por diez la superficie donde el sistema puede resolver mal.

El formato de graphify trae `confidence` EXTRACTED / INFERRED / AMBIGUOUS en
cada arista, que calza 1:1 con nuestro tier. Esa coincidencia es lo que permite
exportar sin perder la unica cosa que hay que preservar: cuanto se puede confiar
en cada arista.
"""

from __future__ import annotations

import json
from pathlib import Path

from .metrics import volume_gate
from .resolve import AliasStore
from .schema import TIER_EXTRACTED, TIER_INFERRED
from .store import DecideStore

_KIND = {"D": "Decision", "C": "Commitment", "A": "Assumption", "Q": "OpenQuestion"}


def to_graphify(store: DecideStore, include_inferred: bool = False) -> dict:
    """Nodos y aristas en el formato de graphify.

    Por defecto **solo aristas EXTRACTED**. Las INFERRED existen y se pueden
    incluir, pero entran apagadas: un grafo bonito construido sobre resolucion
    probabilistica miente con cara de rigor, y alguien actua sobre el el lunes.
    """
    decisions = store.decisions()
    commitments = store.commitments()
    assumptions = store.assumptions()
    questions = store.questions()

    nodes, edges = [], []

    def node(nid: str, label: str, **attrs):
        nodes.append({"id": nid, "label": label, "type": _KIND[nid.split("-")[0]], **attrs})

    def edge(src: str, dst: str, rel: str, tier: str, evidence: str = ""):
        edges.append({
            "source": src, "target": dst, "relation": rel,
            "confidence": tier, "evidence": evidence,
        })

    for d in decisions:
        node(d.id, d.statement, status=d.status, owner=d.owner, scope=d.scope,
             slots=d.slots, date=d.date_decided.isoformat(),
             cita=d.anchor.cita_congelada or None)
        for dep in d.depends_on:
            edge(d.id, dep, "DEPENDE_DE", TIER_EXTRACTED, "enlace declarado a mano")
        for sup in d.supersedes:
            edge(d.id, sup, "SUPERA_A", TIER_EXTRACTED, "enlace declarado a mano")

    for c in commitments:
        node(c.id, c.what, status=c.status, owner=c.owner, due=c.due.isoformat())
        if c.decision_id:
            edge(c.id, c.decision_id, "IMPLEMENTA", TIER_EXTRACTED, "campo obligatorio")

    for a in assumptions:
        node(a.id, a.statement, status=a.status, check_by=a.check_by.isoformat(),
             source=a.source)
        if a.decision_id:
            edge(a.id, a.decision_id, "SOSTIENE", TIER_EXTRACTED, "campo obligatorio")

    for q in questions:
        node(q.id, q.question, status=q.status, resolver=q.resolver)
        for b in q.blocks:
            edge(q.id, b, "BLOQUEA", TIER_EXTRACTED, "enlace declarado a mano")
        if q.reopen_of:
            edge(q.id, q.reopen_of, "REABRE", TIER_EXTRACTED, "campo declarado")

    # Alias confirmados: son aristas de referencia con procedencia humana.
    for al in AliasStore(store.root).load():
        if al.estado == "VIGENTE":
            edges.append({
                "source": f"alias:{al.surface_norm}", "target": al.symbol_id,
                "relation": "REFIERE_A", "confidence": TIER_EXTRACTED,
                "evidence": f"confirmado por {al.confirmado_por} el {al.valido_desde}",
            })

    if not include_inferred:
        edges = [e for e in edges if e["confidence"] == TIER_EXTRACTED]

    ext = sum(1 for e in edges if e["confidence"] == TIER_EXTRACTED)
    return {
        "nodes": nodes,
        "edges": edges,
        "hyperedges": [],
        "meta": {
            "source": "fdekit.decide",
            "regla": "vista derivada del registro; el original vive en git",
            "aristas_extracted": ext,
            "aristas_inferred": sum(1 for e in edges if e["confidence"] == TIER_INFERRED),
            "cobertura": (
                "el grafo contiene SOLO aristas confirmadas o declaradas. Una referencia "
                "que nadie enlazo ni confirmo no aparece: no tratar como exhaustivo."
            ),
        },
    }


def write_graphify(store: DecideStore, out: str | Path, force: bool = False, **kw) -> dict:
    """Escribe el JSON, respetando la compuerta de volumen.

    Bajo ~50 decisiones la deteccion de comunidades re-descubre los titulos de
    la agenda. Los cuatro enfoques del estudio de diseno llegaron a esa
    conclusion por separado, lo que la vuelve su consenso mas fuerte.
    """
    gate = volume_gate(store)
    if not gate["ok"] and not force:
        return {"escrito": False, "motivo": gate["veredicto"], "volumen": gate}

    data = to_graphify(store, **kw)
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "escrito": True,
        "ruta": str(p),
        "nodos": len(data["nodes"]),
        "aristas": len(data["edges"]),
        "volumen": gate,
        "aviso": "" if gate["ok"] else "exportado con --force bajo el minimo de volumen",
    }


def to_mermaid(store: DecideStore, max_nodes: int = 40) -> str:
    """Diagrama para pegar en el A3 o en el reporte al cliente.

    Un grafo completo es ilegible y ese es el error clasico de la primera
    presentacion. Se corta y se dice que se corto.
    """
    data = to_graphify(store)
    ids = {n["id"] for n in data["nodes"][:max_nodes]}
    lines = ["flowchart TD"]
    for n in data["nodes"][:max_nodes]:
        etiqueta = n["label"][:40].replace('"', "'")
        lines.append(f'    {n["id"].replace("-", "_")}["{n["id"]}: {etiqueta}"]')
    for e in data["edges"]:
        if e["source"] in ids and e["target"] in ids:
            lines.append(
                f'    {e["source"].replace("-", "_")} -->|{e["relation"]}| '
                f'{e["target"].replace("-", "_")}'
            )
    if len(data["nodes"]) > max_nodes:
        lines.append(f'    %% cortado: {len(data["nodes"]) - max_nodes} nodos mas no se muestran')
    return "\n".join(lines)
