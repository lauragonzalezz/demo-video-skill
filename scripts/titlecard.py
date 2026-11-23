"""Draw a title card as a PNG, with Pillow rather than ffmpeg's drawtext.

Alaina's title card is an ffmpeg `drawtext` filter, which means two things we'd rather not
inherit on the phone path: Homebrew's plain ffmpeg is built without freetype, so drawtext
needs a source build of ffmpeg-full; and a title has to dodge `: ' \\ %`, which ffmpeg's
filter syntax reads as punctuation. Drawing the card here instead costs one pure-Python
dependency, wraps long titles, and lets a title say anything.

Pillow is imported inside the drawing call: a demo with an empty TITLE skips the card, and
should not need Pillow installed to render.

    uv run -q --no-project --with pillow python assemble_portrait.py ...
"""
from __future__ import annotations

from pathlib import Path

# San Francisco first (it is what iOS draws, so a phone demo's card matches its footage),
# then Helvetica, then the Arial that Alaina's renderer uses.
BOLD_FONTS = ("/System/Library/Fonts/SFNS.ttf",
              "/System/Library/Fonts/HelveticaNeue.ttc",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
TOP, BOTTOM = (0x0F, 0x1A, 0x33), (0x2A, 0x17, 0x45)  # the wallpaper gradient, so the family reads
TEXT = (0xFF, 0xFF, 0xFF)
SUBTEXT = (0xFF, 0xFF, 0xFF, 0xB0)
SIDE_MARGIN = 0.10  # of the width, each side: the text column is the middle 80%
SUBTITLE_FRAC = 0.42  # the subtitle's size, against the title's
LINE_SPACING = 1.22


def _font(size: int):
    from PIL import ImageFont
    for path in BOLD_FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(draw, text: str, font, room: int) -> list[str]:
    """*text* broken into lines that each fit *room* pixels. A single word that doesn't fit
    is left long rather than hyphenated: the caller shrinks the type instead."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and draw.textlength(trial, font=font) > room:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _gradient(width: int, height: int):
    """A vertical gradient, drawn a row at a time: the card's background."""
    from PIL import Image
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        fraction = y / max(height - 1, 1)
        row = tuple(round(a + (b - a) * fraction) for a, b in zip(TOP, BOTTOM))
        for x in range(width):
            pixels[x, y] = row
    return image


def title_png(text: str, width: int, height: int, dst: Path, subtitle: str | None = None,
              font_px: int | None = None) -> Path:
    """Write a *width* x *height* title card for *text* to *dst*.

    The type starts at *font_px* (default: a twelfth of the short side) and shrinks until the
    wrapped title fits the middle 80% of the card, so a long title stays on the card instead
    of running off it.
    """
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as err:
        raise SystemExit("the title card needs Pillow: run this with "
                         "`uv run --no-project --with pillow python ...`, or set TITLE = \"\" "
                         "in demo.py to skip the card") from err
    image = _gradient(width, height)
    draw = ImageDraw.Draw(image, "RGBA")
    room = int(width * (1 - 2 * SIDE_MARGIN))
    size = font_px or max(16, min(width, height) // 12)
    while size > 12:
        font = _font(size)
        lines = _wrap(draw, text, font, room)
        line_height = size * LINE_SPACING
        widest = max((draw.textlength(line, font=font) for line in lines), default=0)
        if widest <= room and line_height * len(lines) <= height * 0.55:
            break
        size = int(size * 0.92)
    sub_font = _font(max(12, int(size * SUBTITLE_FRAC)))
    sub_lines = _wrap(draw, subtitle, sub_font, room) if subtitle else []
    sub_height = len(sub_lines) * int(size * SUBTITLE_FRAC) * LINE_SPACING
    gap = size * 0.7 if sub_lines else 0.0
    block = len(lines) * line_height + gap + sub_height
    y = (height - block) / 2
    for line in lines:
        draw.text(((width - draw.textlength(line, font=font)) / 2, y), line, font=font, fill=TEXT)
        y += line_height
    y += gap
    for line in sub_lines:
        draw.text(((width - draw.textlength(line, font=sub_font)) / 2, y), line,
                  font=sub_font, fill=SUBTEXT)
        y += int(size * SUBTITLE_FRAC) * LINE_SPACING
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst)
    return dst


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 5:
        raise SystemExit("usage: titlecard.py <text> <width> <height> <out.png> [subtitle]")
    print(title_png(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]),
                    sys.argv[5] if len(sys.argv) > 5 else None))


BADGE = (0x1C, 0x7E, 0xD6, 0xD9)  # the same blue Alaina's "+40 s" tag uses
BADGE_PAD = 0.45  # of the type size, around the text


def jump_png(text: str, font_px: int, dst: Path) -> tuple[int, int]:
    """A small rounded badge reading *text* ("+40 s"), for the corner of a shot that follows
    a cut wait. Returns its size, which the caller needs to place it."""
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as err:
        raise SystemExit("the cut-wait tag needs Pillow: run with `--with pillow`") from err
    font = _font(font_px)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    pad = int(font_px * BADGE_PAD)
    width = int(probe.textlength(text, font=font)) + 2 * pad
    height = int(font_px * 1.42) + 2 * pad
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=int(height * 0.28), fill=BADGE)
    draw.text((pad, pad), text, font=font, fill=TEXT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst)
    return width, height
