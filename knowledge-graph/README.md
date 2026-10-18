# FDE Knowledge Graph — Measurement, Trust, Discovery, Structure & Change

Unified knowledge graph connecting **8 foundational books** for Forward Deployed Engineers (FDEs) and Deployment Strategists, plus an integrated **FDE Synthesis Layer** of cross-book insights and end-to-end operational deployment practices.

## Books & Layers Included (`193 nodes`, `488 edges`, `20 external resources`)

| Key | Book / Layer | Authors | Focus in FDE Lifecycle |
|---|---|---|---|
| `htma` | **How to Measure Anything** | Douglas W. Hubbard | Uncertainty reduction, Clarification Chain, 90% CIs, EVPI/EVSI, Monte Carlo |
| `ta` | **The Trusted Advisor** | D. Maister, C. Green, R. Galford | Trust Equation $(C+R+I)/S$, 5-step advisory process, "Name It and Claim It" |
| `mom` | **The Mom Test** | Rob Fitzpatrick | Past-specific discovery, deflecting compliments/fluff, commitment currencies |
| `pp` | **The Pyramid Principle** | Barbara Minto | Answer-First executive memos, SCQA framing, MECE key-line logic, action titles |
| `bps` | **Bulletproof Problem Solving** | Charles Conn, Robert McLean | SMART+ Problem Definition Worksheet, MECE hypothesis trees, 2x2 pruning, heuristics |
| `sw` | **Switch** | Chip Heath, Dan Heath | Rider-Elephant-Path adoption model, bright spots, scripted moves, action triggers |
| `fc` | **Flawless Consulting** | Peter Block | 50/50 collaborative contracting, 9 forms of emotional resistance, neutral naming |
| `cdh` | **Continuous Discovery Habits** | Teresa Torres | Weekly Gemba touchpoints, Opportunity Solution Trees (OST), DVFUE assumption testing |
| `fde` | **FDE Synthesis Layer** | Cross-Book Integration | 18 cross-book insights + 14 FDE field practices chained across the deployment lifecycle |

---

## Architecture & Files

| File / Folder | Purpose |
|---|---|
| `graph.json` | **Single Source of Truth** — 193 nodes, 488 canonical edges, 20 verified external resources |
| `research/*.md` | 8 deep-dive operational dossiers (chapter maps, step-by-step toolkits, conversation scripts, field playbooks) |
| `template.html` | Interactive network viewer template (renders nodes, edges, external links, and embedded Field Playbooks) |
| `build.py` | Validator & compiler: checks canonical predicates, injects dossiers/resources, and generates `out/` |
| `out/index.html` | Self-contained interactive viewer (vis-network) with sidebar playbooks and resource links |
| `out/neo4j.cypher` | Cypher import script using strictly the 12 canonical edge predicates |
| `out/obsidian/` | Obsidian vault with YAML frontmatter, `[[wikilinks]]`, External Resources, and embedded Field Playbooks |

---

## Ontology & Canonical Edge Predicates (12 Types)

To keep Neo4j / Cypher queries clean and expressive, all 488 edges are strictly normalized to **12 canonical predicates**:

- **Structural & Authorship:** `FROM_BOOK` (every book concept links to its `Book` node), `AUTHORED` (`Author` → `Book`), `HAS_COMPONENT`, `HAS_STEP`
- **Analytical & Causal:** `FEEDS` (sequential/enabling flow), `MITIGATES` (technique resolves pitfall/bias), `CAUSES` (pitfall triggers failure mode), `USES`, `MEASURES`
- **Cross-Book & Synthesis:** `SYNTHESIZES` (`CrossInsight` → book concepts), `APPLIES` (`FDEPractice` → frameworks/techniques), `ANALOGOUS_TO` (isomorphic concepts across authors)

---

## Rebuild Outputs

```bash
python build.py
```
