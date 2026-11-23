#!/usr/bin/env bash
# The simulator path's smoke test: record the phone take and assemble the video, end to end.
#   bash run.sh   -> exports/phone-hello/final/phone-hello.mp4 (+ -script.md, -picture.mp4, -preview.mp4)
#
# Needs a booted simulator (any iPhone) and nothing else installed: the scene moves the
# screen with simctl, so no UI driver, no app to build, no network.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export DEMO_VIDEO_SCRIPTS="${DEMO_VIDEO_SCRIPTS:-$HERE/../../scripts}"
# Pillow draws the title card; Kokoro voices the lines in its own environment (see tts.py).
PY=(uv run -q --no-project --with pillow python)
FINAL="$HERE/../../exports/phone-hello/final/phone-hello.mp4"

bash "$DEMO_VIDEO_SCRIPTS/doctor.sh" --simulator
(cd "$HERE" && "${PY[@]}" scenes.py)
"${PY[@]}" "$DEMO_VIDEO_SCRIPTS/fit_portrait.py" "$HERE"
"${PY[@]}" "$DEMO_VIDEO_SCRIPTS/assemble_portrait.py" "$HERE" "$FINAL"
