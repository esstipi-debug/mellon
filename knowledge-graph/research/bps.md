# Dossier: Bulletproof Problem Solving (Charles Conn & Robert McLean)
**Key:** `bps` | **Target Practice:** Forward Deployed Engineering & Deployment Strategy

---

## 1. Core Thesis in 5 Lines
1. Complex problem solving is a learnable, 7-step discipline anchored in hypothesis-driven logic rather than exhaustive data gathering.
2. Step 1 (Problem Definition) prevents solving the wrong problem through the SMART+ framework and the single-page Problem Definition Worksheet.
3. Logic trees (issue trees, hypothesis trees, decision trees) must be strictly MECE to disaggregate complexity into testable branches.
4. Teams must aggressively prioritize branches using the 2x2 Impact vs. Ability-to-Influence matrix before writing a workplan.
5. High-performing problem solvers build a "One-Day Answer" immediately and use back-of-the-envelope heuristics before deploying heavy computational models.

---

## 2. Chapter-by-Chapter Map

* **Ch 1: Learn the 7-Step Problem Solving Method:** The overarching framework: Define problem, Disaggregate into trees, Prioritize issues, Build workplan, Conduct analysis, Synthesize findings, Tell the story.
* **Ch 2: Define the Problem (Step 1):** The Problem Definition Worksheet. Establishes context, decision-makers, success metrics, boundaries, constraints, and time horizons. Introduces "porpoising" (zooming in and out).
* **Ch 3: Disaggregate the Problem (Step 2):** Constructing MECE issue trees, deductive math trees, and inductive hypothesis trees. Avoiding structural blind spots.
* **Ch 4: Prioritize Issues (Step 3):** The Impact vs. Feasibility/Influence 2x2. Pruning low-leverage branches to avoid "boiling the ocean".
* **Ch 5: Build a Workplan (Step 4):** Mapping hypothesis $\rightarrow$ analysis needed $\rightarrow$ lead person $\rightarrow$ timeline $\rightarrow$ deliverable format. Eliminates vague exploration.
* **Ch 6: Conduct Analyses & Heuristics (Step 5):** Order-of-magnitude estimations, Fermi problems, simple heuristics before machine learning, regressions, or large-scale simulations.
* **Ch 7: Synthesize Findings (Step 6):** Assembling the narrative. Transitioning from analysis back into a synthesized "So What?" answer using Pyramid structures.
* **Ch 8: Communicate & Tell the Story (Step 7):** Tailoring communication to executives: Lead with the governing recommendation, structure visually, provide proof points.
* **Ch 9: Dealing with Wicked Problems & Team Biases:** Team safeguards against confirmation bias: Red teams, perspective taking, obligation to dissent, pre-mortems.

---

## 3. Step-by-Step Toolkits for a Deployed Strategist

### A. The Problem Definition Worksheet (PDW)
Fill this out with the client project sponsor within the first 48 hours on-site:
1. **Core Problem Statement:** SMART+ (Specific, Measurable, Action-oriented, Relevant, Time-bound). Example: *"How can Plant 3 reduce unplanned downtime from 14% to under 6% by Q3 without adding headcount?"*
2. **Context & Trigger:** Why is this urgent right now? (e.g., Margin compression, board audit).
3. **Decision-Maker & Decision Rights:** Who has final authority to approve process changes?
4. **Success Criteria & Hard Metrics:** How is victory calculated? (e.g., \$4.2M annualized savings).
5. **Constraints & Guardrails:** What solutions are out of bounds? (e.g., No modifications to core SAP ERP; must comply with union shift regulations).

### B. Hypothesis Tree Construction
Use when investigating why an operational deployment is underperforming:
* **Governing Hypothesis:** *"Line 2 throughput is depressed primarily by raw material batch variance, not robot arm cycle times."*
  * **Branch 1:** Raw material tensile strength variance exceeds 15% across supplier lots.
  * **Branch 2:** Operators are manually overriding automated feed rates when variance spikes.
  * **Branch 3:** Robot arm cycle times remain consistent with manufacturer baseline specs.

### C. The One-Day Answer Protocol
Within 24 hours of landing at a deployment site:
1. Gather the deployment team around a whiteboard.
2. Write down your current best answer to the client's problem without waiting for external data.
3. List the 3 assumptions that *must* be true for this answer to stand.
4. Design the next 3 days of work strictly to attack and attempt to disprove those 3 assumptions.

---

## 4. Official Resources & References
* **Publisher Companion:** Wiley Problem Solving series ([wiley.com](https://wiley.com)).
* **McKinsey Insights Articles:** Charles Conn & Robert McLean: *"Six problem-solving mindsets for very uncertain times"* (McKinsey Quarterly).
* **Follow-up Book:** *The Imperfectionists: Strategic Mindsets for Uncertain Times* (Charles Conn & Robert McLean, Wiley 2023).

---

## 5. Field Playbook for Deployed Strategists

| Trigger in Deployment | FDE Action | Artifact / Script |
|---|---|---|
| **Client sponsor presents a vague, 30-page mandate.** | Facilitate a 60-min Problem Definition Worksheet session. | *"Before we look at the telemetry, let's agree on the exact 1-sentence decision you must make in 90 days."* |
| **Data team wants to clean 10 million historical rows.** | Run Prioritization 2x2; use Heuristics before Big Guns. | Prune 80% of data sources; run Fermi estimates on 1 week of clean data first. |
| **Team is divided on root cause of slow deployment.** | Build a Hypothesis Tree on the wall with sticky notes. | Identify the mutually exclusive tests required to confirm/deny each path. |
| **Deployment team suffering from confirmation bias.** | Run an Obligation to Dissent / Red Team session. | Appoint one engineer to argue why the initial hypothesis is completely invalid. |
