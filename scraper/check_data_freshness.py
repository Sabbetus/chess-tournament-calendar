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
DEFAULT_MAX_STALE_DAYS = 2

# TEMPORARY: ratings.fide.com refuses connections from GitHub-hosted runners
# (ConnectTimeout on every scheduled attempt, while it answers instantly from
# a residential IP), so FIDE data is refreshed by running the scraper
# elsewhere and committing the result. A 2-day threshold would therefore fire
# constantly and mean nothing. 7 days makes it a useful prompt instead: when
# it trips, it is time to run a manual refresh.
#
# REVERT TO 2 once the FIDE scrape runs somewhere it can actually reach FIDE
# (a self-hosted runner) — at that point a stale FIDE archive is a real fault
# again, and a 7-day blind spot would be hiding it.
FIDE_MAX_STALE_DAYS = 7

SOURCES = [
    ("chess-results", ROOT / "public" / "data" / "archive.json", DEFAULT_MAX_STALE_DAYS,
     "check the scrape run logs for [WARN] lines"),
    ("FIDE ratings", ROOT / "public" / "data" / "fide_archive.json", FIDE_MAX_STALE_DAYS,
     "expected until FIDE scraping moves off GitHub-hosted runners — run the scraper "
     "manually and commit the result"),
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

    for name, path, max_stale_days, hint in SOURCES:
        seen = last_seen(path)
        if seen is None:
            print(f"::warning::{name}: no lastSeen found in {path.name} — cannot determine freshness.")
            continue
        try:
            age = (today - date.fromisoformat(seen)).days
        except ValueError:
            print(f"::warning::{name}: unparseable lastSeen {seen!r} in {path.name}.")
            continue
        status = "STALE" if age > max_stale_days else "ok"
        print(f"[{status}] {name}: last successful scrape {seen} "
              f"({age} day(s) ago, threshold {max_stale_days})")
        if age > max_stale_days:
            stale.append((name, seen, age, max_stale_days, hint))

    if stale:
        for name, seen, age, max_stale_days, hint in stale:
            print(
                f"::error::{name} has not scraped successfully since {seen} "
                f"({age} days ago, threshold {max_stale_days}). The scrape workflow may be "
                f"green while the source is unreachable — {hint}."
            )
        sys.exit(1)

    print("All sources fresh.")


if __name__ == "__main__":
    main()
