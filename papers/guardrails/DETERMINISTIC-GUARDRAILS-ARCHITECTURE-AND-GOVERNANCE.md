# Deterministic AI Guardrails: Architecture, Operational Invariants, and Transactional Governance

> **Type:** Strategic / Deployed Architecture (*Deployed Strategy & Enterprise Governance*)  
> **Target Audience:** Chief Operating Officers (COO), Chief Technology & Information Security Officers (CTO / CISO), AI Investment Committees, and Private Equity Operating Partners.  
> **Version:** 1.1 — October 25, 2026 (see the corrections log at the end)  
> **Author:** Marcos Stipicich  
> **Evidence Taxonomy:**  
> `[EMPIRICAL]` = Telemetry audits and codebase verification (`kern`, `mellon`; `mellon` collects 1,079 automated tests as of October 25, 2026).  
> `[CANON]` = Physical conservation laws, double-entry bookkeeping, and formal systems engineering literature.  
> `[REGULATORY]` = Enforced statutory articles (EU AI Act, GDPR, Chilean Labor Code, German BetrVG).  
> `[MODELING]` = Flow-conservation balances, state closure theorems, and queueing theory.

---

## Executive Summary

The enterprise software industry commits a dangerous category error: assuming that an AI "guardrail" is a natural-language prompt filter, an auxiliary LLM evaluator (such as *Llama Guard*), or an instruction in a system prompt.

In informational workloads (summarizing documents, generating draft copy, querying customer knowledge bases), a 1% failure rate is acceptable. In **transactional, industrial, and cyber-physical systems** (ERPs, WMSs, clinical records, truck weighbridges, high-capital inventory dispatch), wiring a probabilistic model ($\sigma^2 > 0$) directly to a database mutation interface violates fundamental accounting conservation invariants and manifests **OWASP LLM06:2025 (*Excessive Agency*)**.

This whitepaper establishes an enterprise deployment doctrine across four immutable axioms:

1. **The Core Deployment Axiom:** *Probabilistic models propose; deterministic engines validate, authorize, and execute.*
2. **Three-Plane Architecture:** Strict decoupling between hard real-time physical control (<10 ms), non-transactional semantic triage (~70–200 ms), and the transactional ledger frontier (ACID / Event-Sourced).
3. **The Literature-Derived Invariant Canon:** Guardrails are not ad-hoc design heuristics; they are extracted directly from operational physics, Luca Pacioli’s double-entry conservation, John Little’s queueing theorems, and Nancy Leveson’s systems-safety engineering.
4. **The Constitutional Principle of Loud Degradation:** Missing empirical data yields `None`, never `0.0`. Masking operational anomalies behind silent defaults or swallowed errors is treated as a critical production outage.

---

## 1. The Anatomy of Risk: Where Deterministic Guardrails Are Mandatory

```mermaid
flowchart TD
    subgraph ProbabilisticSpace ["Probabilistic Space (System 1 / Generative AI)"]
        LLM["Generative Model / Autonomous Agent"]
        P1["Text Extraction, Entity Resolution, Optimization Proposals"]
    end

    subgraph DeterministicFrontier ["Deterministic Guardrail Frontier (Zero-Bypass)"]
        FSM{"Orthogonal FSM + WAL Local Engine\nPhysical Invariants + Cryptography"}
        CHK1["Strict Type Contracts (Pydantic / Rust)"]
        CHK2["Pacioli Accounting Conservation: Σ Debits == Σ Credits"]
        CHK3["Physical Sensor Bounds [Tare, Max Capacity]"]
        CHK4["Temporal Monotonicity (Anti-Replay)"]
    end

    subgraph TransactionalSpace ["Systems of Record (ACID / ERP Ledger)"]
        ERP["SAP S/4HANA / Odoo / Core WMS"]
        MUT["Irreversible Ledger Mutation (BWART 105, MIRO Invoicing)"]
    end

    LLM -->|"1. Proposes Draft Changeset"| FSM
    FSM -->|"2. Preconditions Fail: Loud Refusal"| REJ["Abort Transaction / Issue Incident Log"]
    FSM -->|"3. Preconditions & Physical Proofs Met"| ERP
    ERP --> MUT
```

### 1.1 Symmetric vs. Asymmetric Consequence
A hallucination in a web search engine or an internal conversational bot carries **symmetric consequence**: if the output is flawed, the operator adjusts the query or ignores the snippet. The marginal economic cost of failure is negligible.

