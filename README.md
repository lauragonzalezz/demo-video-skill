# demo-video

A Claude Code skill for making narrated product demo videos **without screen capture** —
including a **native iOS app on the simulator**.

Two ways to record, one pipeline:

- **A phone demo.** `simctl` records the simulator's screen, so you get the phone's own
  picture: portrait, full bleed, no window chrome and no device bezel. You mark what the
  viewer should see; everything else — setup taps, loaders, the wait for a sync — is cut.
- **A web or terminal demo.** Playwright records each window (a terminal, a web app, a chat
  app) headless, as its own stream on one clock, and lays them out as windows on one
  desktop. Works with the Mac's screen locked.

Either way the narration is voiced with [Kokoro-82M](https://github.com/hexgrad/kokoro) (an
open-weight voice that runs on your Mac, so your script stays on it), and you get a
time-stamped script. A person can then read that script as the real voice-over and finish in
iMovie — or you name an [ElevenLabs](https://elevenlabs.io) voice for a finished read, which
sends the script to ElevenLabs. Re-recording one scene doesn't touch the others.

> **Credit.** This is built on **[trianglegrrl/demo-video-skill](https://github.com/trianglegrrl/demo-video-skill)**
> by Alaina Hardie (MIT), used and extended with her blessing. Her recorder, clip model,
> narration stack and desktop renderer are the foundation; the simulator backend and the
> portrait renderer are what this repository adds. See [ATTRIBUTION.md](ATTRIBUTION.md) for
> the file-by-file split and her base commit.

## Install

```bash
git clone https://github.com/lauragonzalezz/demo-video-skill ~/DEV/demo-video-skill
ln -s ~/DEV/demo-video-skill ~/.claude/skills/demo-video
```

The symlink means one source of truth: edits to the repo are live in the skill immediately.
(Cloning straight into `~/.claude/skills/demo-video` works too.) Then ask Claude Code for a
demo video; the skill loads itself. `SKILL.md` is what Claude reads; this README is for
people.

## Requirements

macOS, [uv](https://docs.astral.sh/uv/) and ffmpeg (`brew install ffmpeg`). Kokoro needs
Python 3.10–3.12, which uv fetches on its own; its first run downloads the model (~330 MB).
Then, for whichever path you're on:

| Path | Also needs |
|---|---|
| **Phone** | Xcode, and a booted simulator (`xcrun simctl boot 'iPhone 17 Pro Max'`). Pillow, which uv fetches per run. Only a scene that taps *by itself* needs a UI driver: `brew install idb-companion && pipx install fb-idb` |
| **Web/terminal** | tmux, Playwright's Chromium, and ffmpeg **with `drawtext`** — Homebrew's plain `ffmpeg` is built without freetype, so `brew install ffmpeg-full` and put `$(brew --prefix ffmpeg-full)/bin` first on `PATH`. It is bottled and keg-only, so it sits beside your ffmpeg rather than replacing it |

The phone path deliberately avoids `drawtext`: it draws its title cards with Pillow, so you
don't need a source build of ffmpeg to make a phone demo.

Check what you have:

```bash
bash ~/.claude/skills/demo-video/scripts/doctor.sh --simulator   # or --web, or neither for both
```

## Smoke test

```bash
# Phone: needs a booted simulator and nothing else. ~1 minute.
bash ~/.claude/skills/demo-video/examples/phone-hello/run.sh

# Web and terminal. ~3 minutes.
bash ~/.claude/skills/demo-video/examples/hello/run.sh
```

The phone one drives the stock **Settings** app with `simctl` alone — no UI driver, no app
to build, no network — and writes `exports/phone-hello/final/phone-hello.mp4`.

## What you get

| File | Use |
|---|---|
| `<out>.mp4` | The video with the placeholder narration, to hear the pacing |
| `<out>-picture.mp4` | The video without audio: record your voice-over over it |
| `<out>-script.md` | Each line with its start time and how many seconds it has |
| `<out>-preview.mp4` | A smaller copy for chat uploads |

The human voice-over and iMovie finish are manual: see
[voiceover-and-imovie.md](voiceover-and-imovie.md).

## Writing a demo

A demo is a folder with two files. `demo.py` is the configuration — the title, the device,
the streams, and one narration line per shot:

```python
TITLE = "Adding your first task"   # "" skips the intro card
BACKEND = "simulator"
FORMAT = "portrait"                # the canvas takes the footage's shape: full bleed
OUT = Path("../../exports/my-demo")
DEVICE = "iPhone 17 Pro Max"
BUNDLE_ID = "com.example.myapp"
STREAMS = {"phone": {"title": "iPhone"}}
SCENES = [{"take": "s1-intro", "lines": ["Open the app and pick a project.", ...]}]
```

`scenes.py` says what happens, and — this is the whole idea — which parts the viewer sees:

```python
with SimTake("s1-intro", DEMO) as t:
    with t.clip("choosing a project", "phone"):   # kept
        t.tap_text("Projects")
        t.wait(1.2)
    t.until("Synced", 60)                          # cut: off camera, costs the viewer nothing
    with t.clip("the project is open", "phone"):   # kept
        t.wait(2.5)
```

Copy a template into `demos/<name>/` and edit:

```bash
cp -r examples/phone-hello demos/my-demo && rm demos/my-demo/run.sh
```

`demos/` is gitignored, so your own demos stay yours; `examples/` holds the two that ship
with the skill. `SKILL.md` has the full method, including how to drive the app when you'd
rather not install a UI driver.

## Voices

The narration engine is chosen by the *shape of the voice's name*: `af_heart` is Kokoro
(local, free), `eleven:River` is ElevenLabs (bills characters, sends your script off the
Mac), anything else is a macOS `say` voice. A key alone never turns ElevenLabs on — you have
to name the voice.

Everything here runs through [uv](https://docs.astral.sh/uv/), which builds a throwaway
environment per run — so none of it installs into your system Python or touches any other
project's dependencies. macOS has no bare `python`, so the full command is:

```bash
cd ~/DEV/demo-video-skill
uv run -q --no-project python scripts/kokoro_catalog.py      # the local voices, graded
uv run -q --no-project python scripts/voice_lab.py --serve   # hear them all, offline
uv run -q --no-project python scripts/fit_portrait.py <demo> # does the picture outlast each line?
```

The lab serves on <http://127.0.0.1:8787/>; Ctrl-C stops it. The first run voices every
sample (a minute or so), after which they are cached and it starts instantly.

The voice lab exists because Kokoro's official demo space is English-only, so its Spanish
voices can't be auditioned anywhere else. ElevenLabs setup is in
[SKILL.md](SKILL.md#setting-up-elevenlabs); skip it entirely if you're using Kokoro.

Voiced lines are cached in `~/.cache/demo-video/tts`, so only a changed line is voiced (or
billed) again.

## Layout

| Path | What |
|---|---|
| `SKILL.md` | The steps Claude follows |
| `scripts/` — recording | `sim_recorder.py` + `sim_driver.py` (the simulator), `recorder.py` (Playwright), `stage.sh` + `term_mirror.py` (a clean terminal), `human.py` (a drawn cursor) |
| `scripts/` — rendering | `assemble_portrait.py` (phone, full bleed), `cut.py` + `assemble.py` (the desktop compositor), `layout.py` (canvas presets), `titlecard.py` (Pillow title cards) |
| `scripts/` — narration | `tts.py`, `kokoro_lines.py`, `elevenlabs.py`, `voices.py`, `kokoro_catalog.py`, `voice_lab.py` |
| `scripts/` — timing | `fit_portrait.py`, `fit.py`, `retime.py` |
| `examples/` | `phone-hello/` (simulator) and `hello/` (web) — smoke tests and templates |
| `demos/` | Your own demos, one folder each. Gitignored |
| `exports/` | Everything generated: takes, finals, the voice lab. Gitignored, and safe to delete |
| `troubleshooting.md` | Symptoms, causes and fixes |
| `tests/` | `uv run -q --no-project --with playwright --with pillow --with pytest pytest tests` |

## License

MIT — see [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md). Fork it and use it.
