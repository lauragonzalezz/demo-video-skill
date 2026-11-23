"""Finding an ffmpeg that can draw text, without asking anyone to edit their shell profile."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ffmpeg_path  # noqa: E402


@pytest.fixture(autouse=True)
def fresh():
    """The answer is cached per process; each test asks it afresh."""
    ffmpeg_path.ensure_drawtext.cache_clear()
    yield
    ffmpeg_path.ensure_drawtext.cache_clear()


def test_a_missing_binary_simply_has_no_drawtext():
    assert ffmpeg_path.has_drawtext("/nonexistent/ffmpeg") is False


def test_an_ffmpeg_that_already_draws_text_is_left_completely_alone(monkeypatch):
    """No PATH surgery on a machine that doesn't need it."""
    monkeypatch.setattr(ffmpeg_path, "has_drawtext", lambda ffmpeg="ffmpeg": True)
    before = ffmpeg_path.os.environ["PATH"]
    assert ffmpeg_path.ensure_drawtext() is True
    assert ffmpeg_path.os.environ["PATH"] == before


def test_a_keg_only_build_is_put_in_front_when_the_default_cannot(monkeypatch, tmp_path):
    """ffmpeg-full is installed unlinked, so finding it is the whole job."""
    keg = tmp_path / "ffmpeg-full" / "bin"
    keg.mkdir(parents=True)
    (keg / "ffmpeg").write_text("#!/bin/sh\n")
    (keg / "ffmpeg").chmod(0o755)
    monkeypatch.setattr(ffmpeg_path, "BREW_PREFIXES", (str(tmp_path),))
    monkeypatch.setattr(ffmpeg_path, "has_drawtext",
                        lambda ffmpeg="ffmpeg": ffmpeg != "ffmpeg")  # only the keg one can
    monkeypatch.setenv("PATH", "/usr/bin")

    assert ffmpeg_path.ensure_drawtext() is True
    assert ffmpeg_path.os.environ["PATH"].startswith(str(keg))


def test_nothing_found_means_nothing_claimed(monkeypatch):
    monkeypatch.setattr(ffmpeg_path, "BREW_PREFIXES", ("/nonexistent",))
    monkeypatch.setattr(ffmpeg_path, "has_drawtext", lambda ffmpeg="ffmpeg": False)
    assert ffmpeg_path.ensure_drawtext() is False


def test_the_failure_tells_you_the_fix_instead_of_an_ffmpeg_exit_code(monkeypatch):
    """Without this the first symptom is CalledProcessError ... exit status 8."""
    monkeypatch.setattr(ffmpeg_path, "BREW_PREFIXES", ("/nonexistent",))
    monkeypatch.setattr(ffmpeg_path, "has_drawtext", lambda ffmpeg="ffmpeg": False)
    with pytest.raises(SystemExit, match="brew install ffmpeg-full"):
        ffmpeg_path.require_drawtext()
