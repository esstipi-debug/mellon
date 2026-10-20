# Mellon 🗝️ & Ithildin 🌌

> **The right word to open any gate.**  
> *A repository for seamless integration, secure authentication, and deployment strategies that just work.*  
> **(A Deployment Strategist Playbook)**

---

## 1. The Myth, the Gate, and the Invisible Inscription

At the Doors of Durin, which guarded the western entrance to Khazad-dûm (Moria), two legendary creations converged:

$$\text{\textit{Ennyn Durin Aran Moria: pedo mellon a minno.}}$$

1. **The Invisible Inscription (*Ithildin*):** Crafted by Celebrimbor from *mithril*, Ithildin remained completely invisible under normal light. It reflected only starlight and moonlight when spoken to with the proper words. It represents our passive infrastructure: deterministic guardrails ([`fdekit.ithildin`](src/fdekit/ithildin/)), silent telemetry, and event-driven conditional triggers.
2. **The Password (*Mellon*):** Written on the gate in that exact substance, the inscription read literally: **"Speak, friend, and enter."** Gandalf spent hours chanting incantations of command and spells of siege, assuming an exclusionary obstacle. The gate was never locked with malice; it waited only for the invocation of an alliance between those who build together. In field engineering, the **Deployment Strategist** is the friend who steps onto the *Gemba*, aligns with operations, and eliminates the 95% failure rate of enterprise AI.

---

## 2. The Doctrine of *Mellon*: Becoming "Friends of Operations"

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 THE ENTERPRISE GATEWAY                  │
                  │             (IT, InfoSec, Operations, P&L)              │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       │                                               │
                       ▼                                               ▼
         [The Saruman Approach: Siege & Imposition]     [The Gandalf / Mellon Approach: Alliance]
         • Confined to ivory tower IDEs & slides        • The Pilgrim (Mithrandir) on the floor
         • Contempt for front-line operators            • Friend of every enterprise tribe
         • Imposes abstract AI without listening        • Exchanges knowledge, absorbs fatigue
         • IT vetoes & users reject system              • Deterministic safety + Lasting adoption
                       │                                               │
                       ▼                                               ▼
                  GATE CLOSED                                     GATE OPEN
             (95% Pilot Failure Rate)                        (Value in Production)
