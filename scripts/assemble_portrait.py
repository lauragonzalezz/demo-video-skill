"""Assemble a narrated portrait video from one phone stream: the simulator path's renderer.

    python assemble_portrait.py <demo-folder> <out.mp4> [voice] [--fit [--pause S] [--max-speed X]]

Alaina's `assemble.py` composites a fake macOS desktop — wallpaper, menu bar, up to four
window slots — onto a 1920x1080 canvas, and forces every stream into a 16:9 window. That is
right for a browser and a terminal and wrong for a phone: a 1320x2868 recording put through
it comes out stretched flat. A phone demo has exactly one stream and it already fills the
frame, so this renderer has no compositing to do at all. What is left is: cut each shot out
of the one video, scale it to the canvas **without distorting it**, voice the line, hold the
last frame if the line runs longer, and join.

It keeps everything that is not desktop-shaped: the same `events.jsonl` contract, the same
shot boundaries (`cut.shots`), the same narration stack (`tts.py`: Kokoro, ElevenLabs or
`say`), the same last-frame hold (`assemble.finish_shot`), the same four outputs.

Differences from the landscape renderer, all deliberate:

  * **The canvas comes from the footage.** `ffprobe` measures the recording and `layout.py`
    gives back a canvas of the same shape, so a phone is full bleed with no bars. Nothing is
    hardcoded: device resolutions differ, and `FORMAT = "reels"` asks for a fixed 9:16 target
    instead, where footage that doesn't match is padded rather than stretched.
  * **The title card is drawn with Pillow** (`titlecard.py`), not ffmpeg's `drawtext`, so it
    needs no freetype build of ffmpeg and a title may contain `:`, `'` or `%`. An empty
    `TITLE` skips the card.
  * **`--fit` only speeds up; it never cuts.** `retime.py` finds dead air by looking for
    stretches where only something cursor-sized moved, which is tuned for a mouse on a
    desktop. On phone footage that test is meaningless, so the cutting half is left out
    rather than guessed at. The off-camera gaps between clips are already free.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType

from assemble import TITLE_SECONDS, check, finish_shot, stamp, voice_scenes
from cut import JUMP_TAG, TAG_S, Shot, duration, events_of, jump, shots
from demos import format_of, load_demo
from layout import canvas_for, layout
from retime import LEAD, MAX_SPEED, PAUSE, Pacing, plan, target_for
from titlecard import jump_png, title_png
from tts import choose, spoken

FADE = 0.6  # the title card's fade in and out
TAG_MARGIN = 0.045  # the cut-wait badge's inset, as a fraction of the canvas width
STREAM_SUFFIXES = (".mp4", ".mov", ".webm")  # what a recorded stream may be called


def stream_file(take: Path, stream: str) -> Path:
    """The take's video for *stream*. The simulator writes .mp4; .mov and .webm are accepted
    so a take recorded another way, or an un-normalised capture, still renders."""
    for suffix in STREAM_SUFFIXES:
        candidate = take / f"{stream}{suffix}"
        if candidate.exists():
            return candidate
    raise SystemExit(f"{take}: no video for stream {stream!r} "
                     f"(looked for {', '.join(stream + s for s in STREAM_SUFFIXES)})")


def probe_size(path: Path) -> tuple[int, int]:
    """The footage's real pixel size. Measured, never assumed: every device differs."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    stream = json.loads(out)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def render_shot(src: Path, shot: Shot, start: float, size: tuple[int, int], dst: Path,
                fps: int, tag: Path | None = None) -> None:
    """One shot, cut from the single phone video and scaled onto the canvas.

    `force_original_aspect_ratio=decrease` plus a centred `pad` is the whole trick: the
    footage keeps its shape and is letterboxed only when the canvas asks for a different
    one. On a BLEED canvas the pad is a no-op, so a phone fills the frame edge to edge.
    """
    width, height = size
    seek = max(shot.t0 - start, 0.0)
    span = shot.t1 - shot.t0
    chain = (f"[0:v]setpts=(PTS-STARTPTS)/{shot.speed},"
             f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
             f"fps={fps},format=yuv420p")
    args = ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{seek:.3f}", "-t", f"{span:.3f}",
            "-i", str(src)]
    if tag is not None:
        inset = int(width * TAG_MARGIN)
        args += ["-i", str(tag)]
        chain += (f"[base];[base][1:v]overlay=W-w-{inset}:{inset}:"
                  f"enable='lt(t,{TAG_S})'[v]")
    else:
        chain += "[v]"
    # -t on the output as well: a filter graph that outruns its input is how a 5 s shot
    # once rendered for minutes in the landscape renderer.
    args += ["-filter_complex", chain, "-map", "[v]", "-t", f"{shot.length:.3f}", "-an",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
             str(dst)]
    subprocess.run(args, check=True)
    got = duration(dst)
    if abs(got - shot.length) > 0.5:
        raise RuntimeError(f"shot {shot.label!r} rendered {got:.1f}s, expected {shot.length:.1f}s")


def title_card(demo: ModuleType, size: tuple[int, int], tmp: Path, dst: Path, fps: int) -> float:
    """The intro card, or nothing at all when TITLE is empty."""
    text = (getattr(demo, "TITLE", "") or "").strip()
    if not text:
        return 0.0
    card = title_png(text, *size, tmp / "title.png", getattr(demo, "SUBTITLE", None) or None)
    seconds = TITLE_SECONDS
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(fps),
                    "-t", f"{seconds}", "-i", str(card), "-f", "lavfi", "-t", f"{seconds}",
                    "-i", "anullsrc=r=48000:cl=mono", "-vf",
                    f"fade=t=in:d={FADE},fade=t=out:st={seconds - FADE}:d={FADE},format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(fps),
                    "-c:a", "aac", "-ar", "48000", "-ac", "1", "-shortest", str(dst)], check=True)
    return seconds


