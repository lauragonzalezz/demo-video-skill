"""Load a demo folder's `demo.py`, and read the settings that pick a backend and a canvas.

A demo folder holds a `demo.py` (its streams, title and narration) and the scene scripts
that record it. This module is deliberately free of Playwright and of ffmpeg, so the
simulator path can load a demo without installing the web path's dependencies.

`demo.py` settings this module reads, all optional:

    BACKEND = "simulator"   # or "playwright" (the default: Alaina's web/terminal recorder)
    FORMAT  = "portrait"    # or "landscape" (the default), "reels", "square" — see layout.py

`BACKEND` picks what records; `FORMAT` picks the canvas it is rendered onto. A simulator
demo defaults to `portrait`, a Playwright demo to `landscape`, so neither has to say so.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PLAYWRIGHT, SIMULATOR = "playwright", "simulator"
BACKENDS = (PLAYWRIGHT, SIMULATOR)
# Each backend's canvas when the demo names none: a phone is portrait, a desktop is not.
DEFAULT_FORMAT = {PLAYWRIGHT: "landscape", SIMULATOR: "portrait"}


def load_demo(anchor: str | Path) -> ModuleType:
    """Import the `demo.py` next to *anchor* (a scene file's __file__, or the demo folder).

    `OUT` is expanded and, when relative, resolved against the demo folder: a demo that
    writes to `exports/<name>` lands in the same place however it was started.
    """
    path = Path(anchor).resolve()
    folder = path if path.is_dir() else path.parent
    path = folder / "demo.py"
    if str(folder) not in sys.path:  # demo.py may import its own helpers
        sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location("demo", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"no demo.py at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = Path(module.OUT).expanduser()
    module.OUT = out if out.is_absolute() else (folder / out).resolve()
    module.FOLDER = folder
    return module


def backend_of(demo: ModuleType) -> str:
    backend = getattr(demo, "BACKEND", PLAYWRIGHT)
    if backend not in BACKENDS:
        raise SystemExit(f"demo.py BACKEND must be one of {', '.join(BACKENDS)}, not {backend!r}")
    return backend


def format_of(demo: ModuleType) -> str:
    """The demo's canvas preset, defaulting to the one its backend records for."""
    return getattr(demo, "FORMAT", None) or DEFAULT_FORMAT[backend_of(demo)]
