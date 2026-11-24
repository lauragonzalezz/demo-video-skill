"""Who taps the phone: the seam between a recorded take and the thing driving the app.

`SimTake` records the screen and timestamps the clips; it never touches the UI itself. That
job goes to a driver, so the same scene can be driven three ways:

  * **`idb`** (`DRIVER = "idb"`) — fully scripted. `scenes.py` runs start to finish on its
    own, taps included, which is the most repeatable and the only way to re-record a take
    unattended. Needs `brew install idb-companion` and `pipx install fb-idb`.
  * **an agent** (`DRIVER = "manual"`, the default) — the agent taps through the app with
    whatever it already has (the Expo MCP's `automation_tap`/`automation_type`, or a person
    clicking), while `sim_recorder.py session` holds the recording open and takes `clip` and
    `clipend` on a control pipe. Nothing to install.
  * **anything else** — implement the four verbs below.

Coordinates are **points**, the units the accessibility tree reports and `idb` taps in, not
the recording's pixels: a tap at (100, 200) lands in the same place whatever the device's
scale factor is.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Protocol, runtime_checkable

SWIPES = {"up": (0.5, 0.72, 0.5, 0.28), "down": (0.5, 0.28, 0.5, 0.72),
          "left": (0.8, 0.5, 0.2, 0.5), "right": (0.2, 0.5, 0.8, 0.5)}
SWIPE_DURATION = 0.25


@runtime_checkable
class Driver(Protocol):
    """The verbs a scene can call on `t`. A driver implements these four."""

    def tap(self, x: float, y: float) -> None: ...
    def tap_text(self, text: str) -> None: ...
    def type_text(self, text: str) -> None: ...
    def swipe(self, direction: str) -> None: ...


class ManualDriver:
    """No driver: something outside this process is tapping (an agent, or a person).

    It is not an error to have no driver — it is the zero-install route — so this exists to
    fail with the right advice if a scripted scene calls a verb anyway.
    """

    name = "manual"

    def _refuse(self, verb: str) -> None:
        raise SystemExit(
            f"this take has no UI driver, so it cannot {verb} by itself.\n"
            "Either drive the app from outside and record with "
            "`sim_recorder.py session <demo-folder> <take>`,\n"
            "or set DRIVER = \"idb\" in demo.py and install it: "
            "`brew install idb-companion && pipx install fb-idb`.")

    def tap(self, x: float, y: float) -> None:
        self._refuse(f"tap ({x}, {y})")

    def tap_text(self, text: str) -> None:
        self._refuse(f"tap {text!r}")

    def type_text(self, text: str) -> None:
        self._refuse(f"type {text!r}")

    def swipe(self, direction: str) -> None:
        self._refuse(f"swipe {direction}")

    def describe(self) -> list[dict]:
        self._refuse("read the accessibility tree")
        return []


class IdbDriver:
    """fb-idb: taps, typing and swipes, by coordinate or by accessibility label."""

    name = "idb"

    def __init__(self, udid: str, screen: tuple[int, int] | None = None):
        if not shutil.which("idb"):
            raise SystemExit("DRIVER = \"idb\" but idb is not on PATH -> "
                             "brew install idb-companion && pipx install fb-idb")
        self.udid, self._screen = udid, screen

    def _idb(self, *args: str, capture: bool = False) -> str:
        done = subprocess.run(["idb", *args, "--udid", self.udid],
                              capture_output=capture, text=True)
        if done.returncode != 0:
            detail = (done.stderr or "").strip() if capture else ""
            raise RuntimeError(f"idb {' '.join(args)} failed ({done.returncode}) {detail}".strip())
        return done.stdout if capture else ""

    def describe(self) -> list[dict]:
        """The accessibility tree, as a list of elements with an AXLabel and an AXFrame."""
        raw = self._idb("ui", "describe-all", "--json", capture=True).strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:  # older idb prints one JSON object per line
            return [json.loads(line) for line in raw.splitlines() if line.strip()]
        return parsed if isinstance(parsed, list) else [parsed]

    def find(self, text: str) -> dict | None:
        """The first element whose label or title matches *text*, case-insensitively.

        Exact matches win over partial ones, so a "Save" button is not shadowed by
        "Save and close" just because that one came first in the tree.
        """
        wanted = text.casefold()
        partial = None
        for element in self.describe():
            for key in ("AXLabel", "AXValue", "title", "label"):
                value = element.get(key)
                if not isinstance(value, str):
                    continue
                if value.casefold() == wanted:
                    return element
                if partial is None and wanted in value.casefold():
                    partial = element
        return partial

    @staticmethod
    def _centre(element: dict) -> tuple[float, float]:
        # idb reports the frame twice: a `frame` dict and an `AXFrame` string like
        # "{{21, 528}, {398, 42}}". Prefer the dict; fall back to parsing the string.
        frame = element.get("frame")
        if isinstance(frame, dict):
            try:
                return (frame["x"] + frame["width"] / 2, frame["y"] + frame["height"] / 2)
            except KeyError as err:
                raise RuntimeError(f"element has no usable frame: {element}") from err
        ax = element.get("AXFrame")
        if isinstance(ax, str):
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", ax)]
            if len(nums) == 4:
                x, y, w, h = nums
                return (x + w / 2, y + h / 2)
        raise RuntimeError(f"element has no usable frame: {element}")

    def tap(self, x: float, y: float) -> None:
        self._idb("ui", "tap", str(round(x)), str(round(y)))

    def tap_text(self, text: str) -> None:
        element = self.find(text)
        if element is None:
            labels = sorted({e[k] for e in self.describe() for k in ("AXLabel", "title")
                             if isinstance(e.get(k), str) and e[k]})
            raise RuntimeError(f"nothing on screen is labelled {text!r}. On screen now: "
                               f"{', '.join(labels[:25]) or '(nothing labelled)'}")
        self.tap(*self._centre(element))

    def type_text(self, text: str) -> None:
        self._idb("ui", "text", text)

    def swipe(self, direction: str) -> None:
        if direction not in SWIPES:
            raise ValueError(f"swipe direction must be one of {', '.join(SWIPES)}")
        if not self._screen:
            raise RuntimeError("swiping needs the screen size in points (pass screen= to IdbDriver)")
        width, height = self._screen
        x0, y0, x1, y1 = SWIPES[direction]
        self._idb("ui", "swipe", str(round(x0 * width)), str(round(y0 * height)),
                  str(round(x1 * width)), str(round(y1 * height)),
                  "--duration", str(SWIPE_DURATION))


def driver_for(name: str, udid: str, screen: tuple[int, int] | None = None) -> Driver:
    if name in ("manual", "", None):
        return ManualDriver()
    if name == "idb":
        return IdbDriver(udid, screen)
    raise SystemExit(f"demo.py DRIVER must be \"manual\" or \"idb\", not {name!r}")
