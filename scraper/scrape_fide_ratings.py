"""
Scraper for FIDE's rated-tournaments feed (ratings.fide.com), USA only.

Unlike chess-results.com, FIDE tournaments are registered with FIDE (and show
up in this feed) weeks before they're played, so this is a genuine upcoming
feed rather than a results archive. There's no overlap with chess-results:
these are events organizers submit directly to FIDE rather than run through
chess-results.com.

List endpoint (undocumented, used by the site's own DataTables widget):
  https://ratings.fide.com/a_tournaments.php?country=USA&period=current
Requires a browser User-Agent and Referer or it returns an empty body.

Row structure (9 columns per tournament):
  [0] FIDE event id
  [1] name (sometimes wrapped in an <a href=/report.phtml?event=ID> once played)
  [2] "City, ST"
  [3] time control code: s=Standard, r=Rapid, d=?, m=?, t=?
  [4] start date YYYY-MM-DD
  [5] date received (wrapped in <a>, blank until the tournament is played)
  [6] rating period label, e.g. "August 2026"
  [7] FRL publish date YYYY-MM-DD
  [8] flag (unused)

Per-event detail page (https://ratings.fide.com/tournament_information.phtml?
event=ID) fills in the fields the list doesn't have: end date, full time
control text, and the Chief Organizer's name + FIDE profile id (used to look
up a known club/organizer website via data/fide_organizers.json — FIDE itself
never exposes an "organizer entity", only a person's name).

This script produces its own archive (public/data/fide_archive.json, same
firstSeen/lastSeen/consecutiveMisses/status pattern as scrape_chess_results.py)
and then writes the combined public/data/tournaments.json by merging its own
upcoming entries with chess-results' upcoming entries from
public/data/archive.json (read-only). It must therefore run *after*
scrape_chess_results.py in the workflow, every time, or its output would be
dropped from the next chess-results-only regeneration.
"""

import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
FIDE_ARCHIVE_PATH = ROOT / "public" / "data" / "fide_archive.json"
OUTPUT_PATH = ROOT / "public" / "data" / "tournaments.json"
META_PATH = ROOT / "public" / "data" / "meta.json"
ORGANIZERS_PATH = ROOT / "data" / "fide_organizers.json"

LIST_URL = "https://ratings.fide.com/a_tournaments.php?country=USA&period=current"
DETAIL_URL = "https://ratings.fide.com/tournament_information.phtml?event={event_id}"
EVENT_URL = "https://ratings.fide.com/tournament_information.phtml?event={event_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://ratings.fide.com/rated_tournaments.phtml?country=USA",
    "X-Requested-With": "XMLHttpRequest",
}

TIME_CONTROL_MAP = {
    "s": "Classical",
    "r": "Rapid",
    "d": "Classical",
    "m": "Blitz",
    "t": "Blitz",
}

# The detail page's "Time Control" text starts with FIDE's own name for the
# rating type it's being submitted under ("Standard: 90 minutes with 30 second
# increment from move 1"). That prefix is authoritative; the list feed's
# System code is not — measured against this text, 73 of 280 entries (26%)
# carried the wrong code, including blitz events marked "s" and standard
# events marked "r". So the code is only consulted when the text is missing.
TIME_CONTROL_TEXT_RE = re.compile(r"^\s*(standard|rapid|blitz)\s*:", re.I)
TIME_CONTROL_BY_TEXT = {"standard": "Classical", "rapid": "Rapid", "blitz": "Blitz"}

# The site lists classical and rapid only — its own filters offer no blitz
# option, and the chess-results scraper likewise never queries blitz. FIDE's
# feed is full of them, so they're dropped rather than shown untyped.
EXCLUDED_TIME_CONTROLS = {"Blitz"}

MIN_ABSOLUTE_TOURNAMENTS = 20  # safety floor for USA-only feed; small country, small numbers
MAX_CONSECUTIVE_MISSES = 8  # same cadence reasoning as chess-results (~2 days at 6h runs)

