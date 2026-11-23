"""Shared guards for the demo-video tests: what they need from the machine.

Locally a missing browser or ffmpeg skips the tests that need it (doctor.sh says how to
install them). CI sets DEMO_VIDEO_TESTS_STRICT=1, where a missing one FAILS instead: a test
that skips in CI is a test that never runs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

STRICT = os.environ.get("DEMO_VIDEO_TESTS_STRICT") == "1"


def need(ok: bool, what: str) -> None:
    """Skip (fail, under DEMO_VIDEO_TESTS_STRICT=1) a test whose requirement is missing."""
    if ok:
        return
    if STRICT:
        pytest.fail(f"DEMO_VIDEO_TESTS_STRICT=1 and this test needs {what}")
    pytest.skip(f"needs {what}")


@pytest.fixture(scope="session")
def chromium_launches() -> None:
    """Playwright's Chromium starts on this machine (Take and the in-page tests need it)."""
    from playwright.sync_api import Error, sync_playwright
    pw = sync_playwright().start()
    try:
        pw.chromium.launch().close()
        ok, why = True, ""
    except Error as err:
        ok, why = False, str(err).splitlines()[0]
    finally:
        pw.stop()
    need(ok, f"Playwright Chromium ({why})")


@pytest.fixture
def ffmpeg() -> None:
    need(bool(shutil.which("ffmpeg")), "ffmpeg")


@pytest.fixture
def pillow() -> None:
    """Pillow draws the portrait title card (see scripts/titlecard.py)."""
    try:
        import PIL  # noqa: F401
        ok = True
    except ModuleNotFoundError:
        ok = False
    need(ok, "Pillow (run pytest with --with pillow)")


@pytest.fixture
def drawtext() -> None:
    """ffmpeg can draw text: every rendered shot needs it, and Homebrew's plain ffmpeg can't.

    Asks the same question the renderer does, through ffmpeg_path, so a machine with a
    keg-only ffmpeg-full installed runs these tests instead of skipping them.
    """
    from ffmpeg_path import ensure_drawtext
    need(ensure_drawtext(), "ffmpeg with drawtext (see doctor.sh)")
