"""The canvas presets: that landscape still means exactly what it meant before layout.py
existed, and that a portrait canvas follows its footage instead of a hardcoded size."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import layout  # noqa: E402

IPHONE_17_PRO_MAX = (1320, 2868)  # what simctl recordVideo actually writes for that device


def test_landscape_is_byte_for_byte_the_desktop_renderer_it_replaced():
    """These numbers were constants in cut.py. If this fails, her web output moved."""
    assert (layout.LANDSCAPE.width, layout.LANDSCAPE.height, layout.LANDSCAPE.fps) == (1920, 1080, 30)
    assert (layout.BAR, layout.TITLE) == (30, 30)
    assert layout.FRONT == (176, 76, 1568)
    assert layout.SLOTS == [(28, 44, 760), (1132, 44, 760), (28, 600, 760), (1132, 600, 760)]


def test_cut_still_exposes_those_constants():
    """cut.py imports them now; anything reading cut.W must keep working."""
    import cut
    assert (cut.W, cut.H, cut.FPS) == (1920, 1080, 30)
    assert cut.FRONT == layout.FRONT and cut.SLOTS == layout.SLOTS


def test_a_portrait_canvas_keeps_the_phone_s_own_aspect():
    """The bug this avoids: the desktop renderer forces 16:9, which flattens a tall phone."""
    width, height = layout.canvas_for(layout.PORTRAIT, *IPHONE_17_PRO_MAX)
    source = IPHONE_17_PRO_MAX[0] / IPHONE_17_PRO_MAX[1]
    assert abs(width / height - source) < 0.005, f"{width}x{height} is not the phone's shape"
    assert height == 1920, "the long edge should come down to the cap"


@pytest.mark.parametrize("size", [IPHONE_17_PRO_MAX, (1179, 2556), (750, 1334), (2778, 1284)])
def test_every_canvas_has_even_sides(size):
    """h264 refuses an odd dimension, and the failure is a wall of ffmpeg noise."""
    for name in layout.FORMATS:
        width, height = layout.canvas_for(layout.layout(name), *size)
        assert width % 2 == 0 and height % 2 == 0, f"{name} gave {width}x{height}"


def test_small_footage_is_never_blown_up():
    assert layout.canvas_for(layout.PORTRAIT, 640, 1200) == (640, 1200)


def test_a_fixed_target_keeps_its_own_size_whatever_the_footage():
    assert layout.canvas_for(layout.REELS, *IPHONE_17_PRO_MAX) == (1080, 1920)
    assert layout.canvas_for(layout.SQUARE, 640, 1200) == (1080, 1080)


def test_an_unknown_format_names_the_ones_that_exist():
    with pytest.raises(SystemExit, match="portrait"):
        layout.layout("vertical")


def test_footage_with_no_size_is_refused_rather_than_divided_by_zero():
    with pytest.raises(ValueError, match="no size"):
        layout.canvas_for(layout.PORTRAIT, 0, 0)
