# Polymath Manifesto: long-form video (2:19)

- `polymath-manifesto.mp4`: 1920x1080, 30 fps, English narration + subtitles, -16 LUFS. Under X's 2:20 limit.
- `polymath-manifesto.jpg`: poster.
- `share-copy.txt`: post text.
- `work/`: sources. `script.json` (narration), `tts.py` (Kokoro-ONNX, voice `am_michael`, writes `timeline.json`), `mix.py` (voice + generated music),
  `scene.html` (14 animated diagram scenes, one per principle), `render.js` (Playwright frame renderer).

Rebuild: `python3 work/tts.py && python3 work/mix.py`, render frames with `node work/render.js work/scene.html frames range 0 4189`
(split across processes), then `ffmpeg -framerate 30 -i frames/f_%05d.jpg -i audio.wav ...`. Needs the Kokoro model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`).

Visuals are original animated diagrams (no stock or generated images). Figures shown (758 consultants, +40% / +25%, 84% vs 60-70%, ~2x odds, 1951) come from the manifesto text.
