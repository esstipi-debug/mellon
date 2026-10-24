# The First 30 Days

## A field protocol for deploying AI inside a physical operation

<p class="byline">Marcos Stipicich · Version 1.0 · October 2026</p>

### Preface: the thesis behind the protocol

Enterprise software and AI pay off when the deployment is designed together with the real operation: its incentives, its ergonomics and its workarounds. When it is not, the formal organization adopts the system and the real one routes around it. Models will be wrong some of the time. What decides whether an error stays an anecdote or becomes a loss is how much authority the model has without a deterministic guardrail in front of it.

None of this is new, and that is the point. The protocol rests on three ideas with long records behind them.

**1. Decoupling.** Organizations adopt formal structures to look legitimate and keep the real work running underneath them (Meyer and Rowan, 1977). A system that ignores the real work gets routed around. In 2025, workers at more than 90% of the companies MIT NANDA surveyed used personal AI tools for their jobs, while only 40% of those companies had bought an official subscription.

**2. Incentives.** The more a number is used to reward or punish people, the more it distorts the process it measures (Campbell, 1979; Kerr, 1975). Part of what gets called dirty data is the record of people protecting their pay. Only part: inventory records are also wrong for plain process reasons. DeHoratius and Raman (2008) found 65% of nearly 370,000 store-level inventory records inaccurate, and linked the inaccuracy to auditing practice, store complexity and distribution structure.

**3. Authority.** The model proposes. Deterministic code calculates, validates and writes, and anything that commits cash or inventory needs a named person's approval. Security practice calls the opposite *excessive agency* (OWASP, LLM06:2025). Markets learned the same lesson before AI. In 2012 Knight Capital lost more than $460 million in 45 minutes to a faulty software deployment. It became the first enforcement action under the SEC's Market Access Rule, which requires controls that block erroneous orders.

The protocol turns those three ideas into 30 days of work that end in a decision, not a demo.

| If you are | Read |
|---|---|
| The executive who will sign the decision | Pages 1–3 and 8 |
| The team doing the work on site | Pages 3–8 |
| Checking where this comes from | Page 9 |

<!-- page -->

### What the evidence says, and how to read it

| Source | Finding | How to read it |
|---|---|---|
| MIT NANDA, *The GenAI Divide*, July 2025 | 95% of organizations report zero return from generative AI. Most enterprise tools fail on brittle workflows, no learning from context, and misalignment with day-to-day operations | Preliminary and interview-based, by the authors' own account. The cause they name is the workflow, not the model |
| Gartner CIO survey, October 2026, 2,002 CIOs | 13% say AI has delivered significant value or more. CIOs whose organizations set criteria for when a pilot should not move to production were 2.3 times as likely to be in Gartner's "pioneer" group. Only 31% had such criteria | The stop condition is the cheapest control in an AI program, and most programs skip it |
| RAND, 2024 | Cites estimates that more than 80% of AI projects fail, about twice the rate of IT projects without AI. Its interviews with 65 practitioners point mostly to problem definition, data and infrastructure | Most root causes sit outside the model |
| DeHoratius and Raman, 2008 | 65% of about 370,000 inventory records inaccurate across 37 stores | Check the ledger against the shelf before training anything on it |

### What this protocol is

Thirty days that answer one question for an executive sponsor: should this AI system go into this operation, and under what conditions? It ends with a signed go, go with conditions, or stop. Stopping is a valid result.

It is not a pilot. Nothing writes to production during the 30 days. If the answer is go, a 90-day deployment follows, staged by shift or site, with hypercare until the old workarounds are gone. The top performers in MIT NANDA's sample reported about 90 days from pilot to full implementation; large enterprises took nine months or longer.

| Days | Phase | Output |
|---|---|---|
| 0 | Before kickoff | A signed charter: sponsor, decision, stop criterion, access terms |
| 1–5 | Access | A read-only copy of the data and a first register of anomalies |
| 6–12 | The floor | The process as it is run, the shadow systems, a record-accuracy baseline |
| 13–20 | Incentives and forecast | Incentive conflicts, forecast value added, working capital exposure |
| 21–27 | The boundary | What the model may do, what code checks, what people sign |
| 28–30 | Decision | A one-page memo and a measurement plan |