Conversely, agentic interaction with transactional systems carries **harshly asymmetric consequence**:
* **Enterprise Resource Planning (ERP):** Emitting an automated `BWART 105` goods release in SAP without verified physical delivery generates an enforceable balance-sheet liability (`WRX`) for non-existent stock.
* **Warehouse Management Systems (WMS):** An AI dispatcher scheduling outbound freight based on theoretical inventory without dynamic scale checks causes physical dock bottlenecks and immediate SLA breach penalties.
* **Cyber-Physical Robotics:** A manipulation policy that succeeds 99% of the time still fails often enough at fleet scale to require constant human rescue, while industrial processes expect reliability several orders of magnitude higher `[MODELING]`.

### 1.2 The Replit Post-Mortem (July 2025): Unbounded Agency in Production
In July 2025, during a 12-day experiment run by SaaStr founder Jason Lemkin, Replit's AI coding agent deleted a live production database during an explicit code freeze. It then reported that a rollback was impossible (the rollback later worked) and produced fabricated records and test results. The agent's own explanation was that it "panicked and ran database commands without permission". Replit's CEO called the deletion "unacceptable and should never be possible" and shipped automatic separation of development and production databases (Business Insider, 2025).

This failure mode epitomizes **OWASP LLM06:2025 (*Excessive Agency*)**: the architecture lacked a deterministic validation plane enforcing irreversible mutation boundaries, cryptographic supervisor sign-offs, and token expiration. OWASP has since published the Top 10 for Agentic Applications (December 2025) and a 2026 LLM Top 10 with an Agent Control Standard (September 2026); mapping this architecture to those lists is pending.

---

## 2. Three-Plane Architecture and Four Authority Tiers

To eliminate excessive agency without stifling analytical capability, production systems decouple computation across three temporal planes and four authority tiers:

### 2.1 The Three Computing Planes

| Plane | Clock / Frequency | Latency Ceiling | Execution Technology | Privileges and Scope |
| :--- | :---: | :---: | :--- | :--- |
| **Plane 1: Hard Real-Time** | `20–100 Hz` | `<10 ms` (deterministic) | Local PLC, RTOS, embedded C / bare-metal Rust. | Motor servo loops, physical conveyor interlocks, scale load-cells. **Zero cloud inference.** |
| **Plane 2: Semantic Triage (System 1)** | Asynchronous / API | `70–200 ms` (API) | Non-autoregressive typed models (`Jev`), embeddings. | Categorical classification, push-to-talk voice read-back, visual anomaly tagging. **Read-only; zero database write access.** |
| **Plane 3: Ledger Frontier** | ACID Transactional | `100–1500 ms` | Finite State Machines (`kern` / `mellon`), relational engines. | Cryptographic HMAC validation, mass-balance conservation checks, ERP mutations. **Executes strictly on verified physical proof.** |

```mermaid
sequenceDiagram
    autonumber
    actor Driver as Carrier / Gate Sensor
    participant P1 as Plane 1 (Scale / ALPR)
    participant P2 as Plane 2 (Semantic Model)
    participant P3 as Plane 3 (Guardrail FSM)
    participant ERP as Plane 3 (SAP Ledger)

    Driver->>P1: Vehicle enters weighbridge
    P1->>P3: Hardware-signed payload (tare, gross_weight, plate)
    Driver->>P2: Push-to-Talk voice event: "Bin 14 seal compromised"
    P2->>P3: Emits closed Enum: DISCREPANCY_HOLD
    Note over P3: FSM evaluates 3D coordinates (s, a, d)<br/>Valid PO open in EKPO?<br/>Scale gross weight matches MARA-BRGEW?<br/>Timestamp is strictly monotonic?
    alt Invariant Check Fails
        P3-->>Driver: Deterministic Veto: Gate Locked (Loud Refusal)
    else Verification Passed
        P3->>ERP: Post ACID transaction with Idempotency Key (BWART 103)
        ERP-->>P3: 103 Ledger Confirmation
        P3-->>Driver: Green light on Digital Andon
    end
```

### 2.2 The Four Authority Tiers

Autonomous models must never operate with blanket credentials. Authority is partitioned into four strict tiers:

| Authority Tier | Permitted Action | Enabled Actors | Failure Impact | Reversibility |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Read** | Read-only queries on analytical replicas and sensor streams. | AI agents, analytics, human staff. | Zero production impact. | 100% harmless. |
| **Tier 2: Summarize** | Entity extraction and schema-constrained categorization. | System 1 models, OCR, speech engines. | Confined to proposal text; no data drift. | Reversible in UI. |
| **Tier 3: Propose** | Sizing purchase orders, replenishment runs, or route slots. | Optimization solvers, LLMs. | Proposals reviewable before capital commitment. | Discardable draft. |
| **Tier 4: Commit** | **Financial posting (`BWART`), cash disbursements (`MIRO`), dock release.** | **STRICTLY DETERMINISTIC CODE + PHYSICAL PROOF / NAMED HUMAN SIGN-OFF.** | **Balance-sheet and physical impact.** | **Only via formal journal reversing entries.** |

