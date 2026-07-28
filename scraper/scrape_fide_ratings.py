"""
Scraper for FIDE's rated-tournaments feed (ratings.fide.com), for a fixed list
of countries where chess-results.com has little or no presence — see
COUNTRIES below. Unlike chess-results.com, FIDE tournaments are registered
with FIDE (and show up in this feed) weeks before they're played, so this is
a genuine upcoming feed rather than a results archive.

List endpoint (undocumented, used by the site's own DataTables widget):
  https://ratings.fide.com/a_tournaments.php?country=USA&period=current
Requires a browser User-Agent and Referer or it returns an empty body. The
"period" query param is cosmetic — every country code tested returns the same
rolling ~1-month-back window regardless of its value, so there is no way to
ask this endpoint for an older period.

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
never exposes an "organizer entity", only a person's name). Two countries
(Norway, Denmark) skip that lookup entirely: their national federations run a
single site that lists all of that country's tournaments, so every event from
those countries always links there instead — see COUNTRIES.

This script produces its own archive (public/data/fide_archive.json, same
firstSeen/lastSeen/consecutiveMisses/status pattern as scrape_chess_results.py,
covering every country below in one flat list — FIDE event ids are globally
unique so there's no need to split it up) and then writes the combined
public/data/tournaments.json by merging its own upcoming entries with
chess-results' upcoming entries from public/data/archive.json (read-only). It
must therefore run *after* scrape_chess_results.py in the workflow, every
time, or its output would be dropped from the next chess-results-only
regeneration.
"""

import html
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
FIDE_ARCHIVE_PATH = ROOT / "public" / "data" / "fide_archive.json"
# Per-event detail (end date, time control, organizer) keyed by FIDE event id,
# for *every* event we've fetched — including ones the filters then reject.
# The archive only holds events we publish, so without this the ~100 blitz and
# multi-week events we drop would have their detail pages re-fetched on every
# run, forever. Caching the raw detail rather than a bare "skip these ids" list
# also means the filters are re-evaluated from cache each run, so changing
# MAX_DURATION_DAYS or the blitz rule takes effect without any re-fetching.
FIDE_DETAILS_PATH = ROOT / "public" / "data" / "fide_details.json"
OUTPUT_PATH = ROOT / "public" / "data" / "tournaments.json"
META_PATH = ROOT / "public" / "data" / "meta.json"
ORGANIZERS_PATH = ROOT / "data" / "fide_organizers.json"

LIST_URL_TEMPLATE = "https://ratings.fide.com/a_tournaments.php?country={code}&period=current"
DETAIL_URL = "https://ratings.fide.com/tournament_information.phtml?event={event_id}"
EVENT_URL = "https://ratings.fide.com/tournament_information.phtml?event={event_id}"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def headers_for(country_code):
    return {
        "User-Agent": USER_AGENT,
        "Referer": f"https://ratings.fide.com/rated_tournaments.phtml?country={country_code}",
        "X-Requested-With": "XMLHttpRequest",
    }


# Every country chess-results.com has little or no real presence in, chosen by
# comparing FIDE's feed against a live chess-results.com search over the same
# ~5-week window (2026-06-25 to 2026-07-28, the oldest FIDE's feed goes back
# to): Norway had 65 FIDE tournaments to chess-results' 0, Denmark 14 to 0,
# Australia 51 to 8 with zero name/date overlap between the two lists.
#
# min_tournaments is a per-country safety floor (see MIN_ABSOLUTE_TOURNAMENTS'
# old USA-only reasoning) — scaled down from the volumes above, low enough
# that only a genuine fetch problem trips it, not ordinary week-to-week
# variance.
#
# fixed_organizer_url: Norway (tournamentservice.com) and Denmark
# (turnering.skak.dk) each have a single national federation site listing
# every tournament in the country, confirmed by hand — every event from these
# countries links there instead of going through the per-organizer lookup.
COUNTRIES = [
    {"code": "USA", "name": "United States", "iso": "US", "min_tournaments": 20, "fixed_organizer_url": None},
    {"code": "AUS", "name": "Australia", "iso": "AU", "min_tournaments": 15, "fixed_organizer_url": None},
    {"code": "NOR", "name": "Norway", "iso": "NO", "min_tournaments": 15, "fixed_organizer_url": "https://tournamentservice.com/"},
    {"code": "DEN", "name": "Denmark", "iso": "DK", "min_tournaments": 5, "fixed_organizer_url": "https://turnering.skak.dk/"},
]

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