<!-- page -->

## Day 0 · Before kickoff: four agreements

Many pilots are lost before they start, because nobody agreed in advance what would count as failure. Day 0 produces a one-page charter with four parts.

**1. The sponsor and the decision.** One executive who owns the operation's results signs the decision on day 30. The decision is written as a single question with a yes or no answer. For example: *should replenishment proposals from this system replace manual purchase orders for Class A items at this distribution centre?*

**2. The stop criterion.** Written before any data arrives, so the results cannot rewrite it.

> We stop if, by day 30, [the metric] cannot be measured against [the comparison], or the expected effect is below [the threshold], or [the named risk] has occurred.

**3. Access terms: five business days.**

- Read-only access to a copy of the data, never to production.
- A named owner on the client side for each data source.
- Day 3 checkpoint: the connection works and the tables match the data dictionary.
- Day 5: access is verified, or the sponsor decides. If the sponsor cannot clear it by day 6, the engagement stops there, without blame and with the reason in writing. A program that cannot get read-only data in a week will not get adoption in a quarter.

**4. Safety terms.**

- No writes to production during the 30 days.
- Every proposed change lives in a staging area as a change set that a named person approves.
- One named person can stop everything, and everyone knows who that person is.

| Day 0 charter | Filled in by |
|---|---|
| Decision question, answerable yes or no | Sponsor |
| Stop criterion | Sponsor and deployment lead |
| Data owners and access date | IT |
| Owner of the stop switch | Sponsor |
| Signatures and date | Sponsor, IT, deployment lead |

<p class="note">A working template, not legal language. Contract terms go through the client's counsel.</p>

<!-- page -->

## Days 1–5 · Access: a read-only copy and a first list of anomalies

### What to ask for, in a distribution operation

- Item master, units of measure and conversion factors.
- Inventory on hand by location, and every inventory movement for the last 12 to 24 months.
- Purchase orders, receipts and supplier lead times.
- Sales orders and shipments.
- The forecast as the system produced it and as it was finally approved, with who changed what.
- KPI and bonus definitions for every role that touches the process. This one usually sits with HR or finance, and it is the one most often forgotten.

### First checks, written as code so they can be rerun

Each check is a query that returns the rows breaking one rule. The first run gives a count; every later run shows whether the count moves.

- Negative stock on hand, or stock in locations that do not exist.
- Movements without a source document, or adjustments that cluster at month end.
- Units of measure that do not convert, such as a case recorded as a single unit.
- Supplier lead times in the system that differ from actual receipts by more than one planning cycle.
- Forecast overrides: how many, by whom, and in which direction.

### Findings are hypotheses until the floor confirms them

Every result goes into an anomaly register with its row count and the question it raises. Nothing in the register is a conclusion yet. Days 6–12 decide which entries are real, which are recording habits, and which are the system working as designed.

| Anomaly register | Example entry |
|---|---|
| Rule broken | Adjustments posted in the last two days of the month |
| Rows | 1,240 of 18,600 adjustments (illustrative) |
| Question for the floor | Who posts them, and what were they correcting? |
| Status | Open until days 6–12 |

**Output:** a data inventory, the anomaly register, and the list of questions to take to the floor.

<!-- page -->

## Days 6–12 · The floor: the process as it is run

### Walk every shift, including nights

With supervision thin, the night shift shows how the work really gets done: how a blocked order gets released when IT is asleep, where the cheat sheets live, and who gets the message when something breaks.

### Ask about the last time, not about opinions

People asked what they think tell you what sounds right. People asked what happened last time tell you what they did (Fitzpatrick, *The Mom Test*, 2013).