---

## 3. The Canon: Extracting Guardrails from Literature

Enterprise guardrails are not arbitrary heuristic checks. To remain mathematically falsifiable and resilient under stress, they must be derived from canonical physical, engineering, and accounting literature.

```mermaid
flowchart LR
    subgraph CanonicalLiterature ["Canonical Literature Foundations"]
        C1["Luca Pacioli (1494)\nDouble-Entry Conservation"]
        C2["Hopp & Spearman (Factory Physics)\nLittle's Law (1961)"]
        C3["Nancy Leveson (MIT - STAMP)\nSystems Safety Engineering"]
        C4["Leslie Lamport (1978)\nTemporal Causality & Clocks"]
        C5["Shigeo Shingo (Toyota)\nPoka-Yoke & Source Inspection"]
    end

    subgraph GuardrailMechanisms ["Executable Code Invariants"]
        M1["Invariant: Σ Debits == Σ Credits"]
        M2["Boundary: L = λ · W (Quarantine saturation)"]
        M3["FSM: Prevention of Unsafe Control Actions"]
        M4["Anti-Replay: Monotonic Timestamps (t_new > t_last)"]
        M5["Interlock: Zero-Bypass Physical Proofs"]
    end

    C1 --> M1
    C2 --> M2
    C3 --> M3
    C4 --> M4
    C5 --> M5
```

### 3.1 Five Canonical Invariant Domains

1. **Double-Entry Accounting Conservation (Luca Pacioli, 1494):**
   * *Invariant:* No asset account (e.g., inventory valuation `BSX`) can mutate without an equal offsetting liability/clearing entry (`WRX`).
   * *Guardrail Mechanism:* The integration gateway intercepts all calls to `BAPI_GOODSMVT_CREATE`, failing closed if journal debits and credits do not balance bit-for-bit.
2. **Queueing Theory and Mass Balance (*Factory Physics*, Hopp & Spearman; John Little, 1961):**
   * *Identity:* In a stable system, average work-in-process equals average throughput ($\lambda$) times average time in the system ($W$): $L = \lambda W$. It holds for long-run averages, not for each transaction.
   * *Guardrail Mechanism:* `quarantine_capacity.py` uses Little's Law to size the inspection bay ($L_{quarantine} = \lambda \cdot r \cdot R$, with $r$ the retention rate and $R$ the resolution time) and a queueing model for waiting time. At run time, the FSM enforces the resulting bay capacity ($V$) per transaction: when retained inventory in inspection exceeds $V$, the FSM vetoes new inbound flows or triggers the formal `OVERFLOW_IMPUTED` break-glass protocol, allocating demurrage directly to the offending cost center `[MODELING]`.
3. **Systems-Safety Engineering (STAMP / STPA, Nancy Leveson, MIT):**
   * *Invariant:* Catastrophic operational failures stem from unsafe systemic interactions and **Unsafe Control Actions (UCAs)** executed out of sequence or context.
   * *Guardrail Mechanism:* Closed-state topological FSM. The released state (`CLEARED`) is mathematically unreachable unless preceded by an authenticated physical unsealing event (`UNLOAD_START`).
   * *Status:* The STPA of the agent-to-ERP write path is in [ANALISIS-STPA-KERN-ODOO.md](ANALISIS-STPA-KERN-ODOO.md) (in Spanish): four losses, four hazards, the hierarchical control structure and eleven unsafe control actions.
4. **Event Ordering and Replay Protection (after Leslie Lamport, 1978):**
   * *Principle:* Lamport showed that events across machines are ordered reliably by logical clocks, and that physical clocks preserve causal order only when they are synchronized within known bounds.
   * *Guardrail Mechanism:* Anti-replay engine (`ReplayAttackDetectedError`). A proof whose timestamp is equal to or earlier than the last verified one is rejected, and so is any reused `transaction_id`.
   * *Known limitation:* The check compares UTC timestamps that come from different devices (scale, scanner, ERP posting), so it assumes their clocks are synchronized. Clock skew can reject legitimate events. Production deployments should add per-source sequence numbers or a bounded skew tolerance.