# A single club's recurring event (e.g. Charlotte's weekly "Action Quads")
# gets split by FIDE into one section per skill bracket — "- A", "- B", "- C"
# etc — all sharing a name prefix, city, and start date. When a group like
# that gets large it clutters the US listings with near-duplicate rows for
# what is, from a player's perspective, one club night. Below this size,
# sections are kept as separate entries (as with chess-results) since they
# usually really are distinct sub-tournaments (e.g. an Open + a U1600 section).
SECTION_MERGE_THRESHOLD = 4

SECTION_SUFFIX_RE = re.compile(r"\s*-\s*[A-Za-z0-9]{1,3}\s*$")

# FIDE rates a club's weekly-round series (e.g. "CCC Tuesday Night Action 134",
# one round per Tuesday for a month) as a single event whose Start/End Date
# spans the whole series — 22-29 days for what a visitor would read as "one
# tournament" they could travel to, when it's really one game a week. That's
# not what this site is for, so entries longer than this get dropped. Set
# above chess-results' MAX_DURATION_DAYS (10) rather than at it: the real
# US Championship / US Women's Championship run ~13 continuous days in St.
# Louis and must survive the cut, and nothing else observed in this feed
# falls between 14 and 15 days.
MAX_DURATION_DAYS = 14


def classify_time_control(tc_raw, tc_code):
    """Prefer FIDE's own "Time Control" wording over the list feed's System
    code — see TIME_CONTROL_TEXT_RE for why the code can't be trusted."""
    m = TIME_CONTROL_TEXT_RE.match(tc_raw or "")
    if m:
        return TIME_CONTROL_BY_TEXT[m.group(1).lower()]
    return TIME_CONTROL_MAP.get(tc_code, "Classical")


def strip_html(s):
    text = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(text).replace("\xa0", " ").strip()


def slugify(name, event_id):
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return f"{slug}-fide-{event_id}"


def fetch_list():
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = json.loads(resp.text.lstrip("﻿"))
    return payload["data"]