| Do not ask | Ask instead |
|---|---|
| Would a screen that suggests pick waves help you? | Walk me through the last wave that went out late. What did you do, and who did you message? |
| Do you trust the stock figure in the system? | The last time the scanner sent you to an empty location, what did you press, and what did you write down? |
| Would you follow the order quantity the system proposes? | On your last purchase order for this item, what did the system propose and what did you send? Why? |

### Register the shadow systems

For each spreadsheet, chat group or paper form: what it does that the system cannot, who depends on it, and what breaks if it disappears. A shadow system is a requirement nobody wrote down. The deployment either absorbs it or loses the floor.

### Count blind

Count a random sample of locations, stratified by how fast the items move, without showing the counters the system quantity. Record accuracy is the share of locations where the count and the record match within an agreed tolerance. Every later number in the protocol depends on this baseline.

### Measure the flow where it will be used

Time the current workaround and the proposed flow on the floor, on the shift that will use it, with the equipment and gloves the job requires. If the new flow is slower or takes more steps than the workaround, the floor will go back to the workaround.

**Output:** the process as run next to the process as documented, the shadow-system register, the record-accuracy baseline, and the ergonomic limits the design has to respect.

<!-- page -->

## Days 13–20 · Incentives and the forecast

### The incentive map

For each role that touches the process, write down the metric that pays them, and ask one question: whose bonus gets worse if this system works? Where the answer is anyone, expect resistance that looks irrational and is not.

An example from my own floor work. Management described a run of mixed, short and damaged orders as random warehouse errors. Walking the floor showed they were coming from a bonus paid on individual output: the metric rewarded speed and ignored what reached the customer. I retired the metric and tied the bonus to zero complaints and response time. The errors were not random. The incentive was producing them.

### Forecast value added

Compare three forecasts over the same periods: a naive one, the system's statistical forecast, and the final forecast after people changed it. Each step's value added is the error of the step before it minus its own error.

| Step | Error (WAPE) | Value added |
|---|---|---|
| Naive forecast | 38% | — |
| Statistical forecast | 31% | +7 points |
| Final forecast, after overrides | 34% | −3 points |

<p class="note">Illustrative numbers. The audit runs by planner and by category.</p>

A negative step usually has a reason that is not skill. Planners who are blamed for stockouts and never for excess learn to inflate. The fix sits in the incentive, not in the planner.

### Working capital

For the largest purchasing lines, put each discount next to its cost: carrying the extra quantity for the months it takes to sell, at the carrying-cost rate finance signs off on. A minimum order quantity can cost more than the discount it buys. That number belongs on the buyer's screen before the order goes out.

**Output:** the incentive map with its conflicts, the forecast value added table by planner and category, and the working capital tied up by order minimums and discounts.

<!-- page -->

## Days 21–27 · The boundary: where the model stops

### Who does what, in writing

| Task | Who does it |
|---|---|
| Read, summarize, classify, draft, explain | The model |
| Calculate quantities, costs and dates; check minimums, case packs, capacity and budget | Deterministic code |
| Approve anything that commits cash, inventory or a promise to a customer | A named person |
| Stop everything | The owner of the stop switch |

### Three lanes, by impact

Every proposed change falls into one lane. The thresholds are set with finance in this phase, not copied from another company.

- **Green.** Reversible and inside agreed limits. Applied after the automatic checks pass.
- **Yellow.** Inside policy but large or unusual. Needs a named approver.
- **Red.** Commits material cash or breaks policy. Needs the sponsor.

### How it behaves when something fails

- A failed check means nothing is written, and the person who asked sees which rule failed.
- An approval is tied to the exact change it approved. If the change set is edited, the approval no longer applies.
- If a safeguard is misconfigured, for example a missing signing key, writes stop instead of continuing with a warning. This is the rule most often missed.

### Test the boundary on history before anyone trusts it

Build the checks against the staging copy and replay the last months of orders through them. Two numbers matter: how many past problems each lane would have caught, and how many good orders it would have blocked. A guardrail that nobody tested is a slide.

| Replay result | Why it matters |
|---|---|
| Problems caught, by lane | Shows the boundary earns its friction |
| Good orders blocked | Shows how much friction the floor will feel |
| Orders the model could not classify | Shows where people stay in the loop |

