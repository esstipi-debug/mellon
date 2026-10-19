# FDE Knowledge Graph + 🥋 FDE Field Dojo

A single, offline-first knowledge platform for **Forward Deployed Engineers (FDEs) and Deployment Strategists**: a validated 8-book knowledge graph, a tactical dossier per book, an interactive graph viewer, an Obsidian vault, a Neo4j import script, and a gamified training simulator — the **FDE Field Dojo** with 42 field scenarios (covering **100% of all 173 trainable nodes** across `Concept`, `Principle`, `Framework`, `Technique`, `Pitfall`, `FDEPractice`, and `CrossInsight`), 6 real Palantir deployment cases, 2 `fdekit` CD Pudahuel bridge cases, two 5-day AIP Bootcamp campaigns, 7 Artifact Forge missions, a 20-question 90% CI calibrator with Fermi decomposition scratchpad, and voice-enabled sparring.

The graph is the source of truth. `build.py` compiles every surface from it, validates all references, and fails closed if data is broken.

---

## 1. What is in the box

### Books & layers (`193 nodes · 488 edges · 20 external resources`)

| Key | Book / layer | Authors | Nodes | Focus in the FDE lifecycle |
|---|---|---|---:|---|
| `htma` | **How to Measure Anything** | Douglas W. Hubbard | 25 | Uncertainty reduction, Clarification Chain, 90% CIs, EVPI/EVSI, Monte Carlo, Rule of Five |
| `ta` | **The Trusted Advisor** | D. Maister, C. Green, R. Galford | 24 | Trust Equation $(C+R+I)/S$, five-step advisory process, "Name It and Claim It" |
| `mom` | **The Mom Test** | Rob Fitzpatrick | 25 | Past-specific discovery, deflecting compliments/fluff, commitment currencies, Zombie Leads |
| `pp` | **The Pyramid Principle** | Barbara Minto | 15 | Answer-first executive memos, SCQA, MECE key-line logic, action titles |
| `bps` | **Bulletproof Problem Solving** | Charles Conn, Robert McLean | 18 | SMART+ problem definition, MECE hypothesis trees, 2×2 pruning, red teaming |
| `sw` | **Switch** | Chip Heath, Dan Heath | 20 | Rider–Elephant–Path adoption model, bright spots, scripted moves, action triggers |
| `fc` | **Flawless Consulting** | Peter Block | 16 | 50/50 contracting, forms of emotional resistance, neutral naming, feedback meetings |
| `cdh` | **Continuous Discovery Habits** | Teresa Torres | 18 | Opportunity Solution Trees, story-based interviews, assumption mapping and testing |
| `fde` | **FDE Synthesis Layer** | Cross-book integration | 32 | 18 cross-book insights + 14 end-to-end FDE field practices chained across the deployment lifecycle |

Node types: `Book`, `Author`, `Concept`, `Framework`, `Principle`, `Technique`, `Pitfall`, `CrossInsight`, `FDEPractice`.

### Palantir field cases (`case_study: "palantir"`)

| ID | Organization | Deployment situation | Winning FDE move |
|---|---|---|---|
| `scen_28_palantir_airbus` | Airbus Skywise | A350 ramp-up, recurring wiring/cabin non-conformities, 15 isolated systems, VP demands an 18-month Data Lake | 3 tables → one hangar-1 bottleneck this week; bright spots + small sample; no global lake wait |
| `scen_29_palantir_tyson` | Tyson Foods | $200M inventory allocation opportunity; veteran planners switch off recommendations and keep Excel | Name the loss of expert judgment; human-in-the-loop changeset for 5 high-waste SKUs, signed by planners |
| `scen_30_palantir_nhs` | NHS England | 200 hospitals, 48-hour stock lag, 18% duplicate/incomplete records; committee refuses the reallocation board | Clarification chain + calibrated 90% ranges + answer-first triage threshold that survives the 18% noise |
| `scen_31_palantir_pge` | Pacific Gas & Electric | 40,000 fire-risk assets; engineering wants 14 more weather variables; foremen request 200 mobile UI features | Dig into the foremen's last failed alert; 2×2 impact/influence + EVPI filter; dispatch 5 critical inspections per shift |
| `scen_32_palantir_jacobs` | Jacobs Engineering | Water plant operator says "whatever you say" without discussing night-shift dosing | Name the passive yes; ask for the last failed automatic alert story; co-design the dosing routine |
| `scen_33_palantir_cleveland` | Cleveland Clinic | 5 minutes with the CFO to decide a 12-hospital rollout; team brings 30 chronological HL7 slides | Answer-first Go/No-Go in waves, 3 MECE reasons, calibrated nursing-hours range and a stop trigger |

