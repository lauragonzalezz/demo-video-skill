"""Hear every shortlisted Kokoro voice before picking one, on a page that works offline.

    python voice_lab.py            # render the samples and write the page
    python voice_lab.py --serve    # ...and serve it, so the audio players work

Kokoro's official demo space only offers English, so there is no way to hear its Spanish
voices short of running them. This does that locally: each voice in `kokoro_catalog.py`
reads its language's sample line, the clips land in `exports/voice-lab/`, and an
`index.html` next to them plays each one with its grade and notes.

Everything is local: Kokoro runs on this Mac and the page is static. No ElevenLabs voice is
rendered here, since those would bill characters and send the text off the machine; pick one
with `voices.py` instead.

Clips are cached by `tts.py`, so running this again is fast and re-renders nothing.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import socketserver
import tempfile
from pathlib import Path

from kokoro_catalog import DEFAULT, SAMPLES, VOICES, Voice
from tts import voice_lines

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "exports" / "voice-lab"

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kokoro voice lab</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0 auto; padding: 2.5rem 1.25rem 4rem; max-width: 46rem;
         background: #12141a; color: #e8e9ee;
         font: 16px/1.55 ui-sans-serif, -apple-system, "Helvetica Neue", sans-serif; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 .35rem; }}
  p.lede {{ color: #a2a7b6; margin: 0 0 2rem; }}
  h2 {{ font-size: 1rem; text-transform: uppercase; letter-spacing: .08em;
       color: #8e94a6; margin: 2.5rem 0 .5rem; }}
  blockquote {{ margin: 0 0 1.5rem; padding: .85rem 1rem; border-left: 3px solid #2f3442;
                background: #171a22; border-radius: 0 6px 6px 0; color: #c7cbd8;
                font-size: .94rem; }}
  .voice {{ display: grid; grid-template-columns: 1fr; gap: .5rem; padding: 1rem 0;
            border-top: 1px solid #242836; }}
  .row {{ display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; }}
  code {{ font: 600 1rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; color: #9ecbff; }}
  .grade {{ font-size: .78rem; padding: .1rem .45rem; border-radius: 4px;
            background: #2a3040; color: #b8c0d4; }}
  .default {{ background: #1c4b7d; color: #d6e8ff; }}
  .note {{ color: #8e94a6; font-size: .88rem; }}
  audio {{ width: 100%; }}
  footer {{ margin-top: 3rem; color: #6e7486; font-size: .85rem; }}
</style>
<h1>Kokoro voice lab</h1>
<p class="lede">Every voice reads the same line. Pick one, then pass its name to
<code>assemble_portrait.py</code> or save it with <code>voices.py set &lt;name&gt;</code>.</p>
{sections}
<footer>Rendered locally with Kokoro-82M. Nothing was sent anywhere.</footer>
</html>
"""


def section(title: str, sample: str, voices: list[Voice]) -> str:
    blocks = []
    for voice in voices:
        default = ' <span class="grade default">default</span>' if voice.name == DEFAULT else ""
        grade = f' <span class="grade">{voice.grade}</span>' if voice.grade != "-" else ""
        blocks.append(
            f'<div class="voice"><div class="row"><code>{voice.name}</code>{grade}{default}'
            f'<span class="note">{voice.accent}, {voice.gender} — {voice.note}</span></div>'
            f'<audio controls preload="none" src="{voice.name}.wav"></audio></div>')
    return (f"<h2>{title}</h2>\n<blockquote>{sample}</blockquote>\n" + "\n".join(blocks))


def build(out: Path, only: list[str] | None = None) -> Path:
    """Render every shortlisted voice's sample into *out* and write the page beside them."""
    wanted = [v for v in VOICES if not only or v.name in only]
    if not wanted:
        raise SystemExit(f"no shortlisted voice matches {', '.join(only or [])}; "
                         "see python kokoro_catalog.py")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        for voice in wanted:
            line = SAMPLES[voice.language]
            print(f"  {voice.name} ...", flush=True)
            (clip, seconds), = voice_lines([line], voice.name, Path(scratch))
            shutil.copyfile(clip, out / f"{voice.name}.wav")
            print(f"  {voice.name}  {seconds:.1f}s", flush=True)
    languages = [("English", SAMPLES["en"], [v for v in wanted if v.language == "en"]),
                 ("Spanish", SAMPLES["es"], [v for v in wanted if v.language == "es"])]
    page = PAGE.format(sections="\n".join(section(*args) for args in languages if args[2]))
    index = out / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


def serve(folder: Path, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"\nvoice lab: http://127.0.0.1:{port}/   (ctrl-c to stop)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audition the Kokoro voices locally.")
    parser.add_argument("--out", type=Path, default=OUT, help=f"where to write ({OUT})")
    parser.add_argument("--voices", help="only these, comma separated")
    parser.add_argument("--serve", action="store_true", help="serve the page when it is built")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    target = args.out.expanduser()
    written = build(target, [v.strip() for v in args.voices.split(",")] if args.voices else None)
    print(f"\n{written}")
    if args.serve:
        serve(target, args.port)
