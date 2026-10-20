# Executive Memo — Fulfillment Bottleneck: USD 10.0M Annual EBITDA Leakage and USD 15.7M Trapped Cash

> **Pillar 2 — Executive Problem Decomposition & P&L Gravitas**
> Structure: Minto Pyramid, Answer First (SCQ-R). Companion logic tree: [`mece_issue_tree.mmd`](mece_issue_tree.mmd).
> **Figures are an illustrative reference case** (USD 480M revenue distributor, one national DC). Every number below is a formula over named inputs in §Appendix; replace inputs with client data on Day 1. Do not present these values as client facts.

---

**To:** CEO, CFO, COO · **From:** Deployment Strategist · **Decision required by:** next operating committee · **Reading time:** 3 minutes

## Answer

**Approve a 12-week, single-DC pilot with a held-out control zone.** The fulfillment operation is leaking **USD 10.0M of EBITDA per year** and holding **USD 15.7M of excess inventory**. Roughly 70% of the leakage traces to three fixable causes: wrong master data, unmanaged pick exceptions, and advertising that sells stock we do not have. The pilot fixes those three, and a Difference-in-Differences test against the control zone measures the result before any network rollout is funded.

## Situation

- Revenue USD 480M; gross margin 30%; 2.4M outbound orders per year through one DC.
- Inventory stands at **62 days on hand (DOH)** against a 45-day policy.
- Order fill rate is **93.8%** against a 97.5% customer commitment.

## Complication

- **Cost-to-serve is USD 1.35 above standard on every order** (USD 3.24M per year). The excess is driven by pick exceptions at wrong locations and carton rework from wrong item dimensions. In the reference event log, 46% of orders hit at least one exception path (location exception, carton rework, repack, or short pick). Expedited freight to recover late orders adds **USD 1.45M**.
- **Stockouts cost USD 2.66M of gross margin per year**, even while we carry 17 days of excess stock. The inventory is in the wrong SKUs.
- **USD 1.10M of digital ad spend per year lands on SKUs that are out of stock** or cannot be replenished within the campaign window. Marketing and supply chain do not share a stock signal.
- **Excess inventory costs USD 1.57M per year** in storage, shrink, and obsolescence. It also traps USD 15.7M of working capital, and the capital charge on that cash (USD 1.9M per year) sits below EBITDA and is excluded from the 10.0M.
- A master-data audit of 317 SKUs found **25% with at least one defect**: 17.7% dimensions out of tolerance, 13.2% weight out of tolerance, 7.9% location mismatch.

## Question

Which interventions recover the most EBITDA and cash fastest? And how do we prove the gain came from the intervention rather than from seasonality or volume swings?

## Resolution — Three Moves, One Proof

| # | Move | Mechanism | Target EBITDA (yr) | Evidence asset |
|---|---|---|---:|---|
| 1 | **Clean only the master data that pays** | Rank each defect class by Expected Value of Information (EVI). Fix the classes where expected benefit exceeds cleaning cost, and leave the rest alone. | 1.6M of 3.24M handling excess | `fdekit/hubbard_evi_calculator.py` |
| 2 | **Interlock ad spend with stock** | Automatically pause or reduce campaigns on SKUs whose stockout probability before replenishment exceeds threshold. Every change is a signed, expiring, reversible changeset. | 1.10M ad waste + ~0.8M recovered margin | `fdekit/launch_readiness_gate.py` |
| 3 | **Reslot and standardize exception handling** | ABC reslotting plus a TWI job card for the exception path on night shift. | 1.0M handling + 0.7M expedite | `docs/twi_job_instruction_card.md` |
| — | **Prove it** | Difference-in-Differences: pilot zone vs. control zone, inference clustered by day, placebo-lead test on the pre-period. | — | `fdekit/diff_in_diff_analysis.py` |

**Pilot target:** USD 5.2M annualized EBITDA, plus a DOH reduction path toward 50 days (USD 11.0M cash) once the forecast-to-replenishment loop is closed.

## Decisions Requested Today

1. **Budget:** approve the 12-week pilot scope (one DC, one zone treated, one zone held out as control).
2. **Access:** read access to WMS task events and the item master. Write access stays behind the signed-changeset gate, with no direct writes.
3. **Measurement rule:** finance pre-agrees the success metric (median order cycle time and cost-to-serve per order), the control zone, and the significance standard (p < 0.01, day-clustered) **before** the pilot starts.

## Risks Stated Up Front

- **Pre-period length.** A 3-day pre-window cannot verify parallel trends: the reference panel shows a 48% per day minimum detectable divergence. The pilot requires a **minimum 21-day baseline** before the intervention starts.
- **Attribution.** Not every exception is caused by master data. The EVI model carries attribution as an explicit uncertain input, not a hidden assumption.
- **Adoption.** A fix the night shift does not use is not a fix. Usage is measured weekly during hypercare.

---

## Appendix — Derivation of Every Figure

| Line | Formula | Inputs (illustrative) | Result (USD) |
|---|---|---|---:|
| Handling excess | orders/yr × excess cost/order | 2.4M × 1.35 | 3.24M |
| Expedited freight | recovery shipments × premium | budget variance line | 1.45M |
| Lost gross margin | revenue × fill-rate gap × GM% × unrecovered share | 480M × 3.7% × 30% × 50% | 2.66M |
| Ad waste on OOS SKUs | Σ daily budget on OOS SKUs × days | campaign export × stock snapshot | 1.10M |
| Holding opex | excess inventory × holding opex rate | 15.65M × 10% | 1.57M |
| **EBITDA leakage** | sum of the five lines above | | **10.02M** |
| Excess inventory (cash) | (DOH − policy) × COGS/365 | 17 × 336M / 365 | 15.65M |
| Capital charge (below EBITDA) | excess inventory × WACC | 15.65M × 12% | 1.88M |