```

### A. The Archetype of Gandalf vs. Saruman's Ivory Tower
In Tolkien's lore, Saruman secluded himself inside the tower of Orthanc: enamored with abstract mechanisms, hierarchy, and top-down control, he grew contemptuous of everyday people and fell victim to his own intellectual hubris.

**Gandalf was *Mithrandir*, the wanderer.** He had no throne, crown, or private army. His transformative influence stemmed from being **the friend (*mellon*) of all peoples**:
* He walked the Shire alongside Hobbits, understanding their daily lives and real concerns.
* He sat at the tables of Dwarves in the mountains, respecting their pride and craftsmanship.
* He rode with the Men of Rohan and Gondor, translating strategic foresight into urgent field action.
* He conversed with Elves in Rivendell and Lórien, honoring their wisdom and memory.

It was this condition as a **universal friend** that allowed him to bridge ancient divides between distrustful cultures, facilitate the exchange of knowledge, and forge the alliances required to overcome challenges no single realm could face alone.

### B. The Tribal Fracture in the Modern Enterprise
In any physical enterprise, tribes operate behind walled silos:
* **Operations (The Floor, The Warehouse, The Plant):** The people moving physical freight, enduring heat, dust, physical fatigue, and managing undocumented exceptions. They harbor a healthy skepticism toward "corporate IT initiatives," knowing that the people designing them have never worked a night shift in a picking aisle.
* **Software Engineers & Data Scientists:** Confined to remote monitors and Jupyter notebooks, modeling reality on theoretical assumptions. When an AI pilot fails on the floor, they blame the users: *"the operators resist change and do not log data properly."*
* **Cybersecurity & IT Infrastructure:** Stewards of business continuity who legitimately block deployments out of well-founded fears that an unmonitored script or model will corrupt transactional ERP databases or violate regulatory frameworks.
* **Finance & Executive Leadership:** Pressuring for immediate ROI on spreadsheets while remaining blind to the friction of physical execution.

When an outside consultant arrives like Saruman—promising sweeping revolutions from the executive boardroom, speaking in foreign buzzwords, and attempting to force software onto the floor—operations mounts an immune response. **This tribal misalignment is the exact causal mechanism behind the 95% failure rate of enterprise AI pilots (MIT / RAND, 2026).**

### C. We Must Be *Mellon* to Enter Operations
To deploy software and Artificial Intelligence that survives, scales, and transforms business operations, **we must be *Mellon*:**

1. **Enter the Gemba as a Friend, Not as an Auditor (*Genchi Genbutsu*):**
   We put on steel-toed boots, walk the aisles alongside operators, listen to their frustrations with humility, and understand where the process genuinely breaks down.
2. **A Genuine Exchange of Knowledge:**
   Operations entrusts us with the ground truth missing from standard manuals: where the physical process stalls, which shadow spreadsheets keep the shift running, and how exceptions are handled. In return, the Deployment Strategist delivers tools that respect their labor, automations that absorb cognitive drudgery, and guardrails that ensure systems never leave them stranded.
3. **The Human Handshake and the Cryptographic Handshake:**
   *Mellon* operates across two inseparable planes:
   * **The Human Plane:** Cultivates the psychological safety necessary for supervisors and operators to welcome AI as a collaborative shift partner (*Human-in-the-Loop*).
   * **The Technical Plane (*Ithildin*):** Provides IT and InfoSec with immutable data contracts, HMAC-SHA256 safe-staging writebacks, and deterministic rollback plans—giving enterprise architects mathematical certainty of zero transactional corruption.
4. **"Speak Friend and Enter":**
   The password is not an impossible technical trick. When you become a trusted partner to operations, the operation opens its own gates, delivers its real data, and champions the deployment to production success.

---

## 3. The Dual Operating Model: Mellon 🗝️ & Ithildin 🌌

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 MELLON 🗝️                                    │
│                    Human Alliance & Field Adoption Protocol                 │
│   • Speak the Gemba dialect (floor terms, zero LLM jargon)                  │
│   • Human-in-the-Loop: the agent assists, the operator validates             │
│   • Frictionless native channels (WhatsApp, RF scanners, CLI)               │
│   • TWI (Training Within Industry) & sustained floor Hypercare              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                ITHILDIN 🌌                                   │
│                  Passive Infrastructure & Deterministic Guardrails          │
│   • Dual-Track Architecture: AI proposes -> Deterministic engine validates   │
│   • Cryptographic Safe-Staging: HMAC-SHA256 & mandatory idempotency         │
│   • Silent telemetry: Read-only probes over 5 canonical columns             │
│   • Dormant conditional triggers: event-reactive, zero continuous polling   │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **Development Guidelines:** Consult [`MELLON-ITHILDIN-GUIDELINES.md`](MELLON-ITHILDIN-GUIDELINES.md) for dual-track architecture, HMAC-SHA256 guardrails, and agent production rubrics.  
> **Role Doctrine:** Consult [`DEPLOYMENT-STRATEGIST.md`](DEPLOYMENT-STRATEGIST.md) for FDE (Delta) vs. Deployment Strategist (Echo) differentiation.  
> **Operational Continuity:** [`docs/HANDOFF.md`](docs/HANDOFF.md) details current milestones, mounting instructions, and unyielding field rules.
>
> *Code Compatibility Notice:* The Python package preserves the canonical name `fdekit` to guarantee backward compatibility across 1,000+ unit tests, while tactical safety guardrails, passive probes, and reactive triggers live under [`fdekit.ithildin`](src/fdekit/ithildin/).

Ten integrated tools designed to take an enterprise deployment from raw WMS logs to a quantified A3 report with cryptographic production governance in a single command. Includes a calibrated synthetic distribution center with interconnected failure modes to demonstrate full-system capability offline.

The thesis: traditional engineers instrument software. This kit instruments the **physical operation and deterministic safety**—which determines whether a deployment survives past month three.

```bash
pip install -e .
fdekit demo --out out
```

Five seconds later, `out/` contains: normalized event logs, spaghetti travel diagrams, heatmaps, XmR control charts, master data audits, pick-line capacity sweeps, baseline specifications, TWI job instruction sheets, operational runbooks, and an A3 report pre-populated with quantified findings.

---

## Module Catalog

| # | Module | Core Function | Operational Phase |
|---|---|---|---|
| 1 | `fdekit.gemba` | Structured offline observation → quantified waste Pareto. Includes `transcribe`: aisle audio → structured draft observations | Days 0–14 |
| 2 | `fdekit.timestudy` | Cycle times, inter-operator variance, layout spaghetti, and heatmap from raw WMS event logs | Days 0–14 |
| 3 | `fdekit.processmining` | DFG generation, execution variants, conformance vs. declared flow, total wait-time bottlenecks | Days 15–30 |
| 4 | `fdekit.dataquality` | Sampling plans, physical master data audits, and statistical correlation to observed rework | Days 0–14 |
| 5 | `fdekit.sim` | Calibrated Discrete Event Simulation (DES) + Little's Law + Erlang C queueing | Days 15–30 |
| 6 | `fdekit.baseline` | Signable experiment specs, MDE, sample size calculation with ICC, Difference-in-Differences | Days 30–45 |
| 7 | `fdekit.probe` | EDI X12 validation (940/945/214/856), API contracts, timezone auditing, idempotency checks | Days 45+ |
| 8 | `fdekit.standardwork` | TWI Job Instruction sheets and operational handover runbooks | Days 45–75 |
| 9 | `fdekit.spc` | Statistical Process Control (XmR) with Nelson rules and frozen-limit degradation monitoring | Days 75+ |
| 10 | `fdekit.ithildin` | Passive 5-column telemetry, HMAC-SHA256 safe-staging guardrails, reactive triggers, and rollback validation | Continuous / Governance |

Plus `fdekit.a3` (which generates the executive A3 report with embedded findings) and `fdekit.value` (which transforms operational findings into a defensible economic case with Monte Carlo distributions and pricing ladders):

```bash
fdekit value --findings out/hallazgos.json --archetype todos --scale grande --sites 3 --control
```

Five enterprise archetypes, six value levers mapped to measurement tools, Monte Carlo simulation on attribution and realization, and a pricing ladder that **refuses** to quote gain-share without a measured counterfactual. That refusal is the most valuable feature of the module.

`labor_flex_share`—the most critical variable in the model—is calibrated across **four countries** through adversarial research:

| Country | Low / Mode / High | Underlying Mechanism |
|---|---|---|
| United States | 0.25 / **0.58** / 0.85 | At-will employment: exit cost ≈ 0 |
| Argentina | 0.15 / **0.55** / 0.90 | Severance dynamics + labor law 27.742 |
| Chile | 0.15 / **0.45** / 0.70 | Cost friction rather than legal prohibition |
| Australia | 0.18 / **0.42** / 0.78 | Casual loading at 25%; straightforward offboarding |

However, the primary driver is not geography: **it is the contractual structure.** An open-book 3PL contract in Chile provides higher working capital flexibility than self-operated facilities in the US. Consequently, `staffing_model` shifts from −0.30 (minimum volume commitments) to +0.25 (open-book pass-through), making contractual structure the first question asked during discovery.

---

## Minimal Data Contract

The entire toolkit runs on this minimal contract. It is deliberately lean so that any ERP, WMS, or TMS can export it without custom database modifications:

```
case_id, activity, timestamp, resource, location
```

`resource` and `location` are optional; omitting them merely disables spaghetti distance and operator variance analytics.

---

## Command Line Interface (CLI)

```bash
fdekit demo                                   # Full automated end-to-end diagnosis
fdekit synth --out data/                      # Generates synthetic distribution center logs
fdekit mine --log data/event_log.csv \
            --declared ORDER_RELEASED,PICK,CONSOLIDATE,PACK,QC,SHIP \
            --mermaid dfg.mmd