These six cases are **training syntheses inspired by publicly reported deployment patterns**, not official, confidential or endorsed Palantir material. Organization names frame the operating context; the stakeholder quotes and decisions are constructed for practice.

### Files and outputs

| File / folder | Purpose |
|---|---|
| `graph.json` | **Single source of truth** — nodes, canonical edges, external resources |
| `research/<book>.md` | 8 tactical dossiers: chapter map, step-by-step toolkits, official resources, field playbook and word-for-word scripts |
| `research/<book>.graph-additions.json` | Research deltas merged with `research/merge_research.py` |
| `scenarios.json` | Dojo bank: **42 field scenarios** (6 Palantir + 2 `fdekit` CD Pudahuel), **2 Bootcamps / 10 stages**, **7 Forge missions**, **20 calibration questions**, **8 sparring contexts**, 5-dimension rubric |
| `template.html` | Graph viewer template (vis-network, dark theme, resources, playbook modal, Dojo CTA) |
| `dojo_template.html` | FDE Field Dojo SPA template (5 training modes, localStorage state, no runtime dependencies) |
| `vendor/vis-network.min.js` | Vendored vis-network 9.1.9 so the viewer works offline |
| `build.py` | Fail-closed compiler: validates graph + scenario bank + 100% node coverage, normalizes predicates, compiles all outputs |
| `out/index.html` | Self-contained graph viewer with embedded dossiers and external resources |
| `out/dojo.html` | FDE Field Dojo (fully offline; BYOK chat is the only optional network feature) |
| `out/graph.json` | Validated, predicate-normalized copy of the graph |
| `out/neo4j.cypher` | Cypher import script using strictly the 12 canonical predicates |
| `out/obsidian/` | Obsidian vault: one note per node, `[[wikilinks]]`, External Resources, and the tactical dossier appended to every Book note |

---

## 2. Build

Requires only **Python 3.10+** (standard library, no dependencies).

```bash
cd C:\fde\repo-mytra-fde\knowledge-graph
python build.py
```

Output:

```text
OK graph: 193 nodes, 488 edges, 20 resources, 9 layers
OK dojo bank: 42 scenarios (6 Palantir), 20 calibration questions, 8 contexts, 2 bootcamps / 10 stages, 7 forge missions, 173/173 trainable nodes covered (100%)
OK vendor: vendor/vis-network.min.js (688,911 bytes, offline viewer)
OK build: 193 nodes, 488 edges, 20 resources, 8 dossiers, 42 scenarios, 20 calibration questions, 2 bootcamps / 10 stages
  - out/index.html
  - out/dojo.html
  - out/graph.json
  - out/neo4j.cypher
  - out/obsidian/  (193 notes + 00 Index.md)
```

`out/` is rebuilt from scratch on every run: never edit generated files.

Optional: rebuild the graph after editing research dossiers:

```bash
cd C:\fde\repo-mytra-fde\knowledge-graph
python research/merge_research.py
python build.py
```

`merge_research.py` normalizes legacy research predicates with `build.PREDICATE_ALIASES` before deduplicating, so merging can never reintroduce a non-canonical or duplicated edge.

### Validation guarantees (build fails with a non-zero exit code)

