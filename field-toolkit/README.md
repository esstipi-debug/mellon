# FIELD TOOLKIT: THE DEPLOYMENT STRATEGIST'S FRONTLINE OPERATING SYSTEM
## Field-Executable Artifacts for Gemba Interventions & C-Level Governance

> **Canonical Repository:** `field-toolkit/`  
> **Purpose:** Provide operational artifacts, contract templates, and field protocols to execute the principles of [*The 21st-Century Polymath Manifesto*](../THE-21ST-CENTURY-POLYMATH-MANIFESTO.md) and the doctrine of the [*Deployment Strategist Master Whitepaper*](../DEPLOYMENT-STRATEGIST-WHITEPAPER-MASTER.md) during the first 30 days of enterprise deployment.

---

### Start Here: The First 30 Days

**[The First 30 Days: A field protocol for deploying AI inside a physical operation](FIELD-PROTOCOL-30-DAYS.md)** · [PDF, 9 pages](The-First-30-Days-Marcos-Stipicich.pdf)

The protocol is the operating document of this toolkit. Nothing writes to production during the 30 days, and day 30 ends in a signed go, go with conditions, or stop.

| Days | Phase | Output |
| :--- | :--- | :--- |
| 0 | Before kickoff | A signed charter: sponsor, decision, stop criterion, access terms |
| 1–5 | Access | A read-only copy of the data and a first register of anomalies |
| 6–12 | The floor | The process as it is run, the shadow systems, a record-accuracy baseline |
| 13–20 | Incentives and forecast | Incentive conflicts, forecast value added, working capital exposure |
| 21–27 | The boundary | What the model may do, what code checks, what people sign |
| 28–30 | Decision | A one-page memo and a measurement plan |

---

### Earlier Artifacts

The three artifacts below are earlier drafts of parts of the protocol, kept for reference. Where they differ from the protocol, the protocol governs.

| Artifact | File | Primary Audience & Function | Deployment Window |
| :--- | :--- | :--- | :---: |
| **1. 5-Day Access Agreement (CEO Interlock)** | [`01_ceo_5_day_access_interlock.md`](01_ceo_5_day_access_interlock.md) | Board of Directors, CEO, CISO, and IT.<br>Establishes a peremptory 120-clock-hour SLA for read-only replica data extracts, eliminating pilot purgatory and IT vetoes. | **Day 0 (Inception)** |
| **2. Ethnographic Floor Protocol & The Mom Test** | [`02_gemba_mom_test_ethnographic_guide.md`](02_gemba_mom_test_ethnographic_guide.md) | Floor operators, dock workers, and forklift teams.<br>Forensic graveyard-shift shadowing, cataloging of Shadow IT (WhatsApp/Excel), and verification of the <800 ms interface latency threshold. | **Weeks 1 & 2** |
| **3. Negative FVA Matrix & MOQ Arbitrage Engine** | [`03_negative_fva_incentive_arbitrage_matrix.md`](03_negative_fva_incentive_arbitrage_matrix.md) | Demand Planners, Procurement Buyers, and CFO.<br>Quantitative $\Delta\text{TCO}$ calculator factoring a 24.50% carrying cost against volume discounts, with deterministic Three-Lane gating (Green, Yellow, Red). | **Weeks 3 & 4** |

---
*Direct programmatic integration with the root mathematical suite: [`inventory_mechanics.py`](../inventory_mechanics.py) · [`econometric_engine.py`](../econometric_engine.py) · [`core_event_contracts.py`](../core_event_contracts.py) · [`inbound_fsm_guardrail.py`](../inbound_fsm_guardrail.py).*