REQUEST_TIMEOUT = 30
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_SECONDS = 5

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

# Some Danish club ladders put the round descriptor *after* the division
# marker instead of at the very end ("Hillerod Midtspil 2 - 1 Round 1-2",
# "- 2 Round 1-2", ... one row per division, same club night) — stripping this
# first lets SECTION_SUFFIX_RE's trailing match reach the division marker.
# Safe to strip unconditionally: a group's key already includes city and
# start date, so two genuinely different sessions of the same series stay
# distinguished by date even with "Round X-Y" removed from the name.
TRAILING_ROUND_RE = re.compile(r"\s+Rounds?\s+\d+(?:-\d+)?\s*$", re.I)


def strip_section_suffix(name):
    return SECTION_SUFFIX_RE.sub("", TRAILING_ROUND_RE.sub("", name)).strip()

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


def gha_annotate(level, msg):
    """Emit a GitHub Actions annotation (shows on the run summary page, not
    just in the raw log) in addition to a normal print. Reserved for
    run-level conditions worth noticing from the Actions UI without opening
    the log — a failed FIDE fetch or a hard failure — not per-attempt retry
    noise, which fires too often (every detail-page fetch, not just the list)
    to be a useful annotation.
    GitHub's workflow-command syntax requires %, \\r, \\n percent-encoded so a
    multi-line message can't break the ::level::text line."""
    print(f"[{level.upper()}] {msg}")
    escaped = msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{level}::{escaped}")


def fetch(url, headers):
    """GET with a few retries. ratings.fide.com intermittently refuses
    connections from CI runners — it answers fine from a desktop while timing
    out from GitHub Actions — so a single attempt is not a fair test of
    whether the site is up."""
    last_error = None
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_error = e
            if attempt < FETCH_ATTEMPTS:
                delay = FETCH_BACKOFF_SECONDS * attempt
                print(f"[WARN] {type(e).__name__} on {url} (attempt {attempt}/{FETCH_ATTEMPTS}); retrying in {delay}s.")
                time.sleep(delay)
    raise last_error


def fetch_list(country_code):
    resp = fetch(LIST_URL_TEMPLATE.format(code=country_code), headers_for(country_code))
    payload = json.loads(resp.text.lstrip("﻿"))
    return payload["data"]


def fetch_detail(event_id, country_code):
    """Fetch the per-event detail page. Returns a dict with endDate,
    timeControlRaw, organizer, organizerProfileId, playersRegistered — or
    None if the page couldn't be parsed (kept out of the archive that run,
    picked up again next run)."""
    try:
        resp = fetch(DETAIL_URL.format(event_id=event_id), headers_for(country_code))
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
        base_name = strip_section_suffix(row["name"])
        key = (base_name, row["city"], row["startDate"])
        groups.setdefault(key, []).append(row)
    return list(groups.values())