- Duplicate node ids, blank labels/descriptions, unknown types or layers.
- Edges referencing unknown nodes, self-loops, duplicate edges, non-canonical predicates.
- Orphan nodes (no incoming or outgoing edge).
- Book nodes without `FROM_BOOK`/`AUTHORED` wiring; labels colliding inside an Obsidian folder.
- Invalid resources (unknown `node_id`, non-HTTP URL, missing title/kind).
- Scenario bank: at least 33 scenarios (currently 42), at least 3-per-book coverage, duplicate ids, unknown node ids, wrong node types, missing/duplicate correct options, bad metric keys or deltas, at least 15 calibration questions (currently 20), non-numeric answers, invalid sparring contexts/rubric, at least 6 forge missions (currently 7), and **100% coverage of all 173 non-Book/non-Author nodes**.
- **Palantir cases:** at least 6 cases with `case_study: "palantir"`, `case_org`, and `difficulty: "boss"`; the six canonical ids `scen_28_palantir_airbus` … `scen_33_palantir_cleveland` are required.
- **Bootcamps:** 2 campaigns (`camp_skywise_supply`, `camp_retail_nosilo`), 5 ordered stages each, canonical day themes, `start_metrics` at 55, loss threshold 30, win threshold 65 / average 75, at least 3 options per stage with exactly one best option, and valid graph nodes on every stage.
- **Anti-gaming:** diagnosis texts, action labels and scripts are checked for named books/frameworks/techniques; diagnosis texts and labels must be length-balanced (max/min ≤ 1.25). Leaking `MECE`, `Rule of Five`, `Confirmation Bias`, etc. into option content aborts the build. Scripts are additionally hidden by the UI until the user selects an option, so their length cannot be used as a tell.
- A scenario or forge mission that references a node id absent from `graph.json` **aborts the build** (see `load_scenarios()` in `build.py`).

---

## 3. FDE Field Dojo (`out/dojo.html`)

A gamified, offline-first trainer for field conversations. The Dojo embeds a compact copy of the graph, all 42 scenarios, both Bootcamp campaigns, all 7 Artifact Forge missions, the 20-question calibration bank and the dossiers, so it runs from `file://` or any static server with no API.

### 3.1 HUD and persistence

Four live metrics (0–100), persisted in `localStorage["fde_dojo_state_v1"]` with full **Export / Import (`.json`)** backup in the progress modal:

| Metric | Source | Rises with | Falls with |
|---|---|---|---|
| **TQ** Trust Quotient | Maister | Listening, naming resistance without attacking, honesty | `ta_need_to_be_right`, premature pitching, self-orientation |
| **SIG** Signal Quality | Fitzpatrick & Torres | Past-specific facts, stories, real commitments | Compliments, future opinions, features without pain |
| **EVI** Information Value | Hubbard & Conn | Defining the decision, Rule of Five, MECE decomposition, riskiest assumption first | Measurement inversion, analysis paralysis |
| **ADP** Adoption Momentum | Block & Heath | 50/50 contracting, neutral naming, Rider + Elephant + Path | Fighting resistance with more data, instant compliance |

Also persisted: XP, daily streak, per-scenario accuracy, **spaced repetition queue** (`box` levels 0–5 with 10 min / 1 / 3 / 7 / 14 / 30-day intervals), calibration history, sparring history, forge history and last mode.

### 3.2 Mode 1 · Tactical Reflex Dojo