def fit_pieces(shot: Shot, speech: float | None, pacing: Pacing | None) -> tuple[Shot, ...]:
    """The shot as it will play. With *pacing*, speed it up toward its line's length — but
    never cut: see the module docstring on why still-detection is left to the desktop path."""
    if pacing is None:
        return (shot,)
    return plan(shot, [], target_for(speech, pacing.pause), pacing.max_speed).pieces


def main(demo: ModuleType, out: Path, voice_name: str, options: dict,
         pacing: Pacing | None = None) -> None:
    check(demo)
    fmt = layout(format_of(demo))
    first = demo.OUT / demo.SCENES[0]["take"]
    sample = stream_file(first, next(iter(demo.STREAMS)))
    size = canvas_for(fmt, *probe_size(sample))
    print(f"footage {'x'.join(map(str, probe_size(sample)))} -> {fmt.name} canvas "
          f"{size[0]}x{size[1]}", flush=True)
    script = [f"# {getattr(demo, 'TITLE', out.stem)}: narration", "",
              "Read-along script. Each line: where it starts in the video, (stream, seconds it "
              "has until the next shot) and the words.", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        parts, at = [], 0.0
        card = tmp / "title.mp4"
        seconds = title_card(demo, size, tmp, card, fmt.fps)
        if seconds:
            parts.append(card)
            at += seconds
        voiced = voice_scenes(demo.SCENES, voice_name, tmp, options)
        for s, scene in enumerate(demo.SCENES):
            take = demo.OUT / scene["take"]
            events = events_of(take)
            starts = {e["stream"]: e["t"] for e in events if e["kind"] == "start"}
            script.append(f"## {scene['take']}")
            for i, (shot, text) in enumerate(zip(shots(events, scene.get("speeds")),
                                                 scene["lines"])):
                clip, line_len = (voiced[(s, i)] if text else (None, 0.0))
                src = stream_file(take, shot.focus)
                if shot.focus not in starts:
                    raise SystemExit(f"{scene['take']}: shot {shot.label!r} focuses stream "
                                     f"{shot.focus!r}, which has no start event")
                pieces = fit_pieces(shot, line_len if text else None, pacing)
                raw = tmp / f"{take.name}-{i}.mp4"
                tag = None
                if shot.gap >= JUMP_TAG:
                    tag = tmp / f"tag-{take.name}-{i}.png"
                    jump_png(jump(shot.gap), max(18, int(size[0] * 0.038)), tag)
                render_pieces(src, pieces, starts[shot.focus], size, raw, fmt.fps, tag)
                part = tmp / f"{take.name}-{i}-final.mp4"
                length = finish_shot(raw, clip, line_len, part)
                if text:  # the reader's budget: from this line's start to the next shot
                    script.append(f"- **{stamp(at + LEAD)}** ({shot.focus}, "
                                  f"{length - LEAD:.1f} s) {spoken(text)}")
                at += length
                parts.append(part)
            script.append("")
        listing = tmp / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-c", "copy", str(out)], check=True)
    script[2:2] = [f"Length {stamp(at)}.", ""]
    out.with_name(out.stem + "-script.md").write_text("\n".join(script) + "\n")
    # The voice-over master: the same picture with no audio, so iMovie has nothing to mute.
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(out), "-an", "-c:v", "copy",
                    str(out.with_name(out.stem + "-picture.mp4"))], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(out), "-c:v", "libx264",
                    "-preset", "medium", "-crf", "28", "-vf", "scale=-2:960", "-c:a", "aac",
                    "-b:a", "128k", str(out.with_name(out.stem + "-preview.mp4"))], check=True)
    print(f"{out}  ({stamp(at)})")


def render_pieces(src: Path, pieces: tuple[Shot, ...], start: float, size: tuple[int, int],
                  dst: Path, fps: int, tag: Path | None = None) -> None:
    """A fitted shot, one piece at a time, joined. One piece is the common case."""
    if len(pieces) == 1:
        render_shot(src, pieces[0], start, size, dst, fps, tag)
        return
    with tempfile.TemporaryDirectory() as scratch:
        parts = [Path(scratch) / f"{i:03d}.mp4" for i in range(len(pieces))]
        for i, (piece, part) in enumerate(zip(pieces, parts)):
            render_shot(src, piece, start, size, part, fps, tag if i == 0 else None)
        listing = Path(scratch) / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-c", "copy", str(dst)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble the narrated portrait video.")
    parser.add_argument("folder")
    parser.add_argument("out", type=Path)
    parser.add_argument("voice", nargs="?")
    parser.add_argument("--fit", action="store_true",
                        help="speed a shot up toward its line (never cuts; see fit_portrait.py)")
    parser.add_argument("--pause", type=float, help=f"with --fit: seconds between lines ({PAUSE})")
    parser.add_argument("--max-speed", type=float, help=f"with --fit: the speed cap ({MAX_SPEED})")
    args = parser.parse_args()
    if not args.fit and (args.pause is not None or args.max_speed is not None):
        parser.error("--pause and --max-speed need --fit")
    fitting = Pacing(args.pause if args.pause is not None else PAUSE,
                     args.max_speed if args.max_speed is not None else MAX_SPEED) if args.fit else None
    d = load_demo(args.folder)
    main(d, args.out.expanduser(), *choose(args.voice, d), fitting)
