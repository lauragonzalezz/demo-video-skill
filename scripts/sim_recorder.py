"""Record a demo take from a booted iOS simulator, on the same clock contract as the web path.

A simulator take writes exactly what `cut.py` and `assemble_portrait.py` read:

    <OUT>/<take>/events.jsonl      start / clip / clipend, seconds on the take clock
    <OUT>/<take>/<stream>.mp4      the phone's screen, time 0 == the `start` event
    <OUT>/<take>/<stream>.src.mov  what simctl actually wrote, kept as the master

A scene looks like the web one, with phone verbs instead of a cursor:

    from sim_recorder import SimTake
    from demos import load_demo
    demo = load_demo(__file__)
    with SimTake("s1-onboarding", demo) as t:
        with t.clip("choosing a project", "phone"):
            t.tap_text("Projects")
            t.wait(1.2)

**Why the recording is normalised.** `simctl io recordVideo` writes a frame only when the
screen changes, so a still app records almost nothing: six seconds of a static screen came
out as a single frame in a 0.07 s file. Seeking to a clip four seconds in would then find no
picture at all. So when a take ends, the raw capture is rebuilt at a constant frame rate with
its last frame held, to exactly the take's own length — a held frame is a truthful picture of
an app that did not move, and every later seek is simple arithmetic. This is the simulator's
version of the trick Alaina's recorder plays on Chromium, which stops recording a still page
for the same reason.

CLI:

    python sim_recorder.py devices                        # what is bootable, and what is booted
    python sim_recorder.py session <demo-folder> <take>   # hold a recording open, driven from outside
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator

from demos import load_demo
from sim_driver import Driver, driver_for

FPS = 30
# simctl prints this once the capture is live; the take clock starts there, so the video's
# time 0 and the `start` event mean the same instant.
STARTED = "Recording started"
START_TIMEOUT = 30.0
STOP_TIMEOUT = 60.0
TAIL_S = 1.0  # recorded past the last clip, off camera, so its end is never the file's edge
POLL = 0.25
# A tidy status bar, the one Apple puts in its own screenshots.
STATUS_BAR = ("--time", "9:41", "--batteryState", "charged", "--batteryLevel", "100",
              "--cellularMode", "active", "--cellularBars", "4", "--dataNetwork", "wifi",
              "--wifiMode", "active", "--wifiBars", "3")


def simctl(*args: str, capture: bool = False, check: bool = True) -> str:
    done = subprocess.run(["xcrun", "simctl", *args], capture_output=capture, text=True)
    if check and done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip() if capture else ""
        raise RuntimeError(f"simctl {' '.join(args)} failed ({done.returncode}) {detail}".strip())
    return done.stdout if capture else ""


def devices() -> list[dict]:
    """Every available simulator, each with its name, udid, runtime and state."""
    listing = json.loads(simctl("list", "devices", "available", "--json", capture=True))
    return [{**device, "runtime": runtime.rsplit(".", 1)[-1].replace("-", " ")}
            for runtime, group in listing["devices"].items() for device in group]


def resolve_device(wanted: str | None) -> str:
    """The udid for *wanted*: a udid, a device name, or None/"booted" for the booted one.

    A name that matches several simulators prefers a booted one, then the newest runtime,
    so "iPhone 17 Pro Max" means the obvious thing without pinning a udid in demo.py.
    """
    found = devices()
    if not wanted or wanted == "booted":
        booted = [d for d in found if d["state"] == "Booted"]
        if not booted:
            raise SystemExit("no simulator is booted -> xcrun simctl boot 'iPhone 17 Pro Max' "
                             "(then open Device Hub, in Xcode 26 and later, to watch it)")
        if len(booted) > 1:
            names = ", ".join(f"{d['name']} ({d['udid']})" for d in booted)
            raise SystemExit(f"{len(booted)} simulators are booted; set DEVICE in demo.py: {names}")
        return booted[0]["udid"]
    exact = [d for d in found if d["udid"] == wanted]
    if exact:
        return exact[0]["udid"]
    named = [d for d in found if d["name"] == wanted]
    if not named:
        have = ", ".join(sorted({d["name"] for d in found}))
        raise SystemExit(f"no simulator named {wanted!r}. Available: {have}")
    named.sort(key=lambda d: (d["state"] == "Booted", d["runtime"]), reverse=True)
    return named[0]["udid"]


def boot(udid: str) -> None:
    if any(d["udid"] == udid and d["state"] == "Booted" for d in devices()):
        return
    simctl("boot", udid)
    simctl("bootstatus", udid, check=False)  # returns as soon as the device is ready


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip() or 0.0)


def normalise(src: Path, dst: Path, length: float, fps: int = FPS) -> None:
    """Rebuild *src* at a constant *fps*, exactly *length* seconds long, holding its last frame.

    simctl writes frames only on change, so the capture is sparse and usually far shorter than
    the wall-clock take. Cloning the last frame out to the take's length makes the file's
    timeline and the event log's the same timeline, which is all the cut needs.
    """
    have = duration(src)
    pad = max(0.0, length - have) + 1.0
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf",
                    f"fps={fps},tpad=stop_mode=clone:stop_duration={pad:.3f}",
                    "-t", f"{length:.3f}", "-an", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "20", "-pix_fmt", "yuv420p", str(dst)], check=True)
    got = duration(dst)
    if abs(got - length) > 0.2:
        raise RuntimeError(f"{dst.name} normalised to {got:.2f}s, expected {length:.2f}s")


class SimTake:
    """One recorded take of a booted simulator. Same events, same files, as `recorder.Take`."""

    def __init__(self, name: str, demo: ModuleType, stream: str | None = None):
        self.name, self.demo = name, demo
        self.final, self.dir = demo.OUT / name, demo.OUT / f"{name}.partial"
        streams = list(demo.STREAMS)
        if stream is None and len(streams) != 1:
            raise SystemExit("a simulator take records one stream; demo.py has "
                             f"{len(streams)}: name one, or leave STREAMS with a single entry")
        self.stream = stream or streams[0]
        if self.stream not in demo.STREAMS:
            raise SystemExit(f"no stream {self.stream!r} in demo.py (streams: {', '.join(streams)})")
        self.udid = resolve_device(getattr(demo, "DEVICE", None))
        self.driver: Driver = driver_for(getattr(demo, "DRIVER", "manual"), self.udid,
                                         getattr(demo, "SCREEN_POINTS", None))
        self._log = None
        self._t0 = 0.0
        self._rec: subprocess.Popen | None = None
        self._src = self.dir / f"{self.stream}.src.mov"

    # --- clock and log (the contract cut.py and assemble_portrait.py read) ----------------
    def now(self) -> float:
        return round(time.monotonic() - self._t0, 3)

    def event(self, kind: str, **fields) -> None:
        record = {"t": self.now(), "kind": kind, **fields}
        self._log.write(json.dumps(record) + "\n")
        self._log.flush()
        print(f"[{record['t']:8.1f}] {kind} {fields}", flush=True)

    @contextmanager
    def clip(self, label: str, focus: str | None = None) -> Iterator[None]:
        """A stretch the cut KEEPS. One clip = one shot = one narration line in demo.SCENES.
        Everything between clips is off camera, so waits and setup cost the viewer nothing."""
        focus = focus or self.stream
        if focus != self.stream:
            raise ValueError(f"clip focus {focus!r} is not this take's stream ({self.stream!r})")
        self.event("clip", label=label, focus=focus)
        try:
            yield
        finally:
            self.event("clipend", label=label)

    # --- phone verbs (the driver does the touching; see sim_driver.py) --------------------
    def tap(self, x: float, y: float) -> None:
        self.driver.tap(x, y)

    def tap_text(self, text: str) -> None:
        self.driver.tap_text(text)

    def type(self, text: str) -> None:
        self.driver.type_text(text)

    def swipe(self, direction: str) -> None:
        self.driver.swipe(direction)

    def wait(self, seconds: float) -> None:
        """Hold. Inside a clip this is a reading beat; between clips it is cut."""
        time.sleep(seconds)

    def until(self, text: str, timeout: float, poll: float = 0.5) -> None:
        """Block until something labelled *text* is on screen; fail loudly on timeout."""
        describe = getattr(self.driver, "find", None)
        if describe is None:
            raise SystemExit("waiting on a label needs a driver that reads the accessibility "
                             "tree (DRIVER = \"idb\"); use t.wait(seconds) instead")
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if describe(text) is not None:
                return
            time.sleep(poll)
        raise TimeoutError(f"nothing labelled {text!r} appeared within {timeout:.0f}s")

    def screenshot(self, dst: Path) -> Path:
        """A still of the phone right now: for checking a scene without re-rendering it."""
        simctl("io", self.udid, "screenshot", "--type", "png", str(dst))
        return dst

    # --- app and device ------------------------------------------------------------------
    def launch(self, bundle_id: str, *args: str, relaunch: bool = True) -> None:
        if relaunch:
            simctl("terminate", self.udid, bundle_id, check=False)
            time.sleep(0.6)
        simctl("launch", self.udid, bundle_id, *args)

    def open_url(self, url: str) -> None:
        """Open a URL on the phone: a deep link into the app, or a stock pane like
        "prefs:root=General". Moves the screen without needing a UI driver."""
        simctl("openurl", self.udid, url)

    def appearance(self, mode: str) -> None:
        """Switch the phone between "light" and "dark". Useful off camera, to show the same
        screen both ways without a single tap."""
        if mode not in ("light", "dark"):
            raise ValueError('appearance must be "light" or "dark"')
        simctl("ui", self.udid, "appearance", mode)

    # --- lifecycle -----------------------------------------------------------------------
    def __enter__(self) -> "SimTake":
        boot(self.udid)
        if getattr(self.demo, "STATUS_BAR", True):
            simctl("status_bar", self.udid, "override", *STATUS_BAR, check=False)
        bundle = getattr(self.demo, "BUNDLE_ID", None)
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True)
        self._log = open(self.dir / "events.jsonl", "w")
        try:
            if bundle:
                self.launch(bundle)
                time.sleep(getattr(self.demo, "LAUNCH_SETTLE_S", 2.0))  # off camera
            self._start_recording()
        except BaseException:
            self._stop_recording()
            self._log.close()
            raise
        self.event("start", stream=self.stream)
        self.event("ready")
        return self

    def _start_recording(self) -> None:
        args = ["xcrun", "simctl", "io", self.udid, "recordVideo", "--codec", "h264", "--force"]
        display = getattr(self.demo, "DISPLAY", None)
        if display:
            args += ["--display", str(display)]
        self._rec = subprocess.Popen([*args, str(self._src)], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
        end = time.monotonic() + START_TIMEOUT
        for line in self._rec.stdout:
            print(f"  simctl: {line.rstrip()}", flush=True)
            if STARTED in line:
                self._t0 = time.monotonic()  # the video's time 0 and the take clock's
                return
            if time.monotonic() > end:
                break
        raise SystemExit(f"the simulator never started recording (no {STARTED!r} within "
                         f"{START_TIMEOUT:.0f}s). Is the device booted and its display awake?")

    def _stop_recording(self) -> None:
        if self._rec is None or self._rec.poll() is not None:
            return
        self._rec.send_signal(signal.SIGINT)  # simctl flushes the movie on SIGINT, not SIGTERM
        try:
            self._rec.wait(timeout=STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._rec.kill()
            self._rec.wait()
            print("the recorder had to be killed; this take's video may be short", flush=True)
        self._rec = None

    def __exit__(self, exc_type, *exc) -> None:
        try:
            if exc_type is None:
                time.sleep(TAIL_S)  # off camera: the last clip is never the file's last frame
            self.event("end")
            length = self.now()
        finally:
            self._stop_recording()
            self._log.close()
            if getattr(self.demo, "STATUS_BAR", True):
                simctl("status_bar", self.udid, "clear", check=False)
        if exc_type is not None:
            print(f"take {self.name} failed: kept the last good take; this one is in {self.dir}")
            return
        normalise(self._src, self.dir / f"{self.stream}.mp4", length)
        if self.final.exists():
            shutil.rmtree(self.final)
        self.dir.rename(self.final)
        print(f"{self.final}  ({length:.1f} s)")


# --- session mode: the recording held open, clips taken from a control pipe ----------------
HELP = """commands (one per line):
  clip <label>   start a shot: what the viewer will see
  clipend        end it; everything until the next clip is cut
  end            finish the take and write the video
