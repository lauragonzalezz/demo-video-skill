"""Find an ffmpeg that can draw text, so the desktop renderer works without shell setup.

The desktop compositor draws the menu bar, every window's title and the title card with
ffmpeg's `drawtext` filter, which needs ffmpeg to have been built against freetype.
Homebrew's plain `ffmpeg` formula is not: it has no freetype, fontconfig or harfbuzz, so
`drawtext` simply is not in the binary.

The usual fix is `brew install ffmpeg-full`, which *is* built with freetype — but it is
**keg-only**, meaning Homebrew installs it without linking it into `/opt/homebrew/bin`. So
installing it changes nothing on its own: the `ffmpeg` on PATH is still the one that cannot
draw text, and the renderer dies on its first filter with a bare CalledProcessError.

Rather than ask everyone to edit their shell profile, the three functions that actually use
`drawtext` call `ensure_drawtext()` first. It looks at the `ffmpeg` it would get, and only
if that one can't draw text does it put a keg-only build in front of it, for this process
only. A machine whose `ffmpeg` already has `drawtext` is left completely alone.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

# Keg-only Homebrew builds that are compiled with freetype, newest first.
CANDIDATES = ("ffmpeg-full",)
BREW_PREFIXES = ("/opt/homebrew/opt", "/usr/local/opt")  # Apple silicon, then Intel
ADVICE = ("ffmpeg here has no drawtext filter, which the desktop renderer needs for the "
          "menu bar, window titles and the title card.\n"
          "Fix it with:  brew install ffmpeg-full\n"
          "(it is keg-only, so nothing else on your Mac changes; this skill finds it itself)")


def has_drawtext(ffmpeg: str = "ffmpeg") -> bool:
    """Whether *ffmpeg* was built with the drawtext filter."""
    if not (shutil.which(ffmpeg) or Path(ffmpeg).is_file()):
        return False
    try:
        listed = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True,
                                text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(line.split()[1:2] == ["drawtext"] for line in listed.splitlines() if line.strip())


def _keg_only_with_drawtext() -> str | None:
    for prefix in BREW_PREFIXES:
        for name in CANDIDATES:
            candidate = Path(prefix) / name / "bin" / "ffmpeg"
            if candidate.is_file() and has_drawtext(str(candidate)):
                return str(candidate.parent)
    return None


@lru_cache(maxsize=1)
def ensure_drawtext() -> bool:
    """Make `ffmpeg` on PATH one that can draw text, for this process. True if it now can.

    Cached: the probe runs once per process, not once per rendered shot.
    """
    if has_drawtext():
        return True
    found = _keg_only_with_drawtext()
    if found is None:
        return False
    os.environ["PATH"] = f"{found}{os.pathsep}{os.environ.get('PATH', '')}"
    print(f"using {found}/ffmpeg for drawtext", flush=True)
    return True


def require_drawtext() -> None:
    """Fail with the fix rather than with ffmpeg's exit status 8 deep inside a filter."""
    if not ensure_drawtext():
        raise SystemExit(ADVICE)
