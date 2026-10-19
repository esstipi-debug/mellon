# v5 · The strategist vs. the specialists, 4:5 social cut

**Deliverable:** `sd-four-requests-4x5.mp4`: 1080×1350, 30 fps, 4:15, English narration (Kokoro, am_michael), burned-in English subtitles, -16.0 LUFS. Poster: `sd-four-requests-4x5-poster.jpg`.

Kept for history, superseded: `sd-five-requests-4x5-r1.mp4` and its poster (first 4:5 cut, before the critic-3 fixes) and `sd-five-requests-r1.mp4` (16:9). Those names, and the title in `BRIEF.md`, say "five"; the video has four requests, as its narration says.

## How it is built (`work/`)

- `script.json`: narration per scene, the source of truth.
- `tts.py` writes `voice/*.wav` and `timeline.json` (`timeline.js` loads it as `window.TL`).
- `mix.py` writes `audio.wav` (pads, pluck, sub, ducked under the voice).
- `scene_social.html`: Three.js maquette plus canvas overlays. `window.SCRIPT` must equal `script.json`, and every phrase used for timing must exist in it.
- `render_social.js`: Playwright capture at 1080×1350. `range a b` writes `frames/f_%05d.jpg`; four ranges ran in parallel.
- Encode (two-pass loudnorm, measured on `audio.wav`):
  `ffmpeg -framerate 30 -i frames/f_%05d.jpg -i audio.wav -c:v libx264 -preset slow -crf 25 -pix_fmt yuv420p -af loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-22.03:measured_TP=-2.14:measured_LRA=2.40:measured_thresh=-32.05:offset=0.23:linear=true -c:a aac -b:a 128k -ar 48000 -shortest`

## Numbers

All figures come from `fdekit demo` (seed 7) output: 54.12% conformance (433/800), 313 releases between 9:00 and 10:30, 61% of the wait before picking, pick medians within 6%, 157 m walked per order, 49.4 to 34.6 m per visit (model estimate), rework 2.3x with dimension errors, 25.6% of products with a master-data defect, pilot +56% vs. control +64% (median), DiD -4.7 min.

## Limits

- The pilot read uses 3 days per group; the spec asks for 21. The screen says so.
- fdekit's demo control chart is not used. Its baseline chunks one day's cases in order, so the release wave sits inside it and its limits and "degradation" verdict do not hold. The cut shows a weekly-review card instead.
- "People hear automation and feel replacement" is a practice claim, not a case finding.
- The case is synthetic; the end card says so.
