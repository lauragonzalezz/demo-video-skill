---
name: demo-video
description: Use when making a narrated product demo or screencast video — of a native iOS app on the simulator (a phone demo, portrait, full bleed, no hand-recording), or of a terminal, web app, Teams or Slack window — when real waits would bloat the video, when the Mac's screen is locked or OBS/screen capture records blank frames, when the narration should be a local Kokoro or an ElevenLabs voice, when the picture plays on in silence after a line ends, or when a person will record their own voice-over and finish the edit in iMovie.
---

# Demo video

Records a demo and narrates it, with the waits cut out. Two backends, one contract:

- **`BACKEND = "simulator"`** — a native iOS app on the simulator. `simctl` records the
  screen itself, so the output is the phone's own picture: **portrait, full bleed, no window
  chrome and no device bezel**. This is the path for an app demo.
- **`BACKEND = "playwright"`** (the default) — Alaina Hardie's original: Playwright records
  each web app, terminal or chat window as its own stream, headless, and lays them out as
  windows on a fake macOS desktop at 1920x1080. The Mac may be locked.

Both write the same `events.jsonl` (`start`, `clip`, `clipend` on one take clock) and the
same four outputs, and share the whole narration stack: Kokoro-82M locally by default, an
ElevenLabs voice, or macOS `say`. For a placeholder read, a person then reads the
time-stamped script as the real voice-over and finishes in iMovie.

`SKILL` below means this skill's folder. Tools are in `SKILL/scripts/`.
`examples/phone-hello/` is the simulator smoke test and template; `examples/hello/` is the
web one.

## Running things

- Python: `export DEMO_VIDEO_SCRIPTS=SKILL/scripts` (required once a demo folder is copied
  out of the skill), then run every script, the skill's by full path, as:
  - phone path: `uv run -q --no-project --with pillow python <file>`
  - web path: `uv run -q --no-project --with playwright python <file>`
  "`python`" below means whichever of those matches the path you are on.
- Agent harness: tmux, local ports, Playwright and the simulator need the sandbox off. Takes
  run for minutes: start them as background commands and wait for the completion
  notification (or watch the log with Monitor), never `sleep`.
- Stop what you start: `stage.sh stop <session>` and any local server you launched.

---

# The phone path (iOS simulator)

## 1. Preflight

`bash SKILL/scripts/doctor.sh --simulator`, then `bash SKILL/examples/phone-hello/run.sh`
as is. It needs a booted simulator and nothing else: the smoke test moves the screen with
`simctl` alone, so there is no UI driver to install, no app to build and no network. Done
when it prints `.../phone-hello.mp4  (0:1x.x)`. If it fails, nothing else will work.

Boot a simulator with `xcrun simctl boot 'iPhone 17 Pro Max'`; `python
SKILL/scripts/sim_recorder.py devices` lists what is available and what is booted. In Xcode
26 and later the window is **Device Hub**, not Simulator.app — but nothing here needs the
window open, because `simctl` records the framebuffer directly.

## 2. Script first

Copy `examples/phone-hello/demo.py` and `scenes.py` (not `run.sh`) into a folder of your
own. In `demo.py` set:

- `TITLE` — the intro card. **Set it to `""` to skip the card**; a short demo often reads
  better without one. `SUBTITLE` is optional.
