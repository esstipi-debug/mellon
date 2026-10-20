# Gemba Interview Protocol — The Mom Test Applied to the Warehouse Floor

> **Pillar 1 — Ground Truth Discovery & Gemba Ethnography**
> Companion to [`gemba-walk.md`](gemba-walk.md) (the walk itself) and `fdekit gemba` (the capture schema that produces `gemba_turno_1.jsonl` and `hallazgos.json`).
> Source method: Rob Fitzpatrick, *The Mom Test* (2013), adapted for frontline distribution operations.

---

## 1. Purpose and Scope

This protocol governs every conversation a Deployment Strategist holds with frontline operators, team leads, and shift supervisors during on-site discovery. Its single objective is to collect **verifiable evidence of past behavior** — what people actually did, with which tool, how often, and at what cost — and to reject opinions, forecasts, and compliments as data.

It applies to: receiving, putaway, replenishment, picking, packing, dispatch, inventory control, and returns. It does not replace the physical walk (cycle-time observation, spaghetti tracing); it runs alongside it, at the point of work, never in a meeting room.

**Exit criterion for a shift:** every workaround observed or mentioned has a row in the Shadow Artifact Register (§6) with a frequency, a cost estimate, and a named owner — or an explicit reason why one of those is still `None`.

---

## 2. The Three Rules (Operational Translation)

| Mom Test rule | Warehouse translation | Failure it prevents |
|---|---|---|
| Talk about their life, not your idea | Ask about the last shift, not about the system you plan to deploy | Operators tell you what they think you want to hear about "the new tool" |
| Ask about specifics in the past, not generics or opinions about the future | "Walk me through the last time…" — anchor to a date, an order, a pallet, a location | "We usually…" describes the official process, not the real one |
| Talk less, listen more | The interviewer speaks < 20% of the time; silence after an answer is a tool, not a gap | The strategist's hypothesis contaminates the evidence |

---

## 3. Question Discipline

### 3.1 Prohibited Questions (Speculative, Leading, or Hypothetical)

These questions produce **noise that looks like signal**. They are banned during discovery. If one is asked by mistake, the answer is recorded as `opinion` and excluded from quantification.

| Prohibited question | Why it fails |
|---|---|
| "Would you use an app that tells you the next pick location?" | Future hypothetical. People are poor predictors of their own behavior and want to be polite. |
| "Do you think the WMS is slow?" | Leading opinion. Invites agreement, yields no magnitude. |
| "How much would you pay / how much time would this save you?" | Fabricated number. Nobody has measured it. |
| "Is the scanner a problem?" | Yes/no on a pre-selected suspect. Hides the problems you did not think of. |
| "What features would you want?" | Delegates solution design to the person least positioned to weigh trade-offs. |
| "You follow the putaway procedure, right?" | Compliance trap. Guarantees a "yes" and conceals the workaround. |
| "Why don't you just use the system?" | Accusatory. Ends the conversation and the trust. |

### 3.2 Required Questions (Verifiable Past Action)

Every required question is anchored to **a specific past event** and admits a **checkable answer** (a document, a screen, a location, a timestamp, a person).

| Required question | Evidence it unlocks | Verification path |
|---|---|---|
| "Walk me through the last time the scanner dropped connection. What time was it, and what did you do next?" | Real fallback procedure; frequency; recovery latency | Compare against WMS gap in `event_log.csv` timestamps for that resource |
| "Show me the last pick where the location was empty. Where did you find the product?" | Location master error; informal search pattern | `PICK_EXCEPTION_LOCATION` events; `location_mismatch` in `auditoria_maestros.csv` |
| "What did you do with the last carton that didn't fit the box the system assigned?" | Dimension master error; rework path | `CARTON_REWORK` / `REPACK` events; `dim_out_of_tol` |
| "When was the last time you wrote something down instead of entering it? Can I see the paper?" | Shadow artifact | Physical artifact photographed and logged in §6 |
| "Who did you call the last time an order was short? What did they tell you?" | Informal escalation network; real decision owner | Named person; cross-check with supervisor |
| "How did you decide which orders to pick first at the start of last night's shift?" | Unofficial batching / prioritization rule | Compare against `ORDER_RELEASED` sequence |
| "What took the longest yesterday that shouldn't have?" | Operator-ranked friction | Time-study observation on the next cycle |

### 3.3 Follow-up Ladder

When an answer is generic ("it happens sometimes"), descend the ladder until it is specific or explicitly unknown:

1. **When** was the last time? (date, shift, approximate hour)
2. **What exactly** happened? (order, SKU, location, equipment ID)
3. **What did you do** next? (the actual workaround, step by step)
4. **How long** did it take? (minutes; verify by observation if possible)
5. **How often** does this happen? (per shift / per week — then verify against the log)
6. **Who else** knows about it? (the next interview)

An answer that cannot reach step 3 is recorded as `unverified` — **never** as zero.

---

## 4. Defensive De-escalation Techniques

Frontline workers conceal workarounds because workarounds are, by definition, deviations from procedure, and deviations get punished. The strategist must remove that threat explicitly and repeatedly.

