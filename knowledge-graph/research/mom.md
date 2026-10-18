# Dossier: The Mom Test (Rob Fitzpatrick)
**Key:** `mom` | **Target Practice:** Forward Deployed Engineering & Deployment Strategy

---

## 1. Core Thesis in 5 Lines
1. Asking people if your idea is good guarantees they will lie to you politely; you must never ask anyone if your idea is good.
2. The Mom Test rules: (1) Talk about their life, not your idea; (2) Ask about past specifics, not future generics; (3) Talk less, listen more.
3. Bad data comes in three toxic forms: compliments (fatal), fluff (generic promises), and feature ideas (unvetted opinions).
4. Customer conversations are failures unless they terminate in concrete commitment (time, reputation, or money) and advancement.
5. In enterprise deployments, existing user workarounds and current software spend are the only reliable evidence of genuine pain.

---

## 2. Chapter-by-Chapter Map

* **Ch 1: The Mom Test:** Why your mother and friendly customers will mislead you to protect your feelings. The three core rules.
* **Ch 2: Avoiding Bad Data:** How to deflect compliments (*"Thanks, but how do you solve that right now?"*), anchor fluff down to specific past events, and dig into feature requests to find underlying motivations.
* **Ch 3: Asking Important Questions:** Asking the "scary questions" that could invalidate your business model. Distinguishing between critical needs and nice-to-haves.
* **Ch 4: Keeping it Casual:** Why formal "feedback meetings" kill honesty. The art of 5-minute hallway chats and coffee-machine discovery.
* **Ch 5: Commitment and Advancement:** The difference between a meeting that "went well" and one that succeeded. Defining commitment currencies: Time, Reputation Risk, and Money. Avoiding zombie leads.
* **Ch 6: Finding Conversations:** Cold outreach, industry events, and warm introductions without sounding like a salesperson (The Vision-Framing-Weakness-Pedestal-Ask framework).
* **Ch 7: Choosing Customers (Segmentation):** Customer slicing: narrowing down broad personas (*"manufacturers"*) to specific who-and-where groups (*"Quality assurance leads in automotive plants with ISO 9001 compliance deadlines"*).
* **Ch 8: Running the Process:** Taking disciplined notes, capturing verbatim quotes, and debriefing with the engineering trio immediately after interviews.
* **Ch 9: Conclusion and Cheat Sheet:** Synthesis of good vs. bad questions and summary checklists.

---

## 3. Step-by-Step Toolkits for a Deployed Strategist

### A. The Mom Test Enterprise Interview Script Bank
* **To uncover real operational pain:**
  * *"Walk me through the last time a batch failed inspection on Line 3. What happened step-by-step?"*
  * *"What did you do first? What software did you open?"*
* **To measure current economic spend (Revealed Preference):**
  * *"What have you already bought or tried to build internally to fix that?"*
  * *"How many hours did your team spend manually reconciling those spreadsheets last Friday?"*
* **To deflect toxic compliments:**
  * *Client:* *"Wow, this AI dashboard looks incredible! Our team would love this."*
  * *FDE Response:* *"Thank you. But before we get excited about the visuals—when was the last time you actually needed to generate this report? How did you do it?"*
* **To dig beneath a feature request:**
  * *Client:* *"Can you add an automated PDF export button here?"*
  * *FDE Response:* *"We could, but who receives that PDF? What do they do with it once they open it?"*

### B. The 3 Currencies of Commitment
At the end of any discovery session, test for advancement by requesting one of:
1. **Time Commitment:** *"Can your lead technician sit with us for 90 minutes next Tuesday to run a live test on actual production data?"*
2. **Reputation Commitment:** *"Can you introduce us to the VP of Maintenance so we can verify if this aligns with their budget priorities?"*
3. **Financial / Resource Commitment:** *"Are you willing to allocate 2 dedicated test servers and sign an LOI for Phase 2 if we hit 98% accuracy on this pilot?"*

---

## 4. Official Resources & Tools
* **Official Platform:** The Mom Test ([momtestbook.com](https://www.momtestbook.com))
* **Author Platform & Tools:** Rob Fitzpatrick ([robfitz.com](https://robfitz.com))
* **Follow-up Works:** *Write Useful Books*, *The Workshop Survival Guide*.

---

## 5. Field Playbook for Deployed Strategists

| Trigger in Deployment | FDE Action | Artifact / Script |
|---|---|---|
| **Operator requests 15 custom UI bells and whistles.** | Dig beneath feature requests; look for workarounds. | *"Why is that button important? Show me what you do today when that button doesn't exist."* |
| **Sponsor says: 'The demo was great, let's talk next month.'** | Diagnose a Zombie Lead; force commitment or exit. | *"If this isn't in your Top 3 priorities this quarter, let's pause now so your team doesn't waste time."* |
| **User gives vague future predictions: 'I would use this daily.'** | Anchor Fluff to past specifics. | *"How many times did you do that task last week? Walk me through what you did on Thursday."* |
| **Preparing for site discovery.** | Define the 'Big 3' questions. | Write down the 3 questions that could prove our deployment thesis dead wrong before arriving on site. |