def fetch_detail(event_id):
    """Fetch the per-event detail page. Returns a dict with endDate,
    timeControlRaw, organizer, organizerProfileId, playersRegistered — or
    None if the page couldn't be parsed (kept out of the archive that run,
    picked up again next run)."""
    try:
        resp = requests.get(DETAIL_URL.format(event_id=event_id), headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    page_html = resp.text

    def field(label):
        m = re.search(
            rf"{re.escape(label)}</td>\s*<td[^>]*>\s*(.*?)\s*</td>",
            page_html,
            flags=re.S,
        )
        return strip_html(m.group(1)) if m else None

    end_date = field("End Date")
    tc_raw = field("Time Control")
    players = field("Number of players")
    organizer_match = re.search(
        r"Chief Organizer</td>\s*<td[^>]*>(?:&nbsp;|\s)*<a href=/profile/(\d+)[^>]*>([^<]*)</a>",
        page_html,
        flags=re.S,
    )
    organizer_id = organizer_match.group(1) if organizer_match else None
    organizer_name = (
        html.unescape(organizer_match.group(2)).replace("\xa0", " ").strip()
        if organizer_match else field("Chief Organizer")
    )

    return {
        "endDate": end_date or None,
        "timeControlRaw": tc_raw or None,
        "playersRegistered": int(players) if players and players.isdigit() else None,
        "organizer": organizer_name or None,
        "organizerProfileId": organizer_id,
    }


def parse_rows(raw_rows):
    """Turn the raw list rows into tournament dicts, keeping only future
    start dates (this feed also includes recently-played tournaments waiting
    on their rating period to publish, which we don't want on an "upcoming
    tournaments" site)."""
    today = date.today().isoformat()
    out = []
    for row in raw_rows:
        event_id, name_raw, city_raw, tc_code, start_date = row[0], row[1], row[2], row[3], row[4]
        if start_date <= today:
            continue
        name = strip_html(name_raw)
        if not name:
            continue
        out.append({
            "eventId": event_id,
            "name": name,
            "city": strip_html(city_raw),
            "timeControlCode": tc_code,
            "startDate": start_date,
        })
    return out


def group_sections(rows):
    """Group rows sharing a name prefix (with a trailing "- A"/"- 3" section
    suffix stripped), city, and start date. Returns a list of groups, each a
    list of one or more rows, ordered by event id so the first section is the
    canonical one when a group gets merged."""
    groups = {}
    for row in rows:
        base_name = SECTION_SUFFIX_RE.sub("", row["name"]).strip()
        key = (base_name, row["city"], row["startDate"])
        groups.setdefault(key, []).append(row)
    return list(groups.values())


def load_organizers():
    if not ORGANIZERS_PATH.exists():
        return {}
    with open(ORGANIZERS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def build_tournaments(rows, detail_cache, organizers):
    tournaments = []
    for group in group_sections(rows):
        group.sort(key=lambda r: r["eventId"])
        merged = len(group) > SECTION_MERGE_THRESHOLD
        canonical = group[0]
        base_name = SECTION_SUFFIX_RE.sub("", canonical["name"]).strip()
        name = base_name if merged else canonical["name"]
        event_id = canonical["eventId"]
        detail = detail_cache.get(event_id) or {}

        organizer_name = detail.get("organizer")
        organizer_profile_id = detail.get("organizerProfileId")
        organizer_info = organizers.get(organizer_profile_id) if organizer_profile_id else None

        end_date = detail.get("endDate") or canonical["startDate"]
        try:
            span_days = (date.fromisoformat(end_date) - date.fromisoformat(canonical["startDate"])).days + 1
        except ValueError:
            span_days = 1
        if span_days > MAX_DURATION_DAYS:
            continue

        time_control = classify_time_control(detail.get("timeControlRaw"), canonical["timeControlCode"])
        if time_control in EXCLUDED_TIME_CONTROLS:
            continue

        tournaments.append({
            "id": f"fide-{event_id}",
            "slug": slugify(name, event_id),
            "name": name,
            "startDate": canonical["startDate"],
            "endDate": end_date,
            "city": canonical["city"],
            "country": "United States",
            "countryCode": "US",
            "rounds": None,
            "timeControl": time_control,
            "timeControlRaw": detail.get("timeControlRaw"),
            "playersRegistered": None,  # not known ahead of the event on this feed
            "prizePool": None,
            "currency": None,
            "ratingRequirement": None,
            "open": True,
            "registrationOpen": False,
            "registrationUrl": None,
            "websiteUrl": EVENT_URL.format(event_id=event_id),
            "description": None,
            "organizer": organizer_info["name"] if organizer_info else organizer_name,
            # The Chief Organizer exactly as FIDE reports them (a person). Kept
            # separately because "organizer" above gets replaced by the club
            # name whenever fide_organizers.json has a match — without this,
            # the first mapped run would destroy the original name and a later
            # removal from the map would leave a stale club name behind.
            "organizerRaw": organizer_name,
            "organizerUrl": organizer_info["url"] if organizer_info else None,
            "organizerProfileId": organizer_profile_id,
            "source": "fide-ratings",
            "sectionEventIds": [r["eventId"] for r in group] if merged else None,
        })
    return tournaments


def load_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return default


def merge_into_archive(scraped, archive):
    today = date.today().isoformat()
    by_id = {t["id"]: t for t in archive}
    scraped_ids = {t["id"] for t in scraped}

    for t in scraped:
        existing = by_id.get(t["id"])
        if existing:
            existing.update(t)
            existing["lastSeen"] = today
            existing["consecutiveMisses"] = 0
        else:
            t["firstSeen"] = today
            t["lastSeen"] = today
            t["consecutiveMisses"] = 0
            by_id[t["id"]] = t

    for tid, t in by_id.items():
        if tid not in scraped_ids and t["startDate"] > today:
            t["consecutiveMisses"] = t.get("consecutiveMisses", 0) + 1

    for t in by_id.values():
        t["status"] = "concluded" if t["startDate"] <= today else "upcoming"

    return sorted(by_id.values(), key=lambda t: t["startDate"])


def build_combined_output(fide_archive, existing_output):
    """Combines this script's own upcoming FIDE entries with whatever
    non-FIDE entries are already in tournaments.json. We deliberately don't
    re-derive the chess-results portion from archive.json here — that
    would mean reimplementing build_output()'s field list *and*
    _players_trend()'s history math, which belongs to
    scrape_chess_results.py. Since that script always runs first in the
    workflow, tournaments.json already has an up-to-date, correct
    chess-results (and manual/featured, if ever added there) portion when
    this script runs; we just need to not clobber it, and to replace our
    own previous entries rather than accumulate duplicates."""
    fide_upcoming = [
        t for t in fide_archive
        if t["status"] == "upcoming" and t.get("consecutiveMisses", 0) < MAX_CONSECUTIVE_MISSES
    ]
    for t in fide_upcoming:
        t.pop("firstSeen", None)
        t.pop("lastSeen", None)
        t.pop("consecutiveMisses", None)
        t.pop("status", None)
        t["playersTrend"] = None

    other_rows = [t for t in existing_output if t.get("source") != "fide-ratings"]

    return sorted(fide_upcoming + other_rows, key=lambda t: t["startDate"])


def main():
    print("[INFO] Fetching FIDE USA tournament list...")
    raw_rows = fetch_list()
    rows = parse_rows(raw_rows)
    print(f"[INFO] {len(rows)} upcoming rows out of {len(raw_rows)} total.")

    fide_archive = load_json(FIDE_ARCHIVE_PATH, [])
    # Reuse the detail we already fetched for events we've seen before. Only
    # "organizerRaw" is safe to cache as the organizer — "organizer" may have
    # been rewritten to a club name by a previous run's mapping. Entries
    # predating organizerRaw are left out so they get re-fetched once and heal.
    known_details = {t["id"].replace("fide-", ""): {
        "endDate": t.get("endDate"),
        "timeControlRaw": t.get("timeControlRaw"),
        "organizer": t.get("organizerRaw"),
        "organizerProfileId": t.get("organizerProfileId"),
        "playersRegistered": t.get("playersRegistered"),
    } for t in fide_archive if t.get("organizerRaw")}

    organizers = load_organizers()

    detail_cache = {}
    new_event_ids = {r["eventId"] for r in rows} - set(known_details)
    print(f"[INFO] Fetching detail pages for {len(new_event_ids)} newly-seen events...")
    for event_id in new_event_ids:
        detail = fetch_detail(event_id)
        if detail:
            detail_cache[event_id] = detail
    for event_id, detail in known_details.items():
        detail_cache.setdefault(event_id, detail)

    if len(rows) < MIN_ABSOLUTE_TOURNAMENTS and fide_archive:
        print(
            f"[ERROR] Only {len(rows)} upcoming rows found, below the safety floor of "
            f"{MIN_ABSOLUTE_TOURNAMENTS}. This looks like a partial fetch failure. "
            f"Refusing to update {FIDE_ARCHIVE_PATH}."
        )
        sys.exit(1)

    tournaments = build_tournaments(rows, detail_cache, organizers)

    merged = merge_into_archive(tournaments, fide_archive)
    FIDE_ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FIDE_ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"[INFO] FIDE archive updated: {len(merged)} total entries. Written to {FIDE_ARCHIVE_PATH}")

    existing_output = load_json(OUTPUT_PATH, [])
    combined = build_combined_output(merged, existing_output)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Written combined feed to {OUTPUT_PATH} ({len(combined)} tournaments)")

    meta = load_json(META_PATH, {})
    meta["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[INFO] Written to {META_PATH}")


if __name__ == "__main__":
    main()
