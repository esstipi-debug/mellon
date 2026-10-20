# Mellon & Ithildin Development Guidelines 🗝️🌌

> **Architecture Doctrine, Acceptance Criteria, and Operational Protocols for Field Deployment and AI Agents.**  
> *Version 1.0 · October 2026 · Mellon Playbook*

---

## 1. The Dual Philosophy: Mellon + Ithildin

Building software and artificial intelligence in this ecosystem is not governed by the rules of *desktop SaaS* or academic demo notebooks. It operates under the unforgiving constraints of the **Gemba** (the physical floor where operations happen: warehouses, distribution centers, cross-docks, and manufacturing plants).

For any product or agent to survive and deliver measurable value, it must balance two complementary forces:

$$\textbf{Sustainable Adoption} = \underbrace{\text{Mellon (Human Alliance)}}_{\text{Eliminates 95\% of pilot rejection}} \times \underbrace{\text{Ithildin (Deterministic Rigor)}}_{\text{Zeroes out IT transactional risk}}$$

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 MELLON 🗝️                                    │
│                    Human Alliance & Field Adoption Protocol                 │
│   • Speak the Gemba dialect (floor terms, zero LLM jargon)                  │
│   • Human-in-the-Loop: the agent assists, the operator validates             │
│   • Frictionless native channels (WhatsApp, RF scanners, CLI)               │
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

---

## 2. Mellon Directives (Agent Design for Operations)

### Directive M1: The Agent is an Ally, Never an Undercover Inspector
* **Rule:** No agent is designed to police, punitively score, or displace human operators. It is engineered to absorb cognitive fatigue, eliminate rework, and remove administrative drudgery.
* **Mechanism:** When an agent detects an operational anomaly on the floor, it does not send an accusatory alert to senior leadership; it provides the operator with an actionable, in-context correction directly in their active workflow.

### Directive M2: Speak the Gemba Dialect
* **Rule:** Exposing internal LLM jargon (*embeddings, tokens, prompts, temperature, hallucination*) to operational end-users is strictly prohibited.
* **Mechanism:** The agent translates internal states into operational reality:
  * ❌ *"The model has 85% confidence in this prompt completion."*
  * ✔️ *"Detected 3 pallets at Dock 4 without an assigned receiving tag in SAP."*

### Directive M3: Native Interfaces and Zero Friction
* **Rule:** Do not force warehouse personnel or supervisors to open another browser tab or log into yet another disconnected dashboard.
* **Mechanism:** The agent operates where the workforce already lives:
  * Asynchronous enterprise messaging (WhatsApp, Telegram, Slack).
  * Plaintext outputs compatible with ruggedized RF barcode scanners or VT220 terminals.
  * Webhook integrations and single-line CLI commands (`fdekit`).

---

## 3. Ithildin Directives (Technical Architecture & Guardrails)

### Directive I1: Dual-Track Architecture (Safe-Staging Writeback)
* **Rule:** Generative AI is probabilistic; the transactional database (ERP/WMS) is deterministic. **No LLM or agent has direct write credentials to production tables.**
* **Mechanism:**
  1. The agent processes inputs and generates a structured action proposal (`StagingAction`).
  2. Actions are classified by risk tier:
     * `READ`: Read-only queries, zero state mutation.
     * `REVERSIBLE`: Draft creation, temporary soft reservations, or secondary logs.
     * `IRREVERSIBLE`: Order cancellations, GL accounting adjustments, physical inventory mutations.
  3. Every `IRREVERSIBLE` action must include an executable `rollback_plan`. Without it, the guardrail rejects execution immediately.

### Directive I2: Cryptographic Signatures and Idempotency
* **Rule:** No mutation executes without a valid HMAC-SHA256 token and a unique idempotency key.
* **Mechanism:**
  * Implemented via `fdekit.ithildin.IthildinGuard`.
  * If network instability causes an agent or webhook to retry a submission, the append-only ledger catches the duplicate idempotency key and prevents double-posting in the ERP.

### Directive I3: Zero-Overhead Passive Probing (5 Canonical Columns)
* **Rule:** Diagnostic data collection must never degrade production database throughput with unindexed, expensive queries across millions of rows.
* **Mechanism:**
  * Powered by `fdekit.ithildin.PassiveEventProbe`.
  * Ingestion conforms to the minimal 5-column contract:
    $$\{\texttt{case\_id, activity, timestamp, resource, location}\}$$
  * Passive audits detect timezone-naive timestamps, chronological inversions, and null densities before feeding downstream inference.

### Directive I4: Reactive Triggers over Continuous Polling
* **Rule:** Agents must idle at zero computational overhead until a qualified stimulus crosses an operational threshold.
* **Mechanism:**
  * Powered by `fdekit.ithildin.ConditionalTrigger`.
  * Triggers enforce pure boolean predicates with mandatory cooldown intervals to prevent event storms and runaway execution loops.

---

## 4. Production Certification Rubric

Before any new agent or module is deployed into production or delivered to a client, it must clear these five sequential gates:

| Gate | Critical Inquiry | Blocking Condition |
|---|---|---|
| **1. Cryptographic Guardrail** | Does the agent submit through HMAC-signed staging with an idempotency key? | **YES/NO.** If writing directly to production tables without HMAC, rejected. |
| **2. Rollback Contingency** | Does every irreversible mutation have a verified deterministic reversal plan? | If `risk_level == IRREVERSIBLE` without `rollback_plan`, hard failure. |
| **3. Gemba Dialect** | Does the interface exclusively use physical business and operational terms? | If leaking model telemetry or abstract parameters, rejected. |
| **4. Minimal Data Contract** | Does telemetry adhere to the 5-column schema with timezone-aware timestamps? | If introducing bloated schemas or timezone-naive inputs, rejected. |
| **5. Counterfactual ROI** | Is impact measured via Difference-in-Differences (Diff-in-Diff) against a control? | A valid control group or pre/post counterfactual baseline is mandatory. |

---

## 5. Reference Implementation

All new Python agent workflows should build upon [`fdekit.ithildin`](src/fdekit/ithildin/):

```python
from fdekit.ithildin import (
    ConditionalTrigger,
    IthildinGuard,
    PassiveEventProbe,
    RiskLevel,
    StagingAction,
)

# 1. Initialize deterministic guardrail with secure secret
guard = IthildinGuard(secret_key=b"high-entropy-secret-key-16bytes-min")

# 2. Agent generates proposed staging action
action = StagingAction(
    action_id="act-picking-reassign-001",
    risk_level=RiskLevel.REVERSIBLE,
    target_system="WMS_MANHATTAN",
    payload={"task_id": "T-892", "new_picker": "OP-14"},
    idempotency_key="idemp-wms-20261020-001",
    timestamp_utc="2026-10-20T12:35:00+00:00",
    rollback_plan={"task_id": "T-892", "restore_picker": "OP-03"},
)

# 3. Sign and submit for deterministic evaluation
token = guard.sign_action(action)
verdict = guard.evaluate_and_commit(action, token)

if verdict.approved:
    # Safe to execute writeback to target system
    print(f"Writeback approved with audit hash: {verdict.audit_hash}")
else:
    print(f"Action blocked by Ithildin: {verdict.reason} ({verdict.code})")
```