- **42 high-fidelity scenarios**: 30 book cases + 4 FDE synthesis + **6 Palantir field cases** (Airbus, Tyson Foods, NHS England, PG&E, Jacobs, Cleveland Clinic) + **2 `fdekit` CD Pudahuel bridge cases** (`scen_41_fdekit_gemba_dq`, `scen_42_fdekit_value_spc`), achieving **100% coverage** across all **173 trainable nodes** (`Concept` 25/25, `Principle` 15/15, `Pitfall` 15/15, `FDEPractice` 14/14, `Technique` 59/59, `Framework` 12/12, and `CrossInsight` 18/18, plus 15 additional conceptual nodes).
- **Anti-gaming by design:** options are shuffled per session with a seeded Fisher-Yates (the correct answer is never pinned to the first card); pre-answer labels/texts carry no framework names and are length-balanced; the exact scripts stay hidden until you choose, so you cannot pick the longest or most jargon-heavy option.
- Two steps: **diagnosis first**, then the **exact verbal action/script**.
- Every option carries deltas for TQ/SIG/EVI/ADP, detailed feedback and the best-action script to compare against.
- Clickable node pills call the real graph nodes: `active_pitfalls`, `target_techniques`, `supporting_nodes`, `target_practice` — opening a full node card with description, external resources, incoming/outgoing relations, direct buttons to train the node in Mode 1 or Mode 5, and a link back to the viewer.
- Filters by phase, by book/layer, "Solo fallados", **"Entrenar mis puntos débiles"**, **"⏱ Repaso espaciado"** and **"🏛️ Solo Casos Palantir (6)"**.
- Failing diagnosis or action marks the scenario `needsReview` and schedules it for review; a clean attempt advances the spaced-repetition box. The **⏱ Repaso espaciado (N)** button plays the overdue queue directly.
- **Random Boss Fight** equivalent: "Escenario aleatorio" for Mode 1, "Random Boss Fight" for Mode 3.
- Keyboard: `1–4` select an option, `Enter` / `→` advances to the next scenario/day, `Esc` closes modals.

### 3.3 Mode 2 · Hubbard 90% CI & Equivalent Bet Trainer

- **20 quantitative questions** mixing FDE field metrics (ERP phantom inventory rate, ICU/plant alarm fatigue, binomial Rule of Five extension, Pendo feature non-adoption rate, automotive downtime cost per minute) with operational and technical facts.
- **🧮 Fermi Decomposition Scratchpad (`htma_decomposition`):** break down the unknown quantity into known factors (`units × rate × hours`) right inside the card and apply a `÷2` to `×2` Fermi anchor before locking your interval.
- Enter a `[min, max]` interval, then face the **90% wheel**: 90% green wins $1,000 vs. 10% red wins $0. Widen the range ("estoy sobreconfiado") or lock it ("estoy indiferente").
- After locking, the true value, source, range width (max/min) and an explanation are revealed.
- Live SVG **calibration chart**: cumulative hit rate per question, colored hits/misses, 90% target line.
- Verdict logic: `<75%` → **Sobreconfianza** (`htma_overconfidence`), `>95%` → **Subconfianza**, `80–92%` → **Calibrado**, plus near-miss bands. Overly wide ranges are flagged as uninformative even when they hit.
- Round summary with median range width, failed-question reinforcement round and node drills (`htma_equivalent_bet`, `htma_ci90`, `htma_calibration`).

### 3.4 Mode 3 · Live Sparring Generator & Rubric Evaluator

- Build a mission from the graph: **operational context** (8 real deployment situations, including two Palantir Bootcamp/revolt contexts), **target FDEPractice** (14), **2 hidden Pitfalls** and a **secret emotional objection**.
- The generated **8-turn system prompt**:
  - locks the LLM into the stakeholder persona and forbids breaking character;
  - hides the pitfalls/objection (they must appear as behavior, not exposition);
  - defines escalation/de-escalation rules (pitch → more resistance; naming/evidence → gradual concession);
  - at turn 8 or `/evaluar`, emits a **strict JSON audit** scored 0–100 against the exact graph nodes in the rubric.
