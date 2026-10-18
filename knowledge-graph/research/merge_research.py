"""Merge research/*.graph-additions.json into graph.json (idempotent).

- Adds new nodes (skips existing ids), edges (skips duplicates / unknown ids),
  resources (dedupe by node_id+url) and applies description corrections.
- Legacy research predicates are normalized with build.PREDICATE_ALIASES before
  deduplication so merging never reintroduces non-canonical or duplicated edges.
Usage:  python research/merge_research.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import CANONICAL_PREDICATES, PREDICATE_ALIASES  # noqa: E402

GRAPH = ROOT / "graph.json"
ALLOWED_TYPES = {"Concept", "Framework", "Principle", "Technique", "Pitfall", "FDEPractice", "CrossInsight"}

g = json.loads(GRAPH.read_text(encoding="utf-8"))
g.setdefault("resources", [])
ids = {n["id"]: n for n in g["nodes"]}
edge_keys = {(e["source"], e["relation"], e["target"]) for e in g["edges"]}
res_keys = {(r["node_id"], r["url"]) for r in g["resources"]}

for f in sorted((ROOT / "research").glob("*.graph-additions.json")):
    add = json.loads(f.read_text(encoding="utf-8"))
    stats = dict(nodes=0, edges=0, resources=0, corrections=0, skipped=0)
    for n in add.get("nodes", []):
        if n["id"] in ids or n.get("type") not in ALLOWED_TYPES or n.get("book") not in g["meta"]["books"]:
            stats["skipped"] += 1
            continue
        node = {k: n[k] for k in ("id", "label", "type", "book", "description")}
        g["nodes"].append(node)
        ids[n["id"]] = node
        stats["nodes"] += 1
    for e in add.get("edges", []):
        source, target = e["source"], e["target"]
        relation = e["relation"].upper()
        if relation not in CANONICAL_PREDICATES:
            if relation not in PREDICATE_ALIASES:
                stats["skipped"] += 1
                continue
            relation, inverted = PREDICATE_ALIASES[relation]
            if inverted:
                source, target = target, source
        k = (source, relation, target)
        if k in edge_keys or source not in ids or target not in ids:
            stats["skipped"] += 1
            continue
        g["edges"].append({"source": source, "target": target, "relation": relation})
        edge_keys.add(k)
        stats["edges"] += 1
    for r in add.get("resources", []):
        k = (r.get("node_id"), r.get("url"))
        if not r.get("url") or k in res_keys or r.get("node_id") not in ids:
            stats["skipped"] += 1
            continue
        g["resources"].append({"node_id": r["node_id"], "title": r["title"], "url": r["url"], "kind": r.get("kind", "article")})
        res_keys.add(k)
        stats["resources"] += 1
    for c in add.get("corrections", []):
        if c.get("id") in ids and c.get("description"):
            ids[c["id"]]["description"] = c["description"]
            stats["corrections"] += 1
    print(f"{f.name}: {stats}")

GRAPH.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"TOTAL: {len(g['nodes'])} nodes, {len(g['edges'])} edges, {len(g['resources'])} resources")
