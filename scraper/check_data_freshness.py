#!/usr/bin/env python3
"""
Alerts when a data source has stopped updating.

Both scrapers are deliberately forgiving: if a source is unreachable they
keep serving the data already on disk rather than failing the workflow, so
that one source's outage can't discard the other's fresh scrape or block the
deploy. The cost of that is silence — runs stay green while a source quietly
goes stale. This is the counterweight.

It runs as its own workflow, NOT as a step inside scrape.yml. deploy.yml is
gated on the scrape workflow's conclusion:

    if: github.event_name != 'workflow_run' ||
        github.event.workflow_run.conclusion == 'success'

and because scrape.yml pushes with GITHUB_TOKEN (which by design does not
trigger other workflows), that workflow_run hook is the *only* path from a
scrape to a deploy. A failing step inside scrape.yml would therefore commit
the data and then suppress the deploy of it. Failing from a separate
workflow keeps that gate untouched.

Freshness comes from each archive's "lastSeen", which only advances when a
scrape actually succeeds. meta.json's "lastUpdated" is not usable here — it
is rewritten on every run, including runs that never reached the source.
"""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Dates in the archives are day-resolution, so this is "more than N whole days
# behind today". At the 6-hourly scrape cadence, 2 days is ~8 consecutive
# failed runs — well clear of a transient outage, and harmless in freshness
# terms given tournaments are listed weeks ahead.
MAX_STALE_DAYS = 2

SOURCES = [
    ("chess-results", ROOT / "public" / "data" / "archive.json"),
    ("FIDE ratings", ROOT / "public" / "data" / "fide_archive.json"),
]


def last_seen(path):
    """Most recent lastSeen across an archive, or None if unavailable."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    seen = [e["lastSeen"] for e in entries if e.get("lastSeen")]
    return max(seen) if seen else None


def main():
    today = date.today()
    stale = []

    for name, path in SOURCES:
        seen = last_seen(path)
        if seen is None:
            print(f"::warning::{name}: no lastSeen found in {path.name} — cannot determine freshness.")
            continue
        try:
            age = (today - date.fromisoformat(seen)).days
        except ValueError:
            print(f"::warning::{name}: unparseable lastSeen {seen!r} in {path.name}.")
            continue
        status = "STALE" if age > MAX_STALE_DAYS else "ok"
        print(f"[{status}] {name}: last successful scrape {seen} ({age} day(s) ago)")
        if age > MAX_STALE_DAYS:
            stale.append((name, seen, age))

    if stale:
        for name, seen, age in stale:
            print(
                f"::error::{name} has not scraped successfully since {seen} "
                f"({age} days ago, threshold {MAX_STALE_DAYS}). The scrape workflow may be "
                f"green while the source is unreachable — check the scrape run logs for "
                f"[WARN] lines."
            )
        sys.exit(1)

    print("All sources fresh.")


if __name__ == "__main__":
    main()
