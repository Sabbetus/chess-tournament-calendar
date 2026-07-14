#!/usr/bin/env bash
# Idempotent: postStartCommand runs on every Codespace start/resume, so guard
# against launching a second dev server on top of one still running.
if ! pgrep -f "astro dev" > /dev/null 2>&1; then
  cd "$(dirname "$0")/.."
  nohup npm run dev -- --host 0.0.0.0 > /tmp/astro-dev.log 2>&1 &
fi
