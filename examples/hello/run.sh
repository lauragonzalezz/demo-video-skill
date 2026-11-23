#!/usr/bin/env bash
# The pipeline's smoke test: record both hello takes and assemble the video, end to end.
#   bash run.sh   -> exports/hello/final/hello.mp4 (+ -script.md, -picture.mp4, -preview.mp4)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export DEMO_VIDEO_SCRIPTS="${DEMO_VIDEO_SCRIPTS:-$HERE/../../scripts}"
PY=(uv run -q --no-project --with playwright python)

# The desktop renderer needs ffmpeg's drawtext, which Homebrew's plain ffmpeg lacks.
# ffmpeg-full is keg-only, so it is installed but not on PATH: put it first when it is
# the one with drawtext. Nothing is changed for the rest of the shell.
if ! ffmpeg -hide_banner -filters 2>/dev/null | grep -q " drawtext "; then
  FULL="$(brew --prefix ffmpeg-full 2>/dev/null || true)"
  [ -x "${FULL:-}/bin/ffmpeg" ] && export PATH="$FULL/bin:$PATH"
fi

bash "$DEMO_VIDEO_SCRIPTS/doctor.sh" --web
if lsof -nP -iTCP:8795 -sTCP:LISTEN >/dev/null; then echo "port 8795 is in use; stop that server first"; exit 1; fi
bash "$DEMO_VIDEO_SCRIPTS/stage.sh" start hellodemo 7692 "$HERE" '^report done'
python3 -m http.server 8795 --bind 127.0.0.1 --directory "$HERE" >/dev/null 2>&1 & WEB=$!
trap '{ kill $WEB && wait $WEB; } 2>/dev/null || true; bash "$DEMO_VIDEO_SCRIPTS/stage.sh" stop hellodemo' EXIT

(cd "$HERE" && "${PY[@]}" scenes.py)
"${PY[@]}" "$DEMO_VIDEO_SCRIPTS/assemble.py" "$HERE" "$HERE/../../exports/hello/final/hello.mp4"
