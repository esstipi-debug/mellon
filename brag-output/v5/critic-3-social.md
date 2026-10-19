# Critic 3: social cut, verdict FIX

**Scope.** The named file was replaced mid-review by `sd-five-requests-4x5-r1.mp4` (19:12); I judged -r1. Its picture runs 0.4 s later, and its subtitles are now in sync. Audio: -16.3 LUFS, LRA 2.2, true peak -1.3 dBTP. Frame 0 is flat beige.

**Verdict: FIX.** Still a voiced slide. Sound off, a viewer gets a warehouse and "Four reasonable requests" by 3 s, and four requests plus "54.12%" by 30 s. Then 196-222 s is a text ledger over a dimmed 3D set, and the finale names five branches.

**Defects (mm:ss)**
1. 01:20-01:24, s2 to s3: prior panels stay under the REQUEST 3 header.
2. 01:53-01:55, s3 to s4: ENFORCE stamp stays under NOBODY ASKED.
3. 00:49-00:53, s2: "58 min" drawn over "within 6%".
4. 01:08-01:09, s2: "313" panel collides with the STATISTICS strip.
5. 00:34-00:35, s1: REPAIR tag hidden under the 54.12% panel.
6. 02:47-02:53, s5: 16-px caveat against the subtitle.
7. 03:45, s7: tag runs off the right edge.
8. 03:17-03:49, s7: about 6 s of near-static frames.
9. 03:06-03:16, s6: charts are a seeded random series, not XmR data.
10. 03:44-03:47, s7: "every branch changed a decision" is asserted in 21-px tags. Assertion-only beats: s0 framing, s3 "would have punished", all of s6.

**Fact errors**
- s1 "every number is real" contradicts "synthetic"; say "reproducible."
- s2 "single wave": 313 checks (97+110+106 per half hour), but a 90-minute hump. Gemba's "400 at 10:00, 9 pickers" is unsupported (peak 110); the film says seven pickers.
- s3 "one in four bad master data" (25.6%, any defect) is chained to "removes ~14% of rework". The 2.3x and 14% are dimension-only (18.1%), and the 14% is carton rework per A3.
- s4 "near the dock": "golden zone" is undefined.
- s5 means, but spec_linea_base.md pre-specifies the median (unsigned). On medians: pilot +56%, control +64%, DiD about -4.7 min. Parallel trends are unverified, yet the film states -5.0 as fact. The spec asks 21 baseline days; both windows here are 3.
- s6 "operators feel replacement": no source. "Signed by them": TWI signature lines are blank, and A3 schedules them for weeks 11-12.
- s7 owners versus A3: chart "shift supervisor" (A3: FDE); "pilot" (A3: FDE); "Level the release, ops lead" drops A3's peak-staffing resize (week 4); "data owner" (A3: client master-data lead); "FDE + ops" (A3: FDE). FDE credit is partial.
- CTA "Polymath Manifesto" title is unsourced. Field quotes match gemba.

**Readability (under 26 px)**
- HUD: `#why .r b` and `.c` 15; `#why .r` 23; `#kick .k` 18.
- s1: REPAIR 24, tags 22, source 19. s2: picker tags 22. s3: packer line 22, tags 22-24, CI 22. s4: "157 m" caption 22. s5: axis 18, BEFORE/AFTER 17, CI 19, caveat 16. s6: captions 20-21. s7: AS ASKED/DECIDED 22, owners 18, branch tags 21, CTA footer 19.

**Top 6 fixes**
1. `render()` in scene_social.html and the capture in render_social.js line 15. Current: prior overlays linger 4 s and 2.3 s. Suggested: re-render; frames at 80.0 and 113.5 show only the new beat.
2. `OV.s2`, `w6`. Current: fades at 53.0 s. Suggested: fade out from 'But the order waits'; start `c1` at `AT('Statistics says',.9)`.
3. `OV.s1`, REPAIR tag. Current: drawn before the panel, 24 px. Suggested: draw after `panel(140,BAND,800,240,b)`, 28 px.
4. `OV.s7`, owners (`size:18`) and `dd` tags (`21`). Suggested: 26 px owners from A3 (FDE: monitor, pilot, baseline; client master-data lead; client ops lead: peak staffing). Cut the branch tags, or tie each to a number at 30 px.
5. `OV.s5`, caveat (`size:16`, `y1+76`). Suggested: 26 px above the chart, "3-day baseline, trends unverified"; axis 18 to 24.
6. `OV.s6`, `rng(5)`. Suggested: plot hallazgos `degradation_alarm` (centre 76.4, UCL 96.7, LCL 56.2, mean 86.5), or label the chart illustrative. Cut runtime toward 120 s (X's standard cap was 2:20; verify) and make frame 0 the hook.