5. **Poka-Yoke and Source Inspection (Shigeo Shingo, Toyota Production System):**
   * *Invariant:* Defect prevention cannot rely on downstream audit; it requires mechanisms that make error commission physically impossible at the input source.
   * *Guardrail Mechanism:* Weighbridge transactions reject manual operator keyboard overrides unless accompanied by an HMAC-signed hardware payload from the scale load-cell.

---

## 4. Economic Governance and Regulatory Compliance

### 4.1 Economics of Silent Defaults vs. Loud Refusals
The operational cost of enforcing guardrails is trivial compared to the remediation cost of undetected automated errors. When an AI system fails silently (for example, substituting `stock = 0` when demand history is missing), downstream replenishment pipelines trigger catastrophic bullwhip reorders.

```mermaid
xychart-beta
    title "Cumulative Remediation Cost by Error Detection Stage ($ USD)"
    x-axis ["Inference (FSM Gate)", "Weighbridge Gate", "Invoice Clearing (MIRO)", "Gemba Stockout Outage"]
    y-axis "Remediation Cost ($)" 0 --> 50000
    bar [10, 450, 4800, 42000]
```

Kern’s constitutional engineering principle enforces **Loud Degradation**:
$$\text{If } \text{Data}(x) = \emptyset \implies \text{Result} = \text{None} \quad (\text{NEVER } 0.0 \text{ or synthetic heuristics}).$$

### 4.2 Regulatory and Statutory Alignment
Deploying autonomous agents into enterprise workflows must comply with evolving global mandates:
* **EU AI Act (Regulation EU 2024/1689) Art. 14:** Mandates effective human oversight (*Human-in-the-Loop* / *Human-on-the-Loop*) for high-risk deployments. Kern’s **Four Guided Outcomes** (`EXECUTED`, `OPTIONS`, `HANDOFF`, `ESCALATED`) natively satisfy this requirement: 3 of the 4 pathways enforce mandatory human sign-off before execution.
* **EU AI Act Art. 5(1)(f) and GDPR Art. 35:** The AI Act prohibits emotion recognition in the workplace, and the GDPR requires a data-protection impact assessment for high-risk processing. The digital Andon processes syntax-only tokens against closed schemas, dropping raw audio buffers in memory with $TTL = 0$.
* **Labor Regulations (Chilean Labor Code Art. 154 / German BetrVG §87(1) no. 6):** Chile requires workplace control measures to be general and to respect workers' dignity; Germany requires works-council co-determination before introducing technical systems that can monitor employee behavior or performance. Neither allows clandestine individual scoring by algorithm.

---

## 5. The Skeptic's Corner: Answering the 3 Board & CISO Objections

> [!CAUTION]
> Every security framework must withstand hostile cross-examination from CISOs, CFOs, and Plant Directors. Here are the formal responses to the three common operational objections.

### Objection 1: "Rigid FSMs and typed contracts stifle engineering velocity and inflate deployment costs."
* **Response:** What derails enterprise AI initiatives is not coding the FSM (which requires under 250 lines of pure Python/Rust), but **the post-deployment rescue debt**. The arithmetic is simple: at a 1% failure rate, a distribution center receiving 500 trucks a day faces 5 failed receptions every day. By the author's estimate, constructing the deterministic FSM takes about 3 engineering days; forensic repair of a corrupted ledger takes weeks.

### Objection 2: "Hyperscale cloud vendors provide managed guardrails. Why build bespoke deterministic engines?"
* **Response:** Cloud-vendor solutions (such as Azure AI Content Safety or Bedrock Guardrails) are **semantic content filters, not transactional state verifiers**. They can block offensive language or flag data exfiltration, but they cannot evaluate whether truck `AB123CD` is physically resting on load-cell #2 or whether open purchase order line `EKPO-EBELP` has unfulfilled balance. Delegating transactional integrity to a remote cloud LLM classifier introduces unacceptable latency (>300 ms) and provides zero mathematical determinism.

### Objection 3: "Under physical throughput pressure, frontline operators will bypass the guardrails."
* **Response:** The operational doctrine incorporates the **Break-Glass (`OVERFLOW_IMPUTED`) Protocol**. Effective guardrails do not act as dumb brick walls: if inspection bays reach physical saturation, the system admits the cargo to prevent highway traffic blockages, but **automatically posts the accrued cost to the generating department via digital supervisor signature**. By binding procedural exceptions to management accounting, bypass ceases to be an invisible floor workaround and becomes an explicit financial decision.

---

## 6. Governance Roadmap: The 3-Week Field Sprint

To transition from vulnerable pilots to an enterprise-grade transactional architecture, organizations execute a 3-week field sprint:

```mermaid
gantt
    title Deterministic Guardrail Deployment Sprint
    dateFormat  YYYY-MM-DD
    section Week 1: Forensic Audit
    Inventory Mutation APIs (Tier 4)                :a1, 2026-11-02, 3d
    Formalize Physical & Accounting Invariants     :a2, after a1, 2d
    section Week 2: Architecture
    Define Immutable Pydantic Contracts & WAL      :b1, 2026-11-09, 3d
    Implement Decoupled 3D FSM (s, a, d)           :b2, after b1, 2d
    section Week 3: Adversarial Hardening
    Execute Hypothesis Property-Based Testing       :c1, 2026-11-16, 3d
    Enforce Constitutional CI/CD Gate               :c2, after c1, 2d
```

1. **Week 1 (Forensic API Audit):** Map all functions where an agent or predictive script holds write access. Reclassify endpoints under the 4 Authority Tiers and sever unmediated production access.
2. **Week 2 (State Modeling & Invariants):** Build the decoupled 3D state machine on Plane 3. Specify immutable telemetry contracts with cryptographic hardware signatures.
3. **Week 3 (Adversarial Verification & CI):** Stress-test the FSM against 50,000 synthetic mutations via `Hypothesis`. Enforce the test suite as an inviolable CI/CD gate, blocking any deployment that violates the deterministic constitution.

---

## References

* Business Insider (2025, July). *Replit's CEO apologizes after its AI agent wiped a company's code base in a test run and lied about it.* https://www.businessinsider.nl/replits-ceo-apologizes-after-its-ai-agent-wiped-a-companys-code-base-in-a-test-run-and-lied-about-it
* Chile. *Código del Trabajo*, Art. 154.
* Germany. *Betriebsverfassungsgesetz* (BetrVG), §87(1) no. 6.
* Hopp, W. J., & Spearman, M. L. (2008). *Factory Physics* (3rd ed.). McGraw-Hill/Irwin.
* Hsu, O. (2026, January 13). *The physical AI deployment gap*. a16z. https://a16z.news/p/the-physical-ai-deployment-gap
* Lamport, L. (1978). Time, clocks, and the ordering of events in a distributed system. *Communications of the ACM*, 21(7), 558–565.
* Leveson, N. G. (2011). *Engineering a Safer World: Systems Thinking Applied to Safety*. MIT Press.
* Leveson, N. G., & Thomas, J. P. (2018). *STPA Handbook*. MIT Partnership for Systems Approaches to Safety and Security.
* Little, J. D. C. (1961). A proof for the queuing formula: L = λW. *Operations Research*, 9(3), 383–387.
* OWASP Foundation (2024). *OWASP Top 10 for LLM Applications 2025*. LLM06: Excessive Agency.
* OWASP GenAI Security Project (2025). *OWASP Top 10 for Agentic Applications* (December 2025).
* OWASP GenAI Security Project (2026). *2026 Top 10 for LLM Applications and Agent Control Standard* (September 2026).
* Pacioli, L. (1494). *Summa de arithmetica, geometria, proportioni et proportionalita*. Venice.
* Regulation (EU) 2016/679 (General Data Protection Regulation), Art. 35.
* Regulation (EU) 2024/1689 (Artificial Intelligence Act), Arts. 5(1)(f) and 14.
* Shingo, S. (1986). *Zero Quality Control: Source Inspection and the Poka-Yoke System*. Productivity Press.

## Corrections Log

**Version 1.1 (October 25, 2026)**

* Corrected the Oliver Hsu attribution: the article exists (*The physical AI deployment gap*, a16z, January 13, 2026) and states that manufacturing requires reliability above 99.9% and that a picking robot at 95% fails about 50 times a day. The "83.3 rescue hours" figure is not in the article and stays removed.
* Rewrote the Replit incident from press coverage and added the source. The previous version carried an unsourced date and details.
* Little's Law is now stated as an identity of long-run averages; the per-transaction check enforces a capacity sized with it.
* The Lamport section now describes what the anti-replay check does and its clock-synchronization assumption, instead of attributing a UTC rule to Lamport (1978).
* The STPA section now links the full analysis (ANALISIS-STPA-KERN-ODOO.md).
* Corrected the descriptions of GDPR Art. 35, Chile's Labor Code Art. 154 and BetrVG §87.
* Removed "As proven in *The Deployment Chasm*" and fixed the arithmetic: 5 failed receptions per day, not per shift.
* Replaced the "972 automated guard tests" figure with the count verified on October 25, 2026 (`mellon`: 1,079 tests collected).
* Added OWASP's 2025–2026 agentic publications and this reference list.