- **Option A · Copy-paste + Paste-Back Audit (no API key):** copy the prompt into Claude/ChatGPT/Gemini, run the 8-turn session, and **paste the `/evaluar` response or JSON block back into Tab A** (or trigger manual self-evaluation) to render the visual 5-dimension rubric and update your HUD.
- **Option B · Chat BYOK (optional):** OpenAI, Anthropic or Google Gemini, key stored only in `localStorage["fde_dojo_api_v1"]`. Calls go directly from the browser to the provider. If CORS/network blocks the call, the UI falls back to a **manual self-evaluation**.
- **🎙️ Push-to-Talk voice input:** the browser-native `SpeechRecognition` / `webkitSpeechRecognition` API with `es-CL` / `en-US` selection. The button toggles listening, streams interim results into the chat box, and degrades gracefully (disabled button + explanation) when the browser or context does not support speech.
- Rubric: 5 dimensions × 20 points (`Trust & Contracting`, `Signal Quality`, `Information Value`, `Adoption & Resistance`, `Executive Synthesis`), with `nodes_used` / `nodes_missed` citations. The result is applied back to the HUD and stored in sparring history.

### 3.5 Mode 4 · 5-Day AIP Bootcamp Gauntlet

Two chained campaigns model the Palantir AIP Bootcamp standard: go from zero to a real operational flow in one work week.

| Campaign | Sector | Five days |
|---|---|---|
| `camp_skywise_supply` · **Operación Skywise & Supply Chain Cutover** | Heavy manufacturing / Aerospace | Contracting → Gemba & dirty-data ontology → Prototype & Human-in-the-loop guardrails → Operator rebellion → Executive Go/No-Go |
| `camp_retail_nosilo` · **Operación NoSilo: Sincronización Comercial + Bodega WMS** | Retail / Multichannel distribution | Same five-stage chain across Sales, Supply Chain, WMS and store operations |

- **Start state:** TQ/SIG/EVI/ADP all at **55**. Deltas from Day 1 carry into Day 2 and so on because they move the **real HUD bars**, and each stage displays a **narrative carryover banner** reflecting whether the previous day's move left political capital or tactical friction.
- **Defeat:** if any metric falls below **30** at any day, the client cancels (`Account Lost / Pilot Cancelled`) and you get a post-mortem with the failing bar and the nodes to drill.
- **Victory:** finish Friday with **all four metrics ≥65** and an **average ≥75** (`Production Contract Signed`).
- Every stage is validated against `graph.json` (`active_pitfalls`, `target_techniques`, `supporting_nodes`, `target_practice`) and options are shuffled with hidden scripts and `1–4` keyboard shortcuts, like Mode 1.
- Progress is persisted in `localStorage["fde_dojo_state_v1"]` under `bootcamp`, so a reload resumes the same day and decision state.

### 3.6 Mode 5 · 🛠️ Artifact Forge & EVPI Lab (Deterministic Local Linter)

- **7 production-writing missions across 3 FDE Artifact Archetypes** (stored in `scenarios.json` under `forge_missions` and validated by `build.py`; zero API key required):
  1. **Memorando Ejecutivo SCQA + Answer-First (Minto + Hubbard):** `forge_scqa_nhs` (NHS 200 hospitals), `forge_scqa_airbus` (Airbus A350 Hangar 1 vs. 18-month Data Lake), and `forge_scqa_pudahuel` (`fdekit` CD Pudahuel WMS wave consolidation + SPC stop-loss).
  2. **Guion de Descubrimiento & Resistencia (Mom Test + Peter Block + Teresa Torres):** `forge_mom_tyson` (Tyson Foods planners turning off recommendations), `forge_mom_pge` (PG&E foremen giving compliments and 200 feature requests).
  3. **Hoja de Problema SMART+ & Árbol MECE + EVPI (Conn & McLean + Hubbard):** `forge_bps_port` (Port terminal demurrage penalties), `forge_bps_pharma` (Pharma cold-chain $400k/quarter spoilage).
