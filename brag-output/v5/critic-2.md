# Critic 2 on v5 render r1 (sd-five-requests-r1.mp4, 197.5 s)

**Measured:** -16.3 LUFS integrated, true peak -1.4 dBFS, LRA 2.1 (fine). Music drops to about -22 LUFS under no VO (fine). Freezedetect (n=0.001, d=0.6) with the subtitle band cropped out: 57 static holds, 44 s in total (22 % of runtime). The longest are 36.8–41.6 (4.8 s), 68.9–71.5 (2.6 s), 42.3–44.7 (2.4 s), 140.4–142.7 (2.3 s) and 187.4–193.8 (6.4 s, before the CTA). About 27 s of frames are under 15 % occupied.

## 1. Does it prove what makes the SD special?
Partly. It is clearly better than v4, but the SD is still asserted, not shown.
- **Proves it:** Request 4 (1:55–2:19). The pilot rose 42 %, the control rose 51 %, the DiD is -5 min, so the verdict is "keep the pilot". A statistical branch flips a real decision on screen, and it reads on mute. This is the best beat in the film.
- **Mostly proves it:** Requests 1+2 (0:36–1:08). Medians within 6 %, the pick takes about 70 s, the wait is 58 min, and the queue holds 61 % of all waiting. "No retraining" is earned. "No extra pickers all day / capacity at the peak" is never shown: there is no sim curve and no peak. "THE FLOOR: it is the wait" is backed by event-log data, not the floor. Two of the three tags are decoration.
- **Half:** Request 3. The 2.3x bar is real. But "you ask the floor" shows no floor answer, even though the gemba file holds one: *"El sistema siempre me manda la caja chica para estos."* Calling it "Anthropology" with The Mom Test as the source is a stretch. "Punished the people doing the repairs" is inferred, not shown.
- **Only asserts:** "Nobody asked" (a finding with no counter-decision, and "Walking it" is not a branch of knowledge). "Psychology + Politics" has no data and no counterfactual. The SD/FDE split appears only as a two-line legend at 2:54. The amber SD dot vanishes after 0:20 except in the progress bar, and no beat shows the strategist doing anything different from the engineer.

## 2. Per scene
| Scene | Range | On screen | Empty | Problems (ranked) |
|---|---|---|---|---|
| s0 | 0–21.3 | Floor-plan board, 2 tiny dots, 4 sticky tickets, REASONABLE→MISTAKE? | ~45 % | Actors are about 1 % of the frame, so "two people" is invisible; no imagery; 6.0–7.6 static |
| s1 | 21.3–36.3 | Declared flow line → spaghetti of variants, 54.12 % | ~60 % | Thin strip in a black field for 5 s; 22.2–27.3 almost static |
| s2 | 36.3–68.1 | Axis → 7 operator dots → wait bar → 61 % ring → tags → verdict box | ~70 % | **36.3–41.6: bare axis only (5 s)**; the dots collapse to a sliver at 0 min; the verdict box covers the operator rows |
| s3 | 68.1–95.4 | Detour cards, quote box, 2.3x bars, ~14 % ring | ~65 % | 68.1–71.6 only "THE DETOURS"; 71.6–74 one lone card; right third empty all scene |
| s4 | 95.4–114.8 | White matplotlib spaghetti PNG (Spanish labels), 157 m, 100-visit waffle | ~25 % | 96.2–97 blank white plate flash; Spanish axis/title; right half empty 95.4–100 |
| s5 | 114.8–139.8 | Before/after lines, +42 % / +51 % → -5.0 min, KEEP THE PILOT | ~65 % | 114.8–118 empty axes; label collision (below); y-label wrong (section 4) |
| s6 | 139.8–160.5 | 7 dots, "replacement?", standard-work sheet, XmR chart | ~50 % | 139.8–143 seven dots plus a stray speck; sheet is a gray placeholder (wavy lines) |
| s7 | 160.5–197.5 | AS ASKED / AS SHIPPED ledger, branch→decision list, constellation, CTA | ~70 % | 160.5–166 one-word lists build on empty field; 180.8–182.7 blank; 187–194 near-static; CTA box ~25 % of frame |

