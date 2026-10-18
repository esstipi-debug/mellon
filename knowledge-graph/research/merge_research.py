"""Merge research/*.graph-additions.json into graph.json (idempotent).

- Adds new nodes (skips existing ids), edges (skips duplicates / unknown ids),
  resources (dedupe by node_id+url) and applies description corrections.
Usage:  python research/merge_research.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
        k = (e["source"], e["relation"].upper(), e["target"])
        if k in edge_keys or e["source"] not in ids or e["target"] not in ids:
            stats["skipped"] += 1
            continue
        g["edges"].append({"source": k[0], "target": k[2], "relation": k[1]})
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