"""


def session(demo: ModuleType, take_name: str, stream: str | None = None) -> None:
    """Record while something else drives the app: an agent with the Expo MCP, or a person.

    Prints a control pipe's path, then follows the commands written to it. This is the
    zero-install route: nothing here taps the phone, it only keeps the clock and the log.
    """
    with SimTake(take_name, demo, stream) as take:
        control = take.dir / "ctl"
        os.mkfifo(control)
        print(f"\nRECORDING. Control pipe: {control}\n{HELP}"
              f"  echo 'clip opening the app' > {control}\n", flush=True)
        running = True
        open_label = None
        while running:
            with open(control) as pipe:  # reopened each time: a writer closing is not the end
                for line in pipe:
                    command, _, rest = line.strip().partition(" ")
                    if command == "clip":
                        if open_label is not None:
                            take.event("clipend", label=open_label)
                        take.event("clip", label=rest or "shot", focus=take.stream)
                        open_label = rest or "shot"
                    elif command == "clipend":
                        if open_label is None:
                            print("  (no clip is open)", flush=True)
                            continue
                        take.event("clipend", label=open_label)
                        open_label = None
                    elif command == "end":
                        if open_label is not None:
                            take.event("clipend", label=open_label)
                            open_label = None
                        running = False
                        break
                    elif command:
                        print(f"  unknown command {command!r}\n{HELP}", flush=True)


def main(argv: list[str]) -> None:
    if len(argv) >= 2 and argv[1] == "devices":
        for device in sorted(devices(), key=lambda d: (d["runtime"], d["name"])):
            mark = "*" if device["state"] == "Booted" else " "
            print(f"{mark} {device['name']:<28} {device['runtime']:<10} {device['udid']}")
        return
    if len(argv) in (4, 5) and argv[1] == "session":
        session(load_demo(argv[2]), argv[3], argv[4] if len(argv) == 5 else None)
        return
    raise SystemExit("usage: sim_recorder.py devices\n"
                     "       sim_recorder.py session <demo-folder> <take> [stream]")


if __name__ == "__main__":
    main(sys.argv)
