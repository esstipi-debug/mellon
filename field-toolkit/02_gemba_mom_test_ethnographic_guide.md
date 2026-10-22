# FRONTLINE TACTICAL GUIDE:
## Floor Ethnography Protocol & "The Mom Test" Interview Guide in the Gemba

> **Document Type:** Participant-Observation Protocol & Forensic Interview Methodology  
> **Canonical Path:** `field-toolkit/02_gemba_mom_test_ethnographic_guide.md`  
> **Purpose:** Extract unvarnished operational ground truth across manufacturing plants and distribution hubs, neutralizing compliant corporate bias and cataloging shadow workflows (*Shadow IT*: Excel macros, WhatsApp groups, physical overrides).

---

### 1. The Ethnographic Golden Rule: Historical Actions vs. Speculative Opinions

Rooted in Rob Fitzpatrick’s **The Mom Test**, field interviews must strictly avoid hypothetical questions or speculative queries. Frontline personnel will systematically tell consultants whatever sounds compliant to avoid reprimand or conflict with management.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               FORENSIC QUESTION TRANSLATION MATRIX                                    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  PROHIBITED SPECULATIVE QUERY (TRIGGERS COMPLIANT BIAS):                                               │
│  "Would you like an AI-powered dispatch dashboard that automatically suggests load assignments?"      │
│  OPERATOR RESPONSE: "Yes, that sounds amazing" (and during the graveyard shift, they never log in).     │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  MANDATORY EMPIRICAL QUERY (EXTRACTS CAUSAL MECHANISM & SHADOW PROCESS):                              │
│  "Walk me through what happened last Tuesday at 2:30 AM when a resin tanker pulled up to the scale    │
│   and SAP threw a blocked purchase order exception."                                                   │
│  OPERATOR RESPONSE: "I texted the shift lead on WhatsApp, manually weighed the truck on an offline      │
│   Excel sheet, and signed a paper delivery receipt so 10 trucks wouldn't back up onto the highway."    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2. Direct Floor Shadowing Protocol

A Deployment Strategist does not audit physical operations from corporate conference rooms. We embed directly beside operators at the physical point of friction:

#### 1. Graveyard Shift Immersion (02:00 AM – 06:00 AM)
* **Objective:** Executive supervision is absent during the night shift. This window reveals the enterprise’s **true operational architecture**:
  * How are ERP outages resolved when IT is asleep?
  * What physical workarounds are executed to prevent manufacturing line shutdowns?
  * Where are the laminated cheat sheets containing manual material codes that bypass system validations?

#### 2. Forensic Audit of Shadow IT (Informal Workarounds)
During cross-dock and planning floor shadowing, the DS catalogs and inspects:
* **Local Departmental Spreadsheets:** 50 MB workbooks titled `DISPATCH_SCHEDULE_FINAL_REAL_v4_OCT2026.xlsx` stored on local drives. These workbooks encode the actual operating heuristics that the ERP is incapable of handling.
* **Operational WhatsApp Channels:** High-velocity messaging groups between drivers, yard coordinators, and dispatchers. When an inbound shipment is delayed, coordination does not occur inside enterprise software; it happens via 15-second voice memos.
* **Small-Sample Physical Sampling (*The Rule of Five*):** Pick 5 critical SKUs at random from warehouse racking and audit physical on-hand stock against ERP/WMS inventory balances. If 3 out of 5 exhibit discrepancies, transactional records are structurally corrupted, requiring stochastic models to calibrate for hidden stock.

---

### 3. Role-Based Field Interview Matrix

| Target Role | Mandatory Forensic Question | Operational Red Flag to Detect |
| :--- | :--- | :--- |
| **Weighbridge / Gate Operator** | *"When was the last time an inbound freight truck was held at the gate for more than 45 minutes, and what was the root cause?"* | The operator blames the driver; forensic inquiry reveals the order lacked an active release code in SAP, requiring an off-system email authorization. |
| **Forklift Operator / Picker** | *"When the RF handheld directs you to drop this pallet at Rack 04 Shelf B, but you see the slot physically occupied, what key do you press and what do you write down?"* | The operator confirms the drop in the handheld to preserve pick-rate performance KPIs, then stashes the pallet in an unassigned overflow aisle. |
| **Supply Chain Planner** | *"When MRP or the statistical forecasting engine recommends purchasing 1,000 units of this Class-A SKU, what quantity do you submit on the PO and why?"* | *"I always inflate the order by 20% to 30% for safety. If the plant runs out of raw material I get fired; if we overstock, nobody notices until the annual audit."* |
| **Procurement Buyer** | *"Show me the last order where a vendor offered a 5% discount for doubling batch size. Who calculated the holding cost of carrying that inventory for 6 months?"* | *"No one; my annual bonus is tied strictly to Purchase Price Variance (PPV) savings. Holding cost is logistics' problem, not mine."* |

---

### 4. Interface Ergonomics Rubric (<800 ms Latency Threshold)

Before authorizing any UI/UX or terminal workflow to production on the floor, the DS must audit:

1. **Industrial Glove Test:** Can the worker complete the core transaction using heavy industrial safety gloves without triggering adjacent capacitive buttons?
2. **Sub-Second Acoustic & Haptic Feedback:** Does visual and barcode-scan confirmation execute in **under 800 milliseconds**? A 3-second spinning loader guarantees operator bypass by Day 2.
3. **Zero Incremental Clicks:** Does the new system require more interactions than the legacy paper clipboard or informal WhatsApp workaround? If yes, the interaction design is rejected.
