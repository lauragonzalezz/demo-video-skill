# Attribution

This repository is a derivative of **[trianglegrrl/demo-video-skill](https://github.com/trianglegrrl/demo-video-skill)**
by Alaina Hardie, used and extended with her blessing under the MIT licence. Her
copyright notice stays in [LICENSE](LICENSE) alongside ours.

**Base commit:** [`3c100ed9ae0fe90d43bf973cf216b76cab69738b`](https://github.com/trianglegrrl/demo-video-skill/commit/3c100ed9ae0fe90d43bf973cf216b76cab69738b)
(`Update README.md`, 2026-11-04) — copied 2026-11-23.

There is deliberately **no `upstream` git remote**: this is a separate project, not a
fork. To pull in later improvements, diff by hand against that commit:

```bash
git clone https://github.com/trianglegrrl/demo-video-skill /tmp/upstream
diff -ru /tmp/upstream/scripts scripts | less
```

Then update the base commit recorded above once you have ported what you want.

## Which files are derived, and which are ours

### Derived from Alaina's repo

Unchanged except where noted. These carry her copyright.

| File | Change |
|---|---|
| `scripts/recorder.py` | `load_demo` moved to `scripts/demos.py`; re-exported, so `from recorder import load_demo` still works |
| `scripts/cut.py` | Canvas and layout constants now come from `scripts/layout.py` (identical landscape values); `wallpaper` and `render` call `require_drawtext` first |
| `scripts/assemble.py` | `title_card` calls `require_drawtext` first |
| `scripts/fit.py` | Unchanged |
| `scripts/retime.py` | Unchanged |
| `scripts/human.py`, `scripts/cursor_path.py` | Unchanged |
| `scripts/term_mirror.py`, `scripts/stage.sh` | Unchanged |
| `scripts/tts.py`, `scripts/kokoro_lines.py`, `scripts/elevenlabs.py`, `scripts/voices.py` | Unchanged |
| `scripts/doctor.sh` | Extended with simulator and Pillow checks; her checks kept |
| `examples/hello/` | Still the web-path smoke test. One change: `OUT` (and `run.sh`'s final path) point at the repo's gitignored `exports/`, not `~/Movies`, so all generated media lands in one place |
| `tests/test_*.py` | Her suite, unchanged. `conftest.py` gains a `pillow` fixture, and its `drawtext` fixture now asks `ffmpeg_path` rather than probing PATH directly |
| `troubleshooting.md`, `voiceover-and-imovie.md` | Unchanged |
| `SKILL.md` | Extended with the simulator backend; her web/terminal steps kept |

### Original to this repository

| File | What it does |
|---|---|
| `scripts/demos.py` | `load_demo`, lifted out of `recorder.py` so the simulator path needs no Playwright |
| `scripts/layout.py` | `FORMAT` presets: the canvas as a parameter instead of hardcoded `1920x1080` |
| `scripts/sim_recorder.py` | `SimTake`: `simctl io recordVideo` on a booted iOS simulator, same `events.jsonl` contract |
| `scripts/sim_driver.py` | The UI driver seam: `idb`, and a manual/agent-driven driver |
| `scripts/assemble_portrait.py` | Portrait, single-stream, full-bleed renderer (no desktop chrome) |
| `scripts/fit_portrait.py` | The dead-air report for the portrait path |
| `scripts/titlecard.py` | Pillow title cards, so the portrait path needs no ffmpeg `drawtext` |
| `scripts/ffmpeg_path.py` | Finds the keg-only `ffmpeg-full` when the `ffmpeg` on PATH cannot draw text, so the desktop renderer needs no shell setup |
| `scripts/kokoro_catalog.py` | A graded shortlist of Kokoro voices (`voices.py` only catalogs ElevenLabs) |
| `scripts/voice_lab.py` | Local page to audition those voices, English and Spanish |
| `examples/phone-hello/` | The simulator-path smoke test, against the stock iOS Settings app |
| `tests/test_sim_recorder.py`, `tests/test_portrait.py`, `tests/test_layout.py` | Tests for the above |

Our additions are MIT too, so the whole repository stays MIT: fork it and use it.