def load_organizers():
    if not ORGANIZERS_PATH.exists():
        return {}
    with open(ORGANIZERS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def resolve_organizer(organizer_info, event_name):
    """Pick the {name, url} an organizer's event should link to.

    A FIDE "Chief Organizer" is a person, and some of them run two genuinely
    unrelated series — Shaun Press submits both the weekly Street Chess and
    the ANU Open, Ian McAteer both the CAWA Perth Chess League and a Southern
    Suburbs club cup. Neither series' site lists the other's events, so a
    single URL per profile id would send half the visitors to a page their
    tournament isn't on. An optional "byEventName" list handles that: the
    first entry whose "contains" appears in the event name wins, and the
    top-level url is the fallback for everything else."""
    if not organizer_info:
        return None
    for override in organizer_info.get("byEventName", []):
        if override["contains"].lower() in event_name.lower():
            return override
    return organizer_info


def build_tournaments(rows, detail_cache, organizers, country):
    tournaments = []
    for group in group_sections(rows):
        group.sort(key=lambda r: r["eventId"])
        merged = len(group) > SECTION_MERGE_THRESHOLD
        canonical = group[0]
        base_name = strip_section_suffix(canonical["name"])
        name = base_name if merged else canonical["name"]
        event_id = canonical["eventId"]
        detail = detail_cache.get(event_id) or {}

        organizer_name = detail.get("organizer")
        organizer_profile_id = detail.get("organizerProfileId")
        organizer_info = resolve_organizer(
            organizers.get(organizer_profile_id) if organizer_profile_id else None, name
        )
        # Norway/Denmark: skip the per-organizer lookup entirely, every event
        # from these countries always links to the national federation's own
        # tournament site (see COUNTRIES).
        organizer_url = country["fixed_organizer_url"] or (organizer_info["url"] if organizer_info else None)

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
            "country": country["name"],
            "countryCode": country["iso"],
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
            "organizerUrl": organizer_url,
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


def merge_into_archive(scraped, archive, considered_isos):
    """considered_isos is the set of country ISO codes actually fetched (and
    above their safety floor) this run. A country whose fetch failed, or came
    in suspiciously low, has none of its tournaments in `scraped` — without
    this, every existing entry from that country would look like a miss and
    the whole country would silently age out over a single bad outage, the
    same reasoning as republish_archive_unchanged() but scoped to one country
    instead of all of FIDE."""
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
        if tid not in scraped_ids and t["startDate"] > today and t.get("countryCode") in considered_isos:
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


def write_output(combined):
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Written combined feed to {OUTPUT_PATH} ({len(combined)} tournaments)")

    meta = load_json(META_PATH, {})
    meta["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[INFO] Written to {META_PATH}")


def republish_archive_unchanged(reason):
    """Every country's fetch failed or came in below its safety floor this
    run. Republish the FIDE entries we already have rather than failing.

    Exiting non-zero here would be actively harmful, twice over. The workflow
    would stop before its commit step, throwing away the chess-results scrape
    that already succeeded in the previous step — so an outage at FIDE would
    freeze the entire site's data, not just the FIDE portion. And because
    scrape_chess_results.py rewrites tournaments.json with only its own
    entries, simply skipping this script would publish a feed with every FIDE
    tournament missing. So the archive has to be written back either way.

    The archive is left untouched: no merge, so no consecutive-miss counting.
    A run that never reached FIDE is not evidence that a tournament is gone,
    and counting it as a miss would let a long outage silently age out the
    whole feed. A single country failing while others succeed doesn't reach
    here at all — see main()'s per-country considered_isos handling, which
    keeps a bad country from aging out while the rest of the run proceeds
    normally."""
    gha_annotate("warning", reason)

    # Tolerating an outage is only reasonable while the *other* source still
    # updated — the run then still publishes something new. If chess-results
    # failed too, nothing in this run produced fresh data, and staying green
    # would deploy an unchanged site while hiding a total outage. The workflow
    # passes that step's real result (its outcome, i.e. before
    # continue-on-error is applied) in CHESS_RESULTS_OUTCOME.
    if os.environ.get("CHESS_RESULTS_OUTCOME") == "failure":
        gha_annotate(
            "error",
            "chess-results also failed this run — both sources are unavailable, "
            "so there is nothing fresh to publish. Failing the workflow.",
        )
        sys.exit(1)

    print("[WARN] Republishing the existing FIDE archive unchanged (no misses counted).")
    fide_archive = load_json(FIDE_ARCHIVE_PATH, [])
    if not fide_archive:
        gha_annotate("warning", "No FIDE archive on disk; leaving tournaments.json to the chess-results scraper.")
        return
    today = date.today().isoformat()
    for t in fide_archive:
        t["status"] = "concluded" if t["startDate"] <= today else "upcoming"
    combined = build_combined_output(fide_archive, load_json(OUTPUT_PATH, []))
    write_output(combined)


def main():
    fide_archive = load_json(FIDE_ARCHIVE_PATH, [])
    detail_cache = load_json(FIDE_DETAILS_PATH, {})

    # Seed the cache from the archive on the first run after it was
    # introduced, so an existing archive doesn't trigger a full re-fetch.
    # Only "organizerRaw" is usable as the organizer here — "organizer" may
    # have been rewritten to a club name by a previous run's mapping.
    for t in fide_archive:
        event_id = t["id"].replace("fide-", "")
        if event_id in detail_cache or not t.get("organizerRaw"):
            continue
        detail_cache[event_id] = {
            "endDate": t.get("endDate"),
            "timeControlRaw": t.get("timeControlRaw"),
            "organizer": t.get("organizerRaw"),
            "organizerProfileId": t.get("organizerProfileId"),
            "playersRegistered": t.get("playersRegistered"),
        }

    organizers = load_organizers()

    all_tournaments = []
    considered_isos = set()  # countries fetched successfully and above their floor this run
    fetched_ids_this_run = set()  # union of current list-feed ids, across successfully fetched countries only

    for country in COUNTRIES:
        print(f"[INFO] Fetching FIDE {country['name']} tournament list...")
        try:
            raw_rows = fetch_list(country["code"])
        except (requests.RequestException, ValueError, KeyError) as e:
            gha_annotate("warning", f"{country['name']}: could not fetch the FIDE list: {type(e).__name__}: {e}")
            continue

        rows = parse_rows(raw_rows)
        print(f"[INFO] {country['name']}: {len(rows)} upcoming rows out of {len(raw_rows)} total.")

        if len(rows) < country["min_tournaments"] and any(
            t.get("countryCode") == country["iso"] for t in fide_archive
        ):
            # Same reasoning as republish_archive_unchanged(), scoped to just
            # this country: a suspiciously thin feed is a reason not to trust
            # *this* scrape for *this* country, not a reason to touch its
            # existing archive entries or hold back the other countries.
            gha_annotate(
                "warning",
                f"{country['name']}: only {len(rows)} upcoming rows, below the safety floor of "
                f"{country['min_tournaments']} — leaving this country's archive entries unchanged.",
            )
            continue

        new_event_ids = {r["eventId"] for r in rows} - set(detail_cache)
        print(f"[INFO] {country['name']}: fetching detail pages for {len(new_event_ids)} newly-seen events "
              f"({len(detail_cache)} already cached).")
        for event_id in new_event_ids:
            detail = fetch_detail(event_id, country["code"])
            if detail:
                detail_cache[event_id] = detail

        all_tournaments.extend(build_tournaments(rows, detail_cache, organizers, country))
        considered_isos.add(country["iso"])
        fetched_ids_this_run.update(r["eventId"] for r in rows)

    if not considered_isos:
        republish_archive_unchanged(
            "Every FIDE country failed to fetch or came in below its safety floor this run."
        )
        return

    # Persist the cache, pruned to events still present in the list feed of a
    # country actually fetched this run, plus every id belonging to a country
    # that was skipped (fetch failed, or below floor) — we don't know their
    # current ids without a fresh fetch, so keep what's cached rather than
    # losing it and re-fetching needlessly once that country recovers.
    skipped_isos = {c["iso"] for c in COUNTRIES} - considered_isos
    retained_ids = fetched_ids_this_run | {
        t["id"].replace("fide-", "") for t in fide_archive if t.get("countryCode") in skipped_isos
    }
    pruned_cache = {k: v for k, v in detail_cache.items() if k in retained_ids}
    FIDE_DETAILS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FIDE_DETAILS_PATH, "w", encoding="utf-8") as f:
        json.dump(pruned_cache, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[INFO] Detail cache: {len(pruned_cache)} events "
          f"({len(detail_cache) - len(pruned_cache)} pruned). Written to {FIDE_DETAILS_PATH}")

    merged = merge_into_archive(all_tournaments, fide_archive, considered_isos)
    FIDE_ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FIDE_ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"[INFO] FIDE archive updated: {len(merged)} total entries. Written to {FIDE_ARCHIVE_PATH}")

    write_output(build_combined_output(merged, load_json(OUTPUT_PATH, [])))


if __name__ == "__main__":
    main()