## 3. Layout, collision and transition defects
- 2:01–2:08: "zone B, untouched (control)" overprinted by "+42%".
- 2:07.3–2:08.0: "-5.0 min per order" cross-fades on top of "Kill it? / +51%" (double exposure of text).
- 0:57: STATISTICS pill fades in over the PICK-05/06 labels.
- 3:14–3:17: the CTA box sits on the constellation line, and the line enters the box border.
- Every transition is the same dip to near-black (~0.3 s), then a build from empty. No object carries across, so the three "signature transformations" promised in the storyboard are absent. Every scene therefore opens with 2–5 s of empty frame.
- Same layout repeated: eyebrow + title top-left, tags top-right, subtitle, progress bar, used for all 6 beats.

## 4. Fact errors and over-claims
1. **s5 y-label "median order cycle time" is wrong.** +42 % and +51 % are *means* (56.9→80.6; 56.0→84.6). The medians are +55.8 % / +63.5 %. Relabel the axis "mean", or plot the medians.
2. "AS SHIPPED: master data fixed, capacity at the peak, a pilot that survived" states outcomes. The A3 lists these as planned countermeasures (week 3/4), and parallel trends are `conclusive:false`. Use "decided", not "shipped".
3. "The engineer built every piece of it" conflicts with the A3 owners: master data = client master-data lead; staffing = client ops.
4. "Capacity at the peak" has no peak in the data shown. The gemba gives the wave instead: 10:00 releases 400 orders, root cause batch release, countermeasure heijunka. As drawn, the claim is unsupported.
5. "Retrain seven people": the request was to retrain *the slow ones*.

Correct: 54.12 %, 6 %, ~70 s, 58 min, 61 %, 16.6/30.8/7.0 %, 2.3x (59.8 vs 26.5), 25.6 %, ~14 %, 157 m, 67.6 %, 9 of 68, 49.4→34.6 (−30 %), −4.96 min (CI 1.5–8.5), 3 pre-days. No "CD Pudahuel" visible.

## 5. Top changes, ranked
1. **Make the SD visible in every beat.** Split each decision panel into a blue lane (FDE: the chart it produced) and an amber lane (SD: the question asked, plus the decision it killed with its cost in data terms). Example: "+1 picker all day → 9.6→9.6 min (model, flat demand)". Keep the amber dot moving inside each scene, not only in the footer.
2. **Put the real floor on screen.** In s3, show the packer quote card "The system always sends me the small box" next to the 2.3x bar. In s2, replace "THE FLOOR: it is the wait" with the 10:00 wave: a 400-order block landing on a few picker lanes. That beat becomes queueing plus floor colliding into "level the release / staff the wave".
3. **Kill the empty openings.** Carry the outgoing hero object into the next scene: the 7 operator dots become the 7 people in s6, the detour cards become the ledger rows, the DiD lines become the XmR chart. Never start on a bare axis: draw data from frame 1 at 60 %+ scale.
4. **Fix the s5 label (mean vs median)** and the +42 %/control and -5.0/+51 % collisions. Reserve a right-hand column and swap values in place.
5. **Ledger honesty:** "AS DECIDED" with owners (client data lead, client ops, FDE). Show the pilot verdict as "keep, extend baseline".
6. **Imagery:** replace the white Spanish matplotlib PNG with a dark redrawn floor plan, where class-A boxes physically slide to the golden zone. Give s0/s6 human silhouettes, not 1 % dots.
7. **Cut or earn s6:** add one counterfactual ("imposed standard work → ?") or fold the beat into 10 s of the ledger. Drop the "Walking it / Anthropology" labels for the less pretentious "the floor".
8. **End:** cut the 6 s static constellation to 2 s, enlarge the CTA to 60 % of the frame and hold it 3 s or more.

**ONE MORE PASS**