fdekit travel --log data/event_log.csv --plots figs/
fdekit dq --master data/master_wms.csv --plan-only --moe 0.04
fdekit dq --master data/master_wms.csv --measured data/truth_fisica.csv
fdekit sim --log data/event_log.csv --pickers 7 --packers 8
fdekit spc --values serie.csv --baseline 30 --plot xmr.png
fdekit probe --edi messages/
fdekit templates --out docs/                  # Blank operational templates
```

---

## Desktop Mockup — Measure Rather Than Infer

Tool 2 calculates layout distance using arithmetic over CAD blueprints. `fdekit field` **measures actual travel physically**, and the residual between the two represents the operational finding.

Complete procedure in under two minutes using tabletop items:

1. Print an ArUco marker (`DICT_4X4_50` dictionary) on standard paper and attach it to a mug (representing a picking cart).
2. Tape four desk corners and measure their dimensions. Generate `refs.csv`:

   ```csv
   x_px,y_px,x_m,y_m
   0,0,0,0
   100,0,10,0
   100,100,10,10
   0,100,0,10
   ```

3. Record a 30-second video moving the mug between locations.
4. Extract detections from the video:

   ```bash
   pip install 'fde-field-kit[vision]'
   python -c "from fdekit.field.vision import detect_markers, write_detections; d,n=detect_markers('desk.mp4'); write_detections(d,'det.csv',n); print(n,'frames')"
   ```

5. Run spatial analysis (pure Python, zero OpenCV dependency):

   ```bash
   fdekit field --detections det.csv --refs refs.csv --out out --fps 30 \
                --log data/event_log.csv --k 1 \
                --aisles 4 --bays 10 --aisle-pitch 3 --bay-pitch 1
   ```

   **Why `--k 1` is explicit:** Default anonymity is `k=3` to protect operator identity. Under three subjects, spatial clustering isolates individual humans. Passing `--k 1` explicitly confirms a tabletop test environment. Output includes `anonymity_k` verification.

In `out/espagueti_medido.png`, the physical route is mapped. All outputs pass through a privacy gate (`field.privacy.gate_output`), and session salts hash identifiers to protect operator confidentiality.

---

## What the Demo Discovers

On the calibrated synthetic distribution center:

* **The declared kickoff workflow represents only 54% of actual executions.** Thirty-one variants exist, with five shadow activities recurring daily: `CARTON_REWORK`, `PICK_EXCEPTION_LOCATION`, `REPACK`, `REPLENISH`, `SHORT_PICK`.
* **The bottleneck is a queue, not a slow task.** `ORDER_RELEASED -> PICK` accounts for 61% of total lead-time delay. The slowest individual activity does not rank in the top three for total lost time.
* **Master Data Triangulation:** Orders touching SKUs with incorrect packaging dimensions experience **2.3x higher rework rates** ($\chi^2 = 44.8, p = 2\times 10^{-11}$). Correcting master dimensional data eliminates ~14% of carton rework without touching warehouse software code.
* **Counterfactual Measurement:** Peak volume increased 15% post-implementation. A naive comparison suggests cycle time worsened by 56%. Difference-in-Differences with a control group demonstrates a **net 8.7% improvement** (95% CI [-8.5, -1.5] min, $p = 0.006$).
* **Capacity Dimensioning:** Increasing pickers from 6 to 7 cuts cycle time by 20%; increasing from 7 to 8 yields zero marginal benefit, defining the exact capex inflection point.

---

## The DECIDIDA Channel — `fdekit decide`

**Phase 0 — The Paper Pilot:** Two weeks with a printed ledger and zero in-room software. If a team cannot sustain verbal decision discipline on paper, software will not solve the issue.

```bash
fdekit decide pilot init --out pilot --control "weekly-ops"
fdekit decide pilot baseline --calendar calendar.csv
fdekit decide pilot score --tally pilot/sheet.csv
fdekit decide pilot verdict --calendar calendar.csv --cutoff 2026-07-27 \
      --treat "supply-committee" --control "weekly-ops"