| Technique | Script | When to use |
|---|---|---|
| **Frame as a system audit, not a performance review** | "I'm here to find where the software and the procedures are failing *you*. Every workaround you show me is a defect report against the system, not against you." | Opening of every conversation |
| **Non-attribution guarantee** | "Nothing you tell me goes into a report with your name on it. I record what happens, not who did it." (Then honor it: findings are logged by role and shift, not by name.) | Opening; again when the operator hesitates |
| **Expert inversion** | "You've run this aisle for years. I've been here two hours. Teach me how it *really* works when the system is wrong." | When the operator gives the official answer |
| **Normalize the deviation** | "Every DC I've worked in has a notebook like this somewhere. It usually means the system was missing something important." | When a shadow artifact is half-revealed |
| **Go to the work, not the break room** | Interview at the station, during the task, with the equipment in hand | Always — memory improves at the point of work |
| **Separate supervisor and operator** | Never interview an operator with their supervisor present | Always |
| **Close the loop visibly** | Return within 48 h with one fix or one answer to something the operator raised | Builds the credibility required for the second interview |

**Red flags that defensiveness is active:** answers phrased as procedure ("we always scan first"), glances toward the supervisor, sudden brevity, or "I'd have to check." Response: stop asking, observe one full cycle in silence, then ask about what you just saw.

---

## 5. Interview Execution Checklist

**Before the shift**
- [ ] Pull the previous 7 days of `event_log.csv` for the zone; list the top 5 exception activities by frequency.
- [ ] Pull `auditoria_maestros.csv` for SKUs in the zone; note defect classes present.
- [ ] Prepare one specific past-event question per top exception (§3.2).
- [ ] Confirm with the shift lead *where* you will stand, not *whom* you will interview.

**During the shift**
- [ ] Open with the system-audit frame and the non-attribution guarantee.
- [ ] Ask only past-action questions; descend the follow-up ladder.
- [ ] Photograph every shadow artifact (with permission) and log it immediately.
- [ ] Time at least three cycles of any workaround you are told about.
- [ ] Record each statement with an evidence tag: `observed`, `artifact`, `stated_past`, `opinion`, `unverified`.

**After the shift**
- [ ] Reconcile every `stated_past` frequency against the event log. Log the delta.
- [ ] Complete §6 for every artifact and workaround.
- [ ] Load findings into `fdekit gemba` capture so they enter `hallazgos.json`.
- [ ] Schedule the 48 h close-the-loop return.

---

## 6. Forensic Template — Shadow Artifact & Workaround Register

One row per artifact or workaround. Missing fields are written as `None` with a reason — never as `0` or blank.

```markdown
### SA-<shift>-<nn>: <short descriptive name>

| Field                         | Value |
|-------------------------------|-------|
| Artifact type                 | spreadsheet / paper log / label / taped cheat sheet / verbal rule / device setting |
| Physical location             | e.g., "taped inside forklift FL-07 cab", "shared drive \\dc01\turno_noche\faltantes.xlsx" |
| Owner (role, not name)        | e.g., "night-shift replenishment lead" |
| Process step it patches       | receiving / putaway / replenishment / picking / packing / dispatch / inventory |
| System gap it compensates     | what the WMS/ERP fails to provide (missing field, wrong master data, latency, no report) |
| Evidence tag                  | observed / artifact / stated_past / unverified |
| First known use               | date or "unknown — operator joined after it existed" |
| Frequency of use              | per shift; source: observation or event-log reconciliation |
| Time cost per use (min)       | timed observation, n >= 3 |
| Error / risk introduced       | e.g., "manual stock count not reflected in WMS -> phantom inventory" |
| Event-log signature           | activity + resource pattern that corroborates it, or None (reason) |
| Master-data link              | defect class in auditoria_maestros.csv, or None |
| Annualized cost (USD)         | frequency x time cost x loaded labor rate x operating days; or None (reason) |
| Data the artifact holds that the system lacks | column-by-column list |
| Disposition                   | absorb into system / eliminate root cause / keep (justified) |
| Follow-up owner and date      | |
```

### 6.1 Unmasking Probes for Shadow Spreadsheets

Shadow spreadsheets rarely surface from a direct question. Use these indirect probes:

1. **Follow the printer.** Ask what gets printed at the start of each shift and who prints it. Printouts outside the WMS label flow usually come from a spreadsheet.
2. **Follow the shared drive.** Ask the supervisor which files they open before the shift handover meeting.
3. **Follow the shortage.** Ask how a short pick gets resolved. If the answer involves "the list," ask to see the list.
4. **Follow the new hire.** Ask a recent hire what they were told to "never trust the system for." Their onboarding notes are the workaround map.
5. **Follow the clock.** Compare the WMS timestamps against observed physical time. A consistent lag (e.g., putaway confirmed in batches at end of shift) means the real record lives elsewhere until then.
6. **Follow the columns.** When a spreadsheet is found, every column it has that the WMS lacks is a data-contract requirement. Log them verbatim.

---

## 7. Evidence Quality and Quantification Rules

- Only `observed` and `artifact` evidence may be used to size a financial impact without a confidence caveat.
- `stated_past` evidence may be used for sizing **only after** reconciliation against the event log or a timed observation; the reconciliation delta is reported alongside the figure.
- `opinion` evidence is retained for context and for hypothesis generation, and never enters a cost estimate.
- `unverified` is a first-class state. A workaround with unknown frequency is reported as **unknown frequency**, not as rare.
- The 72-hour success metric (Pillar 1) is met when the register has no row with an unexplained `None`.
