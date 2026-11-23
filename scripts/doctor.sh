#!/usr/bin/env bash
# Check what the demo-video pipeline needs on this Mac; print the fix for anything missing.
#
#   doctor.sh              both paths
#   doctor.sh --web        the Playwright web/terminal path only
#   doctor.sh --simulator  the iOS simulator path only
#
# The two paths need different things, so checking both at once makes a phone demo look
# broken because tmux is missing. Pick the one you are using.
set -uo pipefail
want="${1:---all}"
case "$want" in
  --all|--web|--simulator) ;;
  *) echo "usage: doctor.sh [--all|--web|--simulator]"; exit 2 ;;
esac
web=0; sim=0
[ "$want" = "--all" ] || [ "$want" = "--web" ] && web=1
[ "$want" = "--all" ] || [ "$want" = "--simulator" ] && sim=1
fail=0
need() { if ! command -v "$1" >/dev/null 2>&1; then echo "MISSING $1 -> $2"; fail=1; fi; }

# --- both paths -------------------------------------------------------------------------
need ffmpeg  "brew install ffmpeg"
need ffprobe "brew install ffmpeg"
need uv      "curl -LsSf https://astral.sh/uv/install.sh | sh"

# --- the web/terminal path --------------------------------------------------------------
if [ $web = 1 ]; then
  need tmux "brew install tmux"
  for f in "/System/Library/Fonts/Supplemental/Arial.ttf" "/System/Library/Fonts/Supplemental/Arial Bold.ttf"; do
    [ -f "$f" ] || { echo "MISSING font $f"; fail=1; }
  done
  # Read the list first: `grep -q` closing the pipe early fails it under pipefail.
  filters="$(ffmpeg -hide_banner -filters 2>/dev/null || true)"
  if command -v ffmpeg >/dev/null && ! grep -q " drawtext " <<<"$filters"; then
    # Homebrew's plain ffmpeg formula is built without freetype, so reinstalling it can't help.
    # Only the desktop renderer needs drawtext; the portrait one draws its text with Pillow.
    echo "MISSING ffmpeg drawtext filter (the web path's title card and +N s tags) ->"
    echo "        brew install homebrew-ffmpeg/ffmpeg/ffmpeg   # builds from source, takes a while"
    fail=1
  fi
  if command -v uv >/dev/null && ! uv run -q --no-project --with playwright python -c \
    "from playwright.sync_api import sync_playwright as p; b=p().start().chromium.launch(); b.close()" >/dev/null 2>&1; then
    echo "MISSING Playwright Chromium -> uv run --no-project --with playwright playwright install chromium"; fail=1
  fi
fi

# --- the iOS simulator path ---------------------------------------------------------------
if [ $sim = 1 ]; then
  if ! xcrun simctl help >/dev/null 2>&1; then
    echo "MISSING xcrun simctl -> install Xcode, then: sudo xcode-select -s /Applications/Xcode.app"; fail=1
  else
    booted="$(xcrun simctl list devices booted 2>/dev/null | grep -c "(Booted)" || true)"
    if [ "$booted" = 0 ]; then
      echo "MISSING a booted simulator -> xcrun simctl boot 'iPhone 17 Pro Max'"
      echo "        (Xcode 26 and later: the window is Device Hub, not Simulator.app)"
      fail=1
    elif [ "$booted" -gt 1 ]; then
      echo "note: $booted simulators are booted; set DEVICE in demo.py to say which one"
    fi
  fi
  # Pillow draws the portrait title card. uv fetches it per run, so this only warms the cache.
  if command -v uv >/dev/null && ! uv run -q --no-project --with pillow python -c \
    "import PIL" >/dev/null 2>&1; then
    echo "MISSING Pillow (the portrait title card) -> check uv can reach the network"; fail=1
  fi
  # Optional: only a scripted scene that taps needs a UI driver.
  if command -v idb >/dev/null 2>&1; then
    echo "idb: found (scripted taps available; DRIVER = \"idb\")"
  else
    echo "idb: not installed (fine unless a scene taps by itself; then"
    echo "     brew install idb-companion && pipx install fb-idb)"
  fi
fi

# Optional: only eleven: voices need a key.
if [ -n "${ELEVENLABS_API_KEY:-}" ] || grep -Eq '^[[:space:]]*(export[[:space:]]+)?ELEVENLABS_API_KEY[[:space:]]*=' "$HOME/.config/demo-video/elevenlabs.env" 2>/dev/null; then
  echo "elevenlabs: key found"
else
  echo "elevenlabs: no key (only needed for eleven: voices)"
fi
[ $fail = 0 ] && echo "doctor: ok"
exit $fail
