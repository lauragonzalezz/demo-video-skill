"""Canvas presets: the output size as a parameter instead of a constant.

Alaina's renderer hardcoded 1920x1080 because it draws a *fake macOS desktop* — a menu bar,
a wallpaper and fixed window slots — and a desktop is landscape. A phone screen is not, so
the canvas has to be a setting. A demo picks one with `FORMAT` in its `demo.py`.

Two things get conflated easily, so they are separate here:

  * **the canvas** — what this module decides: the output's pixel size;
  * **the content's own shape** — a browser window is landscape, a phone screen is tall.

One renderer cannot serve both well, so each backend keeps its own (`cut.py`/`assemble.py`
draw the desktop; `assemble_portrait.py` renders a single full-bleed phone stream) and the
preset only chooses the canvas they draw onto.

`landscape` holds exactly the numbers `cut.py` used before this module existed, and is still
the default for the web path, so its output is unchanged.

  landscape  1920x1080, the desktop compositor
  portrait   the footage's own aspect, long edge capped at 1920: a phone fills the frame
  reels      1080x1920, a fixed 9:16 target; footage that doesn't match is padded
  square     1080x1080, likewise
"""
from __future__ import annotations

from dataclasses import dataclass

FPS = 30
BLEED, PAD = "bleed", "pad"


@dataclass(frozen=True)
class Format:
    """A canvas. *width*/*height* are None when the footage decides (see `canvas_for`)."""
    name: str
    width: int | None
    height: int | None
    fit: str  # BLEED: the canvas takes the footage's aspect. PAD: fixed canvas, bars if needed.
    long_edge: int  # BLEED only: the longest side is scaled down to at most this
    fps: int = FPS
    title_seconds: float = 3.0
    # Title-card type, as a fraction of the canvas's short side: a phone's 1080 wide frame and
    # a 1920 wide desktop then get type that reads the same size on screen.
    title_font_frac: float = 0.085

    @property
    def portrait(self) -> bool:
        return self.fit == BLEED or (self.height or 0) > (self.width or 0)


LANDSCAPE = Format("landscape", 1920, 1080, PAD, long_edge=1920, title_font_frac=64 / 1080)
PORTRAIT = Format("portrait", None, None, BLEED, long_edge=1920)
REELS = Format("reels", 1080, 1920, PAD, long_edge=1920)
SQUARE = Format("square", 1080, 1080, PAD, long_edge=1080)
FORMATS = {f.name: f for f in (LANDSCAPE, PORTRAIT, REELS, SQUARE)}

# The desktop compositor's own geometry: only cut.py reads these, and only for `landscape`.
BAR = 30  # menu bar height
TITLE = 30  # window title bar height
# The front window, and the background slots in stream order (x, y, width): 16:9 content
# plus a title bar. Four slots: a demo has at most four streams.
FRONT = (176, 76, 1568)
SLOTS = [(28, 44, 760), (1132, 44, 760), (28, 600, 760), (1132, 600, 760)]


def layout(name: str) -> Format:
    if name not in FORMATS:
        raise SystemExit(f"demo.py FORMAT must be one of {', '.join(FORMATS)}, not {name!r}")
    return FORMATS[name]


def even(value: float) -> int:
    """h264 needs both dimensions even; rounding down never upscales."""
    return max(2, int(value) // 2 * 2)


def canvas_for(fmt: Format, src_width: int, src_height: int) -> tuple[int, int]:
    """The output size for footage measured at *src_width* x *src_height*.

    A PAD format answers with its own fixed canvas. A BLEED format answers with the
    footage's own aspect, scaled down so its longest side is at most `long_edge` — so a
    1320x2868 iPhone recording fills the frame with no bars, and is never upscaled.
    """
    if src_width <= 0 or src_height <= 0:
        raise ValueError(f"footage has no size: {src_width}x{src_height}")
    if fmt.fit == PAD:
        assert fmt.width and fmt.height
        return fmt.width, fmt.height
    scale = min(1.0, fmt.long_edge / max(src_width, src_height))
    return even(src_width * scale), even(src_height * scale)
