"""The portrait renderer: that it finds its footage, measures rather than assumes, and
above all never stretches the picture."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import assemble_portrait as ap  # noqa: E402
import layout  # noqa: E402
from cut import Shot  # noqa: E402
from retime import Pacing  # noqa: E402

PHONE = (330, 716)  # an iPhone 17 Pro Max's shape, small enough to render in a test


def _clip(path: Path, size=PHONE, seconds: float = 8.0) -> Path:
    """A moving portrait clip, so a frame pulled from it says where in the clip it came from."""
    width, height = size
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc=size={width}x{height}:rate=30:duration={seconds}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def _probe(path: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    stream = json.loads(out)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def test_the_stream_file_may_be_mp4_mov_or_webm(tmp_path):
    take = tmp_path / "s1"
    take.mkdir()
    with pytest.raises(SystemExit, match="no video for stream"):
        ap.stream_file(take, "phone")
    (take / "phone.webm").write_bytes(b"x")
    assert ap.stream_file(take, "phone").name == "phone.webm"
    (take / "phone.mp4").write_bytes(b"x")
    assert ap.stream_file(take, "phone").name == "phone.mp4", "mp4 wins: it is the normalised one"


def test_the_footage_is_measured_not_assumed(tmp_path, ffmpeg):
    assert ap.probe_size(_clip(tmp_path / "p.mp4")) == PHONE


def test_a_rendered_shot_keeps_the_phone_s_proportions(tmp_path, ffmpeg):
    """The bug this guards: the desktop renderer scales every window to 16:9, which squashes
    a tall phone into a letterbox. Here the shape of the picture must survive."""
    src = _clip(tmp_path / "phone.mp4")
    size = layout.canvas_for(layout.PORTRAIT, *PHONE)
    out = tmp_path / "shot.mp4"

    ap.render_shot(src, Shot("a", "phone", 2.0, 5.0, 0.0), 0.0, size, out, fps=30)

    assert _probe(out) == size
    assert abs(size[0] / size[1] - PHONE[0] / PHONE[1]) < 0.01, "the canvas changed shape"
    assert abs(ap.duration(out) - 3.0) < 0.2


def test_a_shot_is_capped_at_its_clip_even_when_the_footage_runs_long(tmp_path, ffmpeg):
    """An 8 s source behind a 2 s clip must render 2 s: a filter graph outrunning its input
    is how a 5 s shot once rendered for minutes in the landscape renderer."""
    src = _clip(tmp_path / "phone.mp4", seconds=8.0)
    out = tmp_path / "shot.mp4"
    ap.render_shot(src, Shot("a", "phone", 1.0, 3.0, 0.0), 0.0, layout.canvas_for(layout.PORTRAIT, *PHONE),
                   out, fps=30)
    assert abs(ap.duration(out) - 2.0) < 0.2


def test_a_shot_honours_the_author_s_speed(tmp_path, ffmpeg):
    src = _clip(tmp_path / "phone.mp4")
    out = tmp_path / "shot.mp4"
    ap.render_shot(src, Shot("a", "phone", 1.0, 4.0, 0.0, speed=2.0), 0.0,
                   layout.canvas_for(layout.PORTRAIT, *PHONE), out, fps=30)
    assert abs(ap.duration(out) - 1.5) < 0.2, "3 s of footage at 2x is 1.5 s"


def test_footage_that_does_not_match_a_fixed_canvas_is_padded_not_stretched(tmp_path, ffmpeg):
    """A square target with portrait footage: bars are a choice, distortion is a bug."""
    src = _clip(tmp_path / "phone.mp4")
    out = tmp_path / "shot.mp4"
    ap.render_shot(src, Shot("a", "phone", 1.0, 3.0, 0.0), 0.0,
                   layout.canvas_for(layout.SQUARE, *PHONE), out, fps=30)
    assert _probe(out) == (1080, 1080)


def test_without_fit_a_shot_plays_exactly_as_recorded():
    shot = Shot("a", "phone", 0.0, 9.0, 0.0)
    assert ap.fit_pieces(shot, speech=2.0, pacing=None) == (shot,)


def test_fit_speeds_a_long_shot_up_toward_its_line():
    shot = Shot("a", "phone", 0.0, 9.0, 0.0)
    pieces = ap.fit_pieces(shot, speech=2.0, pacing=Pacing())
    assert len(pieces) == 1, "the phone path never cuts, so a shot stays in one piece"
    assert pieces[0].speed > 1.0 and pieces[0].speed <= 1.5


def test_fit_never_cuts_footage_out_of_the_middle():
    """retime's still-detection is tuned for a mouse pointer; on phone footage it would be
    guessing, so the phone path only ever speeds up. The spans must stay whole."""
    shot = Shot("a", "phone", 4.0, 40.0, 0.0)
    for piece in ap.fit_pieces(shot, speech=1.0, pacing=Pacing()):
        assert (piece.t0, piece.t1) == (4.0, 40.0)


def test_fit_leaves_a_shot_that_already_fits_alone():
    shot = Shot("a", "phone", 0.0, 3.0, 0.0)
    assert ap.fit_pieces(shot, speech=2.0, pacing=Pacing())[0].speed == 1.0


def _demo(tmp_path: Path, title: str) -> SimpleNamespace:
    return SimpleNamespace(TITLE=title, OUT=tmp_path, STREAMS={"phone": {"title": "iPhone"}},
                           SCENES=[{"take": "s1", "lines": ["one"]}])


def test_an_empty_title_skips_the_card_entirely(tmp_path, ffmpeg, pillow):
    assert ap.title_card(_demo(tmp_path, ""), (330, 716), tmp_path, tmp_path / "t.mp4", 30) == 0.0
    assert not (tmp_path / "t.mp4").exists()


def test_a_title_card_may_contain_what_ffmpeg_s_drawtext_forbids(tmp_path, ffmpeg, pillow):
    """drawtext reads : ' \\ and % as syntax, so the desktop renderer refuses them in a title.
    Pillow draws the glyphs, so this one renders."""
    demo = _demo(tmp_path, "Shipping: 100% done, and it's fast")
    out = tmp_path / "t.mp4"
    seconds = ap.title_card(demo, (330, 716), tmp_path, out, 30)
    assert seconds > 0 and _probe(out) == (330, 716)
