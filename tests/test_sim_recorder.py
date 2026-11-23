"""The simulator recorder's logic that can be checked without a device: which simulator a
demo means, and the rebuild that makes a sparse capture seekable."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sim_recorder  # noqa: E402

FLEET = [
    {"name": "iPhone 17 Pro Max", "udid": "AAA", "state": "Shutdown", "runtime": "iOS 26 0"},
    {"name": "iPhone 17 Pro Max", "udid": "BBB", "state": "Shutdown", "runtime": "iOS 27 0"},
    {"name": "iPad mini", "udid": "CCC", "state": "Shutdown", "runtime": "iOS 27 0"},
]


@pytest.fixture
def fleet(monkeypatch):
    def set_state(udid: str | None) -> None:
        monkeypatch.setattr(sim_recorder, "devices", lambda: [
            {**d, "state": "Booted" if d["udid"] == udid else "Shutdown"} for d in FLEET])
    set_state(None)
    return set_state


def test_no_device_named_means_the_booted_one(fleet):
    fleet("CCC")
    assert sim_recorder.resolve_device(None) == "CCC"
    assert sim_recorder.resolve_device("booted") == "CCC"


def test_nothing_booted_says_how_to_boot_one(fleet):
    with pytest.raises(SystemExit, match="simctl boot"):
        sim_recorder.resolve_device(None)


def test_a_name_that_matches_two_runtimes_takes_the_newer(fleet):
    assert sim_recorder.resolve_device("iPhone 17 Pro Max") == "BBB"


def test_a_name_prefers_the_booted_one_over_a_newer_runtime(fleet):
    fleet("AAA")
    assert sim_recorder.resolve_device("iPhone 17 Pro Max") == "AAA"


def test_a_udid_is_taken_as_given(fleet):
    assert sim_recorder.resolve_device("CCC") == "CCC"


def test_an_unknown_name_lists_what_there_is(fleet):
    with pytest.raises(SystemExit, match="iPad mini"):
        sim_recorder.resolve_device("iPhone 4")


def _sparse(path: Path, seconds: float, ffmpeg) -> None:
    """A still clip: one frame's worth, like a simulator recording of an app that didn't move."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=red:s=320x640:d={seconds}", "-frames:v", "1", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


def test_a_still_capture_is_rebuilt_to_the_take_s_full_length(tmp_path, ffmpeg):
    """simctl writes a frame only when the screen changes, so a still app records almost
    nothing: a clip four seconds in would have no picture to seek to."""
    src, dst = tmp_path / "phone.src.mov", tmp_path / "phone.mp4"
    _sparse(src, 0.04, ffmpeg)
    assert sim_recorder.duration(src) < 1.0, "the fixture should be the short capture"

    sim_recorder.normalise(src, dst, length=9.0)

    assert abs(sim_recorder.duration(dst) - 9.0) < 0.2
    # ...and the far end is now seekable, which is the whole point.
    late = tmp_path / "late.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "7.5", "-i", str(dst),
                    "-frames:v", "1", str(late)], check=True)
    assert late.stat().st_size > 0


def test_the_rebuild_refuses_to_claim_a_length_it_did_not_reach(tmp_path, ffmpeg, monkeypatch):
    """A video that came out short would put every later shot on the wrong picture, silently.
    Better to fail the take than to hand the renderer a timeline that does not line up."""
    src, dst = tmp_path / "a.mov", tmp_path / "b.mp4"
    _sparse(src, 0.04, ffmpeg)
    monkeypatch.setattr(sim_recorder, "duration", lambda path: 1.0)  # as if the pad had failed

    with pytest.raises(RuntimeError, match=r"normalised to 1\.00s, expected 9\.00s"):
        sim_recorder.normalise(src, dst, length=9.0)


def test_a_take_must_say_which_stream_when_a_demo_has_several(monkeypatch, tmp_path):
    monkeypatch.setattr(sim_recorder, "resolve_device", lambda wanted: "AAA")
    demo = SimpleNamespace(OUT=tmp_path, STREAMS={"phone": {}, "watch": {}}, DRIVER="manual")
    with pytest.raises(SystemExit, match="records one stream"):
        sim_recorder.SimTake("s1", demo)


def test_a_take_refuses_a_stream_the_demo_never_declared(monkeypatch, tmp_path):
    monkeypatch.setattr(sim_recorder, "resolve_device", lambda wanted: "AAA")
    demo = SimpleNamespace(OUT=tmp_path, STREAMS={"phone": {}}, DRIVER="manual")
    with pytest.raises(SystemExit, match="no stream 'tablet'"):
        sim_recorder.SimTake("s1", demo, "tablet")


def test_events_are_the_same_three_kinds_the_cut_reads(monkeypatch, tmp_path):
    """The whole contract with cut.py and assemble_portrait.py is this log's shape."""
    monkeypatch.setattr(sim_recorder, "resolve_device", lambda wanted: "AAA")
    demo = SimpleNamespace(OUT=tmp_path, STREAMS={"phone": {}}, DRIVER="manual")
    take = sim_recorder.SimTake("s1", demo)
    take.dir.mkdir(parents=True)
    take._log = open(take.dir / "events.jsonl", "w")
    take.event("start", stream="phone")
    with take.clip("a shot", "phone"):
        pass
    take._log.close()

    rows = [json.loads(line) for line in (take.dir / "events.jsonl").read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["start", "clip", "clipend"]
    assert rows[0]["stream"] == "phone" and rows[1]["focus"] == "phone"
    assert all(isinstance(r["t"], float) for r in rows)
    import cut
    assert [s.label for s in cut.shots(rows)] == ["a shot"], "cut.py must read these back"


def test_a_clip_cannot_focus_another_stream(monkeypatch, tmp_path):
    monkeypatch.setattr(sim_recorder, "resolve_device", lambda wanted: "AAA")
    demo = SimpleNamespace(OUT=tmp_path, STREAMS={"phone": {}}, DRIVER="manual")
    take = sim_recorder.SimTake("s1", demo)
    take.dir.mkdir(parents=True)
    take._log = open(take.dir / "events.jsonl", "w")
    with pytest.raises(ValueError, match="not this take's stream"):
        with take.clip("a shot", "laptop"):
            pass
    take._log.close()