**Output:** the boundary specification, lane thresholds signed by finance, and the replay results.

<!-- page -->

## Days 28–30 · The decision

### The one-page memo to the sponsor

| Section | Content |
|---|---|
| The question | As written on day 0 |
| The stop criterion | Met or not, with the number |
| What we found | The top three findings from the floor, the incentives and the data |
| Expected effect | A range with its assumptions, not a single point |
| Risks | Each one, and the lane that covers it |
| Cost to proceed | People, licenses, and the client's own time |
| Recommendation | Go, go with conditions, or stop |

### The measurement plan, if the answer is go

One primary metric. Its baseline from days 6–12. A comparison group that does not get the change at first: another shift, site or item family. The dates of the first and second readings. Comparing the change against both its own past and a group that did not change separates the effect of the system from everything else that moved that quarter; in statistics this is a difference-in-differences design.

### The next 90 days, if the answer is go

- Staged rollout: one shift or site first, the comparison group later.
- Hypercare on the floor until the old workarounds are gone, not until go-live.
- Shadow systems retired one at a time, each one only after its job is covered.
- The stop criterion stays alive in production. Gartner found that criteria for ending low-value AI projects already in production were rarer still: 17% of CIOs reported them.

### If the answer is stop

The memo says why, what would have to change for a different answer, and what the client keeps: the anomaly register, the shadow-system register, the record-accuracy baseline and the incentive map. A stop on day 30 costs a month. A stop in month nine costs the budget and the floor's trust.

**Output:** a signed decision, plus either the measurement plan and the 90-day plan, or a clean stop.

<!-- page -->

## Where this comes from, and its limits

Thirteen years in distribution, inventory and planning in Chile, Argentina and Australia. Three pieces of that work shaped this protocol.

**AGCO, Melbourne, 2022–2024.** I ran the operations side of a cutover from a custom WMS to Manhattan Associates in a distribution centre with more than 50,000 SKUs and a 20-person floor team. Over the years the team had built undocumented workarounds around the old system, so configuring from the documentation would have deployed against an operation that did not exist. I mapped the process the floor actually ran and stayed through hypercare until the workarounds were gone. Order processing time fell 20% after the cutover. There is no written baseline for that figure, and Manhattan is a better product than the system it replaced, so part of the gain belongs to the software.

**The bonus case on page 6:** an incentive producing the errors management called random.

**A USD 30M P&L, 2020–2022,** owned across direct and wholesale channels, which is why every phase here ends in a number finance can check.

**Code.** I build the deterministic side. `kern` is a supply chain decision engine where the model never computes a quantity and writes to the system of record go through approval ([github.com/esstipi-debug/kern](https://github.com/esstipi-debug/kern)). It is built and tested; no client runs it in production yet.

### Limits

- This protocol writes down how I worked in operations. It has not yet been run as a packaged 30-day engagement with an outside client.
- Thirty days assumes one site and one decision. Programs across several sites need more time in days 6–20.
- Numbers in the examples are illustrative unless a source is named.

### Sources

Meyer and Rowan, *American Journal of Sociology*, 1977 · Kerr, *Academy of Management Journal*, 1975 · Campbell, *Evaluation and Program Planning*, 1979 · DeHoratius and Raman, *Management Science*, 2008 · Fitzpatrick, *The Mom Test*, 2013 · U.S. SEC, press release 2013-222 on Knight Capital · RAND, *The Root Causes of Failure for Artificial Intelligence Projects*, 2024 · Challapally, Pease, Raskar and Chari, *The GenAI Divide: State of AI in Business 2025*, MIT NANDA · OWASP Top 10 for LLM Applications 2025, LLM06 · Gartner, CIO and Technology Executive Agenda survey, October 2026.

<p class="byline"><a href="https://www.linkedin.com/in/marcos-stipicich">linkedin.com/in/marcos-stipicich</a> · <a href="https://github.com/esstipi-debug">github.com/esstipi-debug</a></p>