```

The system tracks one agenda row per decision item written *prior* to the meeting. Empty cells represent non-decisions, ensuring declaration rates remain unfalsifiable.

### The System Invariants:
* Rejects vague criteria like *"make it better"*; requires quantitative or verifiable predicates.
* Rejects commitments without an associated `decision_id`.
* Enforces an upper ceiling of 7 decisions per meeting.
* Prevents closing decisions that retain unresolved commitments.
* Mandatory meeting consent verification prior to record creation.

---

## Key Design Principles

1. **Causally Chained Synthetic Data:** Master dimension errors trigger carton rework; expired location tags cause pick exceptions. Tools independently converge on verified root causes.
2. **Direct Rework Measurement:** Avoids confounding cycle-time comparisons across congested shifts.
3. **Frozen Control Limits:** Recalculating SPC control limits weekly normalizes degradation. Limits remain frozen post-calibration.
4. **Non-Euclidean Physical Routing:** Layout transitions enforce aisle exits rather than straight-line Euclidean shortcuts.
5. **Robust EDI Parsing:** X12 delimiters are parsed directly from ISA envelopes rather than assuming standard asterisks.
6. **Multi-Day Baseline Sampling:** Multi-day sampling across balanced shifts controls for day-of-week and peak-shift variance.

---

## Deployment Timeline

| Phase | Days | Modules | Primary Deliverable |
|---|---|---|---|
| **Gemba** | 0–14 | 1, 2, 4 | A3 report with quantified problem statements and shadow exceptions |
| **Diagnosis** | 15–30 | 3, 5 | Real vs. declared VSM, bottleneck identification, confidence-bounded promises |
| **Baseline** | 30–45 | 6 | Experiment specification signed by operational sponsors |
| **Pilot** | 45–75 | 7, 8 | Single zone/wave/shift trial. Weekly operator-level reviews |
| **Handover** | 75–90+ | 9, 10 | Frozen SPC monitors, TWI standard work documentation, A3 closed against baseline |

---

## Knowledge Graph & FDE Field Dojo (`knowledge-graph/`)

Operational findings must navigate contracting discussions, misaligned incentives, and executive committees. In [`knowledge-graph/`](knowledge-graph/README.md), the strategic and behavioral operating system is synthesized across **8 foundational management texts** into an auditable graph (**193 nodes · 488 edges · 12 canonical predicates**) and an offline simulator (**FDE Field Dojo**):

```bash
python knowledge-graph/build.py
```

Generates within `knowledge-graph/out/` (100% offline, zero external dependencies):
* **`knowledge-graph/out/index.html`** — Interactive graph visualizer with BFS path discovery.
* **`knowledge-graph/out/dojo.html`** — **FDE Field Dojo** featuring 5 training modes:
  1. **Tactical Reflex Dojo:** 42 branching scenarios (including 6 Palantir deployment cases) with Leitner spaced repetition.
  2. **90% CI Calibration Lab:** 20 calibrated estimation questions with Fermi scratchpads and equivalent betting wheels.
  3. **5-Day AIP Bootcamp Gauntlet:** 2 five-day campaigns with live metric tracking (`TQ`, `SIG`, `EVI`, `ADP`).
  4. **Artifact Forge & EVPI Lab:** 7 structured writing missions evaluated by a local deterministic linter.
  5. **Stakeholder Sparring:** Multi-turn roleplay simulations with optional voice synthesis.
* **`knowledge-graph/out/neo4j.cypher`** & **`knowledge-graph/out/obsidian/`** — Direct export for Neo4j and Obsidian vaults.

---

## Automated Verification

```bash
pytest -q
```

1,071 automated tests verify mathematical and operational invariants: DFG case isolation, Difference-in-Differences recovery under seasonal shifts, SPC false alarm rates below 2%, and data quality consistency.

## License

MIT.