- **Deterministic 5-Rule Local Linter (0–100 pts):** checks your written artifact for Answer-First opening, absence of chronological pipeline dumps (`pp_chronological_dump`), quantified Complication tension (`pp_scq`), explicit 90% calibrated ranges (`htma_ci90`), MECE key-line pillars (`pp_mece`), reversal stop-triggers (`fde_go_no_go`), zero future conditionals (`mom_fluff`), neutral resistance naming (`fc_naming_protocol`), past-specific story anchors (`mom_past_specifics`, `cdh_story_interview`), workaround probes (`mom_workarounds`), commitment currencies (`mom_commitment`), SMART+ decision framing without solution fixation (`bps_define`, `cdh_whether_or_not`), 2×2 pruning (`bps_prioritize_2x2`), and Rule-of-Five sampling (`htma_rule_of_five`).
- **Gold Standard Comparison:** inspect or load the master FDE artifact side-by-side to compare phrasing and structure.
- **🧮 Interactive EVPI & Rule-of-Five Calculator:** live sidebar calculator computing Expected Opportunity Loss ($\text{EOL} = P_{\text{error}} \times C_{\text{error}}$), Expected Value of Sample Information ($\text{EVSI}$), Net Measurement Value, and exact binomial median confidence ($1 - 2 \cdot 0.5^n$) for small field samples ($n=5 \Rightarrow 93.75\%$, $n=7 \Rightarrow 98.4\%$).

### 3.7 Deep links

| URL | Effect |
|---|---|
| `out/index.html#fc_naming_protocol` | Opens the viewer focused on a node |
| `out/dojo.html#node=fc_naming_protocol` | Filters Dojo scenarios that train that node |
| `out/dojo.html#scen=scen_25_cutover_go_no_go` | Opens a specific scenario |
| `out/dojo.html#mode=calibration` (`#cal`) | Opens the calibration trainer |
| `out/dojo.html#mode=bootcamp` | Opens the 5-Day AIP Bootcamp selector |
| `out/dojo.html#mode=forge` | Opens the Artifact Forge & EVPI Lab |
| `out/dojo.html#mode=sparring` | Opens the sparring generator |

The viewer and the Dojo link to each other from their top navigation, and every node card in the viewer has a green **"🥋 Entrenar en el Dojo"** button.

---

## 4. Ontology & canonical edge predicates

The original 59-predicate vocabulary (35 single-use verbs) was consolidated into **12 canonical predicates**. Direction is preserved: when a legacy verb pointed "backwards" semantically, endpoints were swapped.

| Predicate | Meaning |
|---|---|
| `FROM_BOOK` | Node belongs to a Book layer (concept → `book_*`) |
| `AUTHORED` | Author → Book |
| `HAS_STEP` | Framework → ordered step/technique |
| `HAS_COMPONENT` | Whole → part / rule / manifestation |
| `FEEDS` | Enabling or sequential flow between concepts, techniques, phases or artifacts |
| `USES` | A node relies on another method/component |
| `MITIGATES` | Technique/framework reduces a Pitfall or bias |
| `CAUSES` | Node produces another state/pitfall |
| `MEASURES` | Instrument/technique measures a concept |
| `SYNTHESIZES` | Cross-book insight → source concepts |
| `APPLIES` | FDE practice/principle operationalizes a book concept |
| `ANALOGOUS_TO` | Isomorphic concepts across authors |

`build.py` keeps `PREDICATE_ALIASES`: the full legacy→canonical mapping (including direction inversions for `PRODUCED_BY`, `RESOLVED_BY`, `MEASURED_IN`, `PART_OF`, etc.). Hand-edited data that reintroduces an old verb is normalized automatically; an unknown predicate aborts the build. The Cypher export and the viewer therefore only ever see the 12 canonical predicates.

---

## 5. Obsidian & Neo4j

**Obsidian** (`out/obsidian/`):

- One note per node in folders `01 How to Measure Anything` … `08 Continuous Discovery Habits` and `99 FDE Synthesis`.
- YAML frontmatter (`id`, `type`, `book`, `tags`), `[[wikilinks]]` for every relation, and an `00 Index.md`.
- `## External Resources` with `- [title](url) _(kind)_` for every node with resources; Book notes aggregate all resources of their layer.
- Book notes append the full `research/<book>.md` dossier under `## Tactical Field Dossier`, with headings demoted one level to keep the vault outline clean.

