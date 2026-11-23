"""Measure the dead air in a phone demo: how long each shot plays on after its line stops.

    python fit_portrait.py <demo-folder> [voice] [--pause S] [--max-speed X]

The same question `fit.py` answers for the desktop path, asked of a single phone stream. It
voices the lines (cached, so this is the audio `assemble_portrait.py` will use, and an
ElevenLabs voice bills only lines it has not voiced before) and changes no footage and no
words.

It differs from `fit.py` in one way, for one reason. `fit.py` reports how much dead air
`--fit` could *cut*, which it finds by scanning the front window for stretches where only
something cursor-sized moved. That test is built around a mouse pointer drifting on a web
page; a phone has no pointer, so on this footage it would be guessing. So the phone path
only ever speeds a shot up, and this report says what that leaves for the line to fill.

The fix for a shot that is too long is usually not here anyway: the gaps between clips cost
the viewer nothing, so shorten the hold inside the clip and re-record the take, or give the
line more words.
"""
from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import retime
from assemble import check, voice_scenes
from assemble_portrait import fit_pieces
from cut import Shot, events_of, shots
from demos import load_demo
from fit import words_to_add
from retime import MAX_SPEED, PAUSE, Pacing, target_for
from tts import choose, spoken


@dataclass(frozen=True)
class Row:
    take: str
    index: int
    shot: Shot
    line: str | None
    speech: float | None
    played: float  # seconds the picture runs after fitting
    target: float  # seconds it should run: the speech plus the pause


def pace(rows: list[Row]) -> float:
    """This voice's words a second, measured from its own lines."""
    spoken_rows = [r for r in rows if r.speech]
    seconds = sum(r.speech for r in spoken_rows)
    return sum(len(spoken(r.line).split()) for r in spoken_rows) / seconds if seconds else 0.0


def _row_text(row: Row, words_per_second: float) -> str:
    speech = f"{row.speech:5.1f}" if row.speech else "    -"
    dead = row.played - row.target
    head = (f"{row.take} #{row.index}  footage {row.shot.length:5.1f}  speech {speech}  "
            f"dead {max(dead, 0):5.1f}")
    if dead <= retime.SLOP:
        return f"{head}  ok"
    speed = row.shot.length / row.played if row.played else 1.0
    action = f"x{speed:.2f}" if speed > 1.01 else "no speed-up left"
    if row.speech:
        action += f", {dead:.1f} s left: add about {words_to_add(dead, words_per_second)} words"
        action += " or shorten the hold and re-record"
    else:
        action += f", {dead:.1f} s over the silent hold"
    return f"{head}  {action}"


def report(rows: list[Row]) -> str:
    words_per_second = pace(rows)
    before = sum(r.shot.length for r in rows)
    after = sum(max(r.played, retime.LEAD + r.speech + retime.TAIL if r.speech else 0.0)
                for r in rows)
    worst = max((r.played - r.target for r in rows), default=0.0)
    return "\n".join([*(_row_text(r, words_per_second) for r in rows), "",
                      f"This voice reads {words_per_second:.1f} words a second.",
                      f"Footage {before:.1f} s, fitted {after:.1f} s. "
                      f"Most dead air in one shot: {max(worst, 0):.1f} s."])


def measure(demo: ModuleType, voice: str, options: dict, pacing: Pacing, tmp: Path) -> list[Row]:
    check(demo)
    voiced = voice_scenes(demo.SCENES, voice, tmp, options)
    rows = []
    for s, scene in enumerate(demo.SCENES):
        events = events_of(demo.OUT / scene["take"])
        for i, (shot, line) in enumerate(zip(shots(events, scene.get("speeds")), scene["lines"])):
            speech = voiced[(s, i)][1] if line else None
            played = sum(p.length for p in fit_pieces(shot, speech, pacing))
            rows.append(Row(scene["take"], i, shot, line, speech, played,
                            target_for(speech, pacing.pause)))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure each shot's dead air. Voices uncached lines, which an ElevenLabs voice bills.")
    parser.add_argument("folder")
    parser.add_argument("voice", nargs="?")
    parser.add_argument("--pause", type=float, default=PAUSE)
    parser.add_argument("--max-speed", type=float, default=MAX_SPEED)
    args = parser.parse_args()
    d = load_demo(args.folder)
    chosen, chosen_options = choose(args.voice, d)
    with tempfile.TemporaryDirectory() as scratch:
        print(report(measure(d, chosen, chosen_options,
                             Pacing(args.pause, args.max_speed), Path(scratch))))
