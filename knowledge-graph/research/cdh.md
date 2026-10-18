# Dossier: Continuous Discovery Habits (Teresa Torres)
**Key:** `cdh` | **Target Practice:** Forward Deployed Engineering & Deployment Strategy

---

## 1. Core Thesis in 5 Lines
1. Enterprise product and deployment teams must replace milestone-based feature shipping with continuous, outcome-driven learning loops.
2. Discovery is conducted weekly by the core trio (Product/Strategist, Designer, Engineer) directly interacting with operators and users.
3. The Opportunity Solution Tree (OST) visually connects top-level business outcomes $\rightarrow$ customer opportunity space $\rightarrow$ solutions $\rightarrow$ assumption tests.
4. Interviews should never ask hypothetical opinions; they extract specific, chronological past stories of real customer behavior.
5. Teams should not test full solutions; they map and test the underlying leap-of-faith assumptions (desirability, usability, feasibility, viability, ethics).

---

## 2. Chapter-by-Chapter Map

* **Ch 1: The What and Why of Continuous Discovery:** Defining continuous discovery: weekly touchpoints with users to drive measurable outcomes, not output volume.
* **Ch 2: Outcomes over Outputs:** Distinguishing business outcomes (lagging, e.g. revenue) from product outcomes (leading behavioral metrics, e.g. weekly active workflows).
* **Ch 3: Visualizing Your Thinking:** The Opportunity Solution Tree (OST). Building a shared mental map to prevent solution fixation.
* **Ch 4: Continuous Interviewing:** Establishing an automated recruiting pipeline so interviews happen every week with zero friction.
* **Ch 5: Story-Based Interviewing:** How to ask questions that uncover past behavior instead of generic generalities or feature wishlists.
* **Ch 6: Synthesizing What You Learn:** The Interview Snapshot: Capturing quotes, quick facts, pain points, and experience maps on a single page.
* **Ch 7: Mapping the Opportunity Space:** Grouping and structuring customer needs into a parent-child opportunity tree.
* **Ch 8: Prioritizing Opportunities:** Assessing opportunity sizing, market factors, and customer urgency before brainstorming solutions.
* **Ch 9: Ideating Solutions:** Generating multiple alternative solutions per opportunity to foster "Compare and Contrast" decision-making.
* **Ch 10: Identifying Hidden Assumptions:** The 5 assumption types: Desirability, Viability, Feasibility, Usability, and Ethics. Using the Assumption Map.
* **Ch 11: Testing Assumptions:** Designing small, rapid experiments (unbounce pages, concierge tests, prototype walkthroughs) instead of shipping MVPs.
* **Ch 12: Measuring Discovery Impact:** Evaluating whether the team's discovery cadence is moving the needle on the target product outcome.
* **Ch 13: Managing Stakeholders with Discovery:** Showing your work through the OST so executives understand trade-offs and rationale.

---

## 3. Step-by-Step Toolkits for a Deployed Strategist

### A. The Opportunity Solution Tree (OST) for Deployments
When deploying complex software in an enterprise client:
1. **Desired Outcome (Top):** Specific leading metric (e.g., *"80% of daily maintenance workorders generated automatically without manual phone escalation"*).
2. **Opportunities (Branch 1 & 2):** Discovered pains from interviews:
   - *Opp A:* "Field technicians cannot read error codes in low-light environments."
   - *Opp B:* "Shift supervisors don't trust automated priority rankings."
3. **Solutions (Under Opp B):** Compare and contrast 3 solutions:
   - *Sol 1:* Display historical failure precedent alongside the priority rank.
   - *Sol 2:* Allow supervisors to override and log rationale in 1 click.
   - *Sol 3:* Implement peer-review verification for top-severity flags.
4. **Assumption Tests (Under Sol 1):** Rapid test: *Do supervisors actually read the historical precedent when given a paper prototype?*

### B. Story-Based Interview Protocol for Field Deployers
Never ask: *"Do you like the new system?"* or *"What features do you want?"*
* **Opening:** *"Think back to the last shift where equipment unexpectedly jammed. Walk me through that morning from the moment you noticed something was wrong."*
* **Drilling In:** *"What was the very next button you pressed? What was on your screen?"*
* **Uncovering Workarounds:** *"What did you do when the system showed an error? Did you call someone on WhatsApp? Did you write it down on paper?"*

---

## 4. Official Resources & Tools
* **Official Platform:** Product Talk ([producttalk.org](https://www.producttalk.org))
* **Templates & Courses:** OST Canvas, Interview Snapshot Template, Assumption Mapping Matrix available via Product Talk Academy.

---

## 5. Field Playbook for Deployed Strategists

| Trigger in Deployment | FDE Action | Artifact / Script |
|---|---|---|
| **Client demands a fixed 12-month feature roadmap.** | Reframe to Outcome-based delivery using an OST. | *"Let's fix the target metric (e.g. cycle time reduction), and let our weekly discovery uncover which features actually move it."* |
| **Team is building features operators never use.** | Mandate weekly Story-Based Interviews with operators. | Run 3 interviews/week; synthesize onto 1-page Interview Snapshots shared with client leads. |
| **Debate over whether a complex integration is needed.** | Run Assumption Mapping (Feasibility vs. Desirability). | Test if operators even perform the workflow before spending 4 sprints building the backend API. |
| **Executive questions team direction.** | Walk them through the OST visual map. | Show how the chosen solution connects directly to their strategic board outcome. |