**Neo4j** (`out/neo4j.cypher`):

```cypher
MATCH (n:KGNode) DETACH DELETE n;
CREATE CONSTRAINT kg_id IF NOT EXISTS FOR (n:KGNode) REQUIRE n.id IS UNIQUE;
// CREATE (:KGNode:Book {id:"book_htma", ...});
// MATCH (a {id:"..."}), (b {id:"..."}) CREATE (a)-[:FEEDS]->(b);
```

Useful queries are included at the end of the file (cross-book synthesis, shortest path to an FDE practice, pitfalls mitigated per book, practices reachable from a framework).

---

## 6. Edge cases & data policy

- **Offline-first:** `out/dojo.html` has no external requests. `out/index.html` uses the vendored `vendor/vis-network.min.js`; if the vendor file is missing at build time, `build.py` falls back to the unpkg CDN and prints a warning.
- **No book text ingested:** all graph descriptions are paraphrases; `research/*.md` are operational synthesis dossiers, not reproductions. Palantir case scenarios are training syntheses from public patterns, not confidential client material.
- **Voice data:** the Dojo does not record or store audio; the browser's speech service returns text that is placed in the chat box and is only sent to an LLM if you explicitly use the BYOK chat.
- **API keys:** never sent anywhere except the chosen provider; stored only in the browser's `localStorage`. Clear it with "Reiniciar todo" in the progress panel or by removing the `fde_dojo_api_v1` key.
- **Voice input:** uses the browser's SpeechRecognition service; audio is not stored by the Dojo. Chrome/Edge may require `http://localhost` or HTTPS and microphone permission. When unavailable, the button is disabled with an explanation and text input remains fully functional.
- **Reset progress:** the progress panel exposes `Exportar progreso (.json)` and `Reiniciar todo`.
- **Independence:** the Dojo never writes to `graph.json` or `out/`; it only reads the embedded payload.

---

## 7. Verification checklist

```bash
cd C:\fde\repo-mytra-fde\knowledge-graph
python build.py
```

Then:

1. `out/index.html` opens the graph; the sidebar shows `193 nodes · 488 edges · 20 external resources · 8 embedded field playbooks`.
2. The prominent **🥋 Ir al FDE Field Dojo** button opens `out/dojo.html`; the Dojo's **🕸 Grafo** link returns to `out/index.html`.
3. In the Dojo, complete a scenario: the HUD moves, feedback and node pills appear, and failing marks the scenario as `needs review`. Confirm the correct answer is not always the first card and that option scripts stay hidden until you choose.
4. Click **🏛️ Solo Casos Palantir (6)** and verify exactly six boss cases, including Airbus, Tyson, NHS, PG&E, Jacobs and Cleveland.
5. In calibration, submit a range, use the wheel/widen flow, lock it, and confirm the real value and cumulative chart.
6. In sparring, generate a mission, copy the prompt, confirm it contains the hidden state rules and JSON audit schema, and verify the **🎙️ Hablar (Push-to-Talk)** button degrades gracefully if SpeechRecognition is unavailable.
7. Open **🏛️ 5-Day Bootcamp**, start a campaign, verify all HUD bars reset to 55, play five days, and confirm either `Production Contract Signed` or `Account Lost / Pilot Cancelled` with a post-mortem.
8. `out/obsidian/` contains 193 notes + `00 Index.md`; Book notes end with `## Tactical Field Dossier` and node notes with resources show `## External Resources`.
9. `out/neo4j.cypher` contains only the 12 canonical predicates.

To confirm the fail-closed validation, temporarily point a scenario at a fake node id (or duplicate a node id) and run `python build.py`: it must exit with `BUILD FAILED — scenarios.json: ... references unknown node id ...` and not produce a partial `out/`.
