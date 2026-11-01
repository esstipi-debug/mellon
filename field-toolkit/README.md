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

### Other Artifacts

Artifacts 1–3 below are earlier drafts of parts of the protocol, kept for reference. Artifact 4 is a specification and artifacts 5–7 are Python scripts. Where any of them differs from the protocol, the protocol governs.

| Artifact | File | Primary Audience & Function | Deployment Window |
| :--- | :--- | :--- | :---: |
| **1. 5-Day Access Agreement (CEO Interlock)** | [`01_ceo_5_day_access_interlock.md`](01_ceo_5_day_access_interlock.md) | Board of Directors, CEO, CISO, and IT.<br>Establishes a peremptory 120-clock-hour SLA for read-only replica data extracts, eliminating pilot purgatory and IT vetoes. | **Day 0 (Inception)** |
| **2. Ethnographic Floor Protocol & The Mom Test** | [`02_gemba_mom_test_ethnographic_guide.md`](02_gemba_mom_test_ethnographic_guide.md) | Floor operators, dock workers, and forklift teams.<br>Forensic graveyard-shift shadowing, cataloging of Shadow IT (WhatsApp/Excel), and verification of the <800 ms interface latency threshold. | **Weeks 1 & 2** |
| **3. Negative FVA Matrix & MOQ Arbitrage Engine** | [`03_negative_fva_incentive_arbitrage_matrix.md`](03_negative_fva_incentive_arbitrage_matrix.md) | Demand Planners, Procurement Buyers, and CFO.<br>Quantitative $\Delta\text{TCO}$ calculator factoring a 24.50% carrying cost against volume discounts, with deterministic Three-Lane gating (Green, Yellow, Red). | **Weeks 3 & 4** |
| **4. NARYA 💍🔥: Frontline Andon & Stewardship Engine** | [`04_frontline_andon_and_stewardship_engine.md`](04_frontline_andon_and_stewardship_engine.md) | Shift operators, pickers, forklift crew, and shift supervisors.<br>Specification only; not implemented. Defect reporting by voice, photo or text, quarantine-location assignment, reporting time credited so it does not count against pick-rate targets, and pre-triaged decision cards for shift supervisors. | **Weeks 2 & 4** |
| **5. Gemba Reconnaissance & Diagnostic Playbook Engine** | [`05_supply_chain_gemba_recon_pipeline.py`](05_supply_chain_gemba_recon_pipeline.py) | Field Deployment Strategists & Forensic Auditors.<br>Prototype. Matches Spanish-language field notes to 10 pre-written failure modes by shared words (TF-IDF; no semantic search and no graph) and, for each match, prints a red-flag threshold, a service offer and a cost estimate computed from fixed assumptions in the code. The references cited for the thresholds (OSHA, EN 15635, WERC) are unverified. Design notes, including a graph and embedding search the script does not implement: [`supply_chain_diagnostic_ontology.md`](supply_chain_diagnostic_ontology.md). | **Day 1 (Reconnaissance)** |
| **6. Frontline Voice Bot & WhatsApp/Telegram Webhook** | [`06_frontline_voice_gemba_bot.py`](06_frontline_voice_gemba_bot.py) | Deployment Strategists & Floor Auditors.<br>Prototype with no tests in this repository. Wraps script 5 in a Telegram bot that accepts text and voice notes (transcribed in Spanish with Faster-Whisper) and in an HTTP API (text and audio upload) whose WhatsApp webhook handles Twilio text messages only. Replies with script 5's report, with the same limits; WhatsApp replies are cut at 1,500 characters. No access control: the bot answers anyone who messages it, the API has no authentication and listens on all network interfaces, and the webhook does not check that requests come from Twilio. | **Day 1 (Reconnaissance)** |
| **7. Forensic Process Mining & Invariants Simulator** | [`07_forensic_process_conformance_simulator.py`](07_forensic_process_conformance_simulator.py) | Principal FDEs & Forensic Industrial Auditors.<br>Demonstration on three synthetic cases written into the script; it does not read SAP, Wi-Fi or CAN-bus data. Checks each step-to-step transition against a table of allowed transitions and maximum times, and flags consecutive scans that imply moving faster than 2.2 m/s. The Little's Law check runs on figures fixed in the code, and the odometry and Wi-Fi checks print explanations written in advance. Design notes, which go beyond what the script does: [`supply_chain_causal_forensics_architecture.md`](supply_chain_causal_forensics_architecture.md). | **Day 5–14 (Forensic Audit)** |

---
*Direct programmatic integration with the root mathematical suite: [`inventory_mechanics.py`](../inventory_mechanics.py) · [`econometric_engine.py`](../econometric_engine.py) · [`core_event_contracts.py`](../core_event_contracts.py) · [`inbound_fsm_guardrail.py`](../inbound_fsm_guardrail.py).*
