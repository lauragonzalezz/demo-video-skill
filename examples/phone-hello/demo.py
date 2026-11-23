"""The phone-hello demo: the simulator path's smoke test, and the template to copy.

It drives the stock iOS **Settings** app, which every simulator already has, so this runs on
a fresh checkout with nothing installed and no app to build. `run.sh` records and assembles
it end to end in about a minute.
"""
from pathlib import Path

TITLE = "Hello, phone demo"          # the intro card; set to "" to skip the card entirely
SUBTITLE = "Recorded on the simulator, narrated by Kokoro"
BACKEND = "simulator"                # simctl records the screen; see scripts/sim_recorder.py
FORMAT = "portrait"                  # the footage's own aspect, full bleed; see scripts/layout.py
OUT = Path("../../exports/phone-hello")  # relative to this folder, and gitignored

# Which simulator. None means "the one that is booted"; a name like "iPhone 17 Pro Max" boots
# it if needed. The recording is the screen itself: no window chrome, no device bezel.
DEVICE = None
BUNDLE_ID = "com.apple.Preferences"  # launched off camera before the take starts
DRIVER = "manual"                    # no taps here, so no idb needed; see scripts/sim_driver.py

# A simulator take records one stream: the phone.
STREAMS = {"phone": {"title": "iPhone"}}

# One entry per take, in video order; one line per clip in that take (None = no line).
SCENES = [
    {"take": "s1-settings",
     "lines": ["Here's the phone, with Settings open, in the light theme.",
               "And here's the very same screen in the dark one, with the switch cut out."]},
]