- `BACKEND = "simulator"`, and `FORMAT` (`portrait` is the default here: the canvas takes the
  footage's own shape, so the phone fills the frame. `reels` forces 9:16, `square` 1:1 —
  footage that doesn't match is padded, never stretched).
- `OUT` — where takes land. A relative path resolves against the demo folder, so
  `Path("../../exports/<name>")` keeps generated media in the repo's gitignored `exports/`.
- `DEVICE` (a name like `"iPhone 17 Pro Max"`, a udid, or `None` for whichever is booted),
  `BUNDLE_ID` (launched off camera before the take), `DRIVER` (below).
- `STREAMS` — exactly one entry for a simulator take, e.g. `{"phone": {"title": "iPhone"}}`.
- `SCENES` — one take per scene, **one line per clip** (`None` = silent).

Budget ~2.7 words a second for Kokoro, ~3 for ElevenLabs against the length asked for;
`fit_portrait.py` measures the voice you actually pick. Write the lines in the voice of the
person who will read them (their voice skill, if they have one): full spoken sentences,
plain words, not captions. A word Kokoro gets wrong takes its pronunciation inline,
`[frontmatter](/fɹˈʌntmætəɹ/)`; the script shows just the word. Public-facing: no customer
or prospect names. Review the lines as an expert in the audience's job would ("Act as a
<their role> with fifteen years in the job…"): wrong numbers, vague timings, claims a
practitioner would doubt. Done when the person approves the lines. If you can't ask, go on
and mark the lines **unapproved** in the handoff.

## 3. Who taps the phone

`SimTake` records and keeps the clock; something else touches the UI. Pick one:

| `DRIVER` | Who taps | Needs | Use it when |
|---|---|---|---|
| `"manual"` (default) | **you, the agent**, or a person | nothing | the normal case: you already have the Expo MCP's `automation_tap`/`automation_type`, or you can drive the app by hand |
| `"idb"` | `scenes.py` itself | `brew install idb-companion && pipx install fb-idb` | a take must re-record unattended, or you want it fully repeatable |

**Agent-driven (`manual`).** Start the recorder in the background and send it clip
boundaries on a control pipe while you tap:

```bash
python SKILL/scripts/sim_recorder.py session <demo-folder> <take>   # prints the pipe's path
echo 'clip choosing a project' > <OUT>/<take>.partial/ctl           # a shot starts
#   ...tap through the app now...
echo 'clipend' > <OUT>/<take>.partial/ctl                           # a shot ends
#   ...setup, waiting out loaders: off camera, so it costs the viewer nothing...
echo 'end'     > <OUT>/<take>.partial/ctl                           # finish the take
```

Clip boundaries land on the take clock exactly as a scripted take's do, so everything
downstream is identical. Tap latency sits inside the clip, which is why the holds matter.

**Scripted (`idb`).** `scenes.py` runs start to finish: `t.tap_text("Save")`, `t.tap(x, y)`,
`t.type("...")`, `t.swipe("up")`, `t.until("Done", 20)`, `t.wait(1.2)`. Taps are by
accessibility label, so a screen with good labels is reliable to drive.

Either way, a scene can move the app without any driver at all: `t.open_url("myapp://...")`
for a deep link, `t.launch(bundle_id)`, `t.appearance("dark")`.

## 4. Scenes

One function per take. `with t.clip(label, "phone"):` holds **only what the viewer should
see**; everything between clips is cut, so long waits, setup taps and loaders are free. A
wait of a few seconds that shows progress can stay on camera; cut it otherwise and let the
line say so — only cuts of 20 s or more get an on-screen "+N s" tag.

Hold a reading shot with `t.wait(seconds)` inside the clip, and **size that hold against the
line**: the picture holds its last frame if the line runs longer, which reads as a freeze.
Unlike the web path, a still phone is fine — a static screen records almost no frames, and
the recorder rebuilds the take at a constant frame rate with the last frame held, so a
motionless app comes out as a held picture rather than a gap.

Before the first clip, off camera: get the app to a known state (`t.launch(...)` relaunches,
`t.appearance("light")`, a deep link to the right screen). The status bar is pinned to 9:41
with full bars for the take and cleared afterwards; set `STATUS_BAR = False` in demo.py to
leave it alone.

## 5. Record and look

Run the scene (scripted) or hold a session (agent-driven). A take that fails keeps the
previous good one; its partial recording stays in `OUT/<take>.partial`. Then pull frames and
**look at them**:

```bash
ffmpeg -ss T -i <OUT>/<take>/phone.mp4 -frames:v 1 frame.png
```

Done when every shot shows what its line says: no splash screen, no empty list, no keyboard
covering the thing being pointed at, text readable. `t.screenshot(path)` grabs the phone
mid-scene while you are building one.

## 6. Fit and assemble

Each shot runs for its clip or its line, whichever is longer, so a line shorter than its
footage leaves the picture playing in silence. Measure that first:

```bash
python SKILL/scripts/fit_portrait.py <demo-folder> [voice]
python SKILL/scripts/assemble_portrait.py <demo-folder> <out.mp4> [voice] [--fit]
```

Where it says to add words, write them in the reader's voice and have the person approve
them, as in step 2; where a shot is too long, prefer **shortening the hold and re-recording
that take** — the gaps between clips are already free. `--fit` on this path only **speeds a
shot up** (to 1.5x), never cuts: the cutting half of `retime.py` finds dead air by looking
for stretches where only something cursor-sized moved, which is a mouse heuristic and would
be guessing on phone footage.

The first Kokoro run downloads the model (~330 MB) and takes a minute; after that it voices
faster than real time. Voiced lines are cached, so re-running is quick and re-bills nothing.

Writes `<out>.mp4` (narrated), `-script.md` (each line's start and its seconds),
`-picture.mp4` (no audio, the voice-over master) and `-preview.mp4` (small, for chat).

## 7. Hand off

Same as the web path — see [Hand off](#hand-off) below.

---

# The web and terminal path

Unchanged from Alaina's original. In short:

1. **Preflight.** `bash SKILL/scripts/doctor.sh --web`, then `bash
   SKILL/examples/hello/run.sh` as is (it owns tmux `hellodemo`, ports 7692 and 8795, and
   `~/Movies/demo-video/hello`). Done when it prints `.../hello.mp4  (0:2x.x)`. This path's
   title card and "+N s" tags need ffmpeg's `drawtext` filter, which Homebrew's plain ffmpeg
   lacks — `doctor.sh --web` says so and how to fix it. (The phone path draws its text with
   Pillow instead, so it does not need this.)
2. **Script first.** Copy `examples/hello/demo.py` and `scenes.py`. Set `TITLE`, `OUT`,
   `PROFILES` (a folder of its own: two demos sharing one collide), `TMUX`, `STREAMS` (at
   most 4; order sets the window slots) and `SCENES`. Same rules for writing lines as above.
3. **Scenes.** One function per take. `with t.clip(label, focus):` holds only what the viewer
   should see. Long waits go **between** clips; a short wait for output can sit inside one
   with `t.until(pattern, timeout, poll=0.3)`. Point with `human` (headless draws no
   pointer): `human.cursor(page)` once per page, then `human.click`/`human.move`/
   `human.hover` (a hover-only button: `human.reveal(page, parent)`, then `click(page,
   button, within=parent)`) and `human.wheel`; hold a reading shot with `human.idle(page,
   seconds)`, **not** `time.sleep` — a frozen page stops Chromium's recording, because it
   writes a frame only when something changes. A stream behind a login either signs in once
   by hand (`python SKILL/scripts/recorder.py signin <demo-folder> <stream>`, for MFA) or in
   its `prepare` on every take.
4. **Record and look.** `bash SKILL/scripts/stage.sh start <session> <port> [cwd]
   [highlight-regex]`, start any local servers, run each take, then `python
   SKILL/scripts/cut.py <demo-folder> <take>` and pull frames from
   `OUT/<take>/<take>-desktop.mp4`. **Look at them.**
5. **Fit and assemble.** `python SKILL/scripts/fit.py <demo-folder> [voice]`, then `python
   SKILL/scripts/assemble.py <demo-folder> <out.mp4> [voice] --fit`. Here `--fit` does cut
   stills as well as speed up, so check nothing that matters was one.
6. **Hand off.** Below.

---

# Voices and fit

## Picking a voice

There is **no engine switch**: the *shape of the name* picks the engine, so "Kokoro or
ElevenLabs" is really "which name".

- `af_heart`, `bf_emma`, `ef_dora` … → **Kokoro**, local and free.
- `eleven:River`, or plain `eleven` → **ElevenLabs**, which bills characters and **sends the
  lines off this Mac**.
- anything else → macOS `say -v`.

The order: the command line, `VOICE` in demo.py, the saved choice, then `af_heart`.

**Ask the person before assembling**, in two questions:

1. **Engine.** "Local Kokoro (free, offline) or ElevenLabs (needs a key)?" — only offer
   ElevenLabs when a key is already present (`ELEVENLABS_API_KEY` or
   `~/.config/demo-video/elevenlabs.env`). Otherwise offer Kokoro only.
2. **Voice.** Show the shortlist: `python SKILL/scripts/kokoro_catalog.py`. To let them
   *hear* it, `python SKILL/scripts/voice_lab.py --serve` renders every shortlisted voice
   reading a line of product copy, in English and Spanish, onto a local page. Kokoro's own
   demo space is English-only, so this is the only way to audition the Spanish ones.

Default to `af_heart` if they don't choose. Pass the name as the `[voice]` argument, or save
it once with `python SKILL/scripts/voices.py set <name>`.

A voice cloned from a real person needs that person's permission: never pick one on your own.

## Setting up ElevenLabs

Only when the person wants an ElevenLabs voice. `doctor.sh` says whether a key is there, not
whether it works. With none, ask them to create one on the
[ElevenLabs Developers page](https://elevenlabs.io/app/developers), under API Keys,
restricted to Text to Speech and Voices (read), with a credit quota if they want a spending
cap. Then have them run this in their own terminal, which saves it with mode 600 and keeps
it out of shell history:

    mkdir -p ~/.config/demo-video && (umask 077; printf "ElevenLabs key: "; read -rs key; echo; printf "ELEVENLABS_API_KEY=%s\n" "$key" > ~/.config/demo-video/elevenlabs.env)

Never ask for the key in chat, put it on a command line or print it, and don't search other
projects for one; if they point you at a file that has it, copy the line without showing it.
`ELEVENLABS_API_KEY` in the environment wins over the file, so an old one there hides a new
key. Done when `python SKILL/scripts/voices.py list --search River` prints River (free). A
401 means a bad key or a missing permission.

    python SKILL/scripts/voices.py list [--search TEXT] [--gender G] [--accent A]
    python SKILL/scripts/voices.py say Matilda "A line to audition." --out try.wav  # bills the line
    python SKILL/scripts/voices.py set Matilda --stability 0.4     # saved for every demo

`set` takes `--model`, `--stability`, `--similarity`, `--style`, `--speed` and
`--speaker-boost`, for that voice only; one demo overrides them with `VOICE_SETTINGS` in
demo.py. The default model, `eleven_v4`, ignores `--speed` and reads `[word](/ipa/)` inline:
audition those words.

ElevenLabs runs only when named — a key alone never turns it on, and a *saved* ElevenLabs
voice counts, sending every later demo's lines. Never use it for a script the person hasn't
cleared to leave the Mac.

## Fitting

A shot should run for its speech plus `--pause` (1 s: a person changing gears). What it has
beyond that is dead air.

- **Phone** (`--fit` on `assemble_portrait.py`): speeds the shot up, to `--max-speed` (1.5).
  It never cuts. What is left over is reported as words to add.
- **Desktop** (`--fit` on `assemble.py`): cuts what is still in the front window first
  (`human.idle` drift counts as still; clicks, moves and new text do not), then speeds up.
  A shot's last second is never cut. A shot with no line holds 3 s.

Neither ever writes narration, and neither slows footage down.

# Changing a shot later

Re-record only that take and re-assemble; other takes are reused as recorded. A wording
change needs only the assemble step, and re-voices only that line.

# Hand off

An ElevenLabs read can be the finished video: hand over `<out>.mp4`. For a human read:
`-picture.mp4` (record over it), `-script.md`, the narrated `.mp4` (to hear the pacing once)
and [voiceover-and-imovie.md](voiceover-and-imovie.md); assemble that one without `--fit` or
with `--pause 2`, since a human reads slower than the voice it was fitted to. In chat, send
`-preview.mp4` (uploads cap at 30 MB). The script's times hold for the voice used.

# When it breaks

[troubleshooting.md](troubleshooting.md): blank terminal, wrong cue matched, Teams refusing
the browser, a shot rendering for minutes, ffmpeg filter errors, small text, a background
window that looks black — plus the simulator's own failures.
