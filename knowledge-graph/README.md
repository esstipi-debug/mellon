# FDE Knowledge Graph — Measurement, Trust & Customer Discovery

Knowledge graph connecting **How to Measure Anything** (Hubbard), **The Trusted Advisor** (Maister, Green, Galford) and **The Mom Test** (Fitzpatrick), with a synthesis layer of cross-book insights and FDE practices.

> Built from general knowledge of the books (no book text ingested). Descriptions are paraphrases, not quotes.

## Files
| File | Purpose |
|---|---|
| `graph.json` | **Source of truth** — edit nodes/edges here |
| `template.html` | Interactive viewer template |
| `build.py` | Validates the graph and generates `out/` |
| `out/index.html` | Interactive graph (open in a browser; loads vis-network from a CDN) |
| `out/neo4j.cypher` | Neo4j import script (`cypher-shell -f out/neo4j.cypher`) |
| `out/obsidian/` | Obsidian vault (open the folder as a vault; use Graph View) |

## Model
- **Node types:** Book, Author, Concept, Framework, Principle, Technique, Pitfall, CrossInsight, FDEPractice
- **Layers (`book`):** `htma`, `ta`, `mom`, `fde` (synthesis)
- **Key edges:** `HAS_STEP`, `HAS_COMPONENT`, `MITIGATES`, `INCREASES`, `CAUSES`, `ANALOGOUS_TO`, `SYNTHESIZES` (cross-insight → source concepts), `APPLIES` (FDE practice → concepts), `FEEDS` (practice workflow)

## Rebuild
```
python build.py
```
