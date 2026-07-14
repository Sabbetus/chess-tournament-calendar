#!/usr/bin/env bash
# Idempotent: postStartCommand runs on every Codespace start/resume, so guard
# against launching a second dev server on top of one still running.
if ! pgrep -f "astro dev" > /dev/null 2>&1; then
  cd "$(dirname "$0")/.."
  # setsid fully detaches into a new session so the server survives
  # postStartCommand's process group being torn down once it exits.
  setsid nohup npm run dev -- --host 0.0.0.0 > /tmp/astro-dev.log 2>&1 < /dev/null &
  disown
fi
