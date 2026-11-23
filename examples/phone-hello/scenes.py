"""Record the phone-hello take.

    uv run -q --no-project python scenes.py

No UI driver: this scene changes the screen with simctl alone, so it runs on a fresh
checkout with nothing installed beyond Xcode. A scene that taps needs DRIVER = "idb" in
demo.py, or the agent-driven route (`sim_recorder.py session`). See ../../SKILL.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# The skill's scripts/: set DEMO_VIDEO_SCRIPTS when this folder is copied elsewhere.
sys.path.insert(0, os.environ.get("DEMO_VIDEO_SCRIPTS",
                                  str(Path(__file__).resolve().parents[2] / "scripts")))
from demos import load_demo  # noqa: E402
from sim_recorder import SimTake  # noqa: E402

DEMO = load_demo(__file__)


def s1() -> None:
    with SimTake("s1-settings", DEMO) as t:
        t.appearance("light")  # before the first clip: start from a known screen
        t.wait(1.5)
        with t.clip("settings in the light", "phone"):
            t.wait(3.2)  # a reading hold; a still phone records fine, its frame is held
        t.appearance("dark")  # off camera, between clips: the switch itself is cut
        t.wait(2.0)
        with t.clip("the same screen in the dark", "phone"):
            t.wait(3.2)


SCENES = {"s1": s1}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(SCENES):
        SCENES[name]()
