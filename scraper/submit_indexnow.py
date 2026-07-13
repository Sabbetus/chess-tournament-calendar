#!/usr/bin/env python3
"""
One-time (and reusable) IndexNow URL submission script.
Submits all tournament pages to Bing/IndexNow for fast indexing.
"""
import json
import re
import unicodedata
import urllib.request
import sys
import os

HOST = "chesstournamentcalendar.com"
KEY = "d3a6913ec3c84c58bf5edd4a2542ce02"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
INDEXNOW_URL = "https://api.indexnow.org/indexnow"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


LANGS = ["es", "pt", "de", "cs", "fi"]


def slugify_location(name):
    # Mirrors src/lib/locationSlug.ts's slugifyLocation exactly.
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = n.lower()
    n = re.sub(r"[^a-z0-9]+", "-", n)
    return n.strip("-")


def load_continent_map():
    # Parse CONTINENT_MAP straight out of the TS source so this script can't
    # silently drift out of sync with the site's own continent assignments.
    path = os.path.join(BASE_DIR, "src", "lib", "continents.ts")
    content = open(path).read()
    m = re.search(r"CONTINENT_MAP.*?=\s*{(.*?)}", content, re.DOTALL)
    return dict(re.findall(r"([A-Z]{2}):'([A-Z]{2})'", m.group(1)))


def load_items():
    tournaments_path = os.path.join(BASE_DIR, "public", "data", "tournaments.json")
    with open(tournaments_path) as f:
        tournaments = json.load(f)
    featured_path = os.path.join(BASE_DIR, "data", "featured.json")
    with open(featured_path) as f:
        featured = json.load(f)
    return tournaments + featured


def location_urls(all_items=None):
    """Country + continent page URLs (all languages). Content on these pages
    changes on every scrape (tournaments come and go), not just when a brand
    new tournament first appears, so -- unlike tournament pages -- they're
    resubmitted unconditionally on every deploy (see deploy.yml)."""
    if all_items is None:
        all_items = load_items()
    urls = []

    # Country pages -- one per country with an ISO code (matches
    # getCountryGroups()'s own requirement in src/lib/locationGroups.ts).
    country_slugs = {
        slugify_location(t["country"])
        for t in all_items
        if t.get("country") and t.get("countryCode")
    }
    for slug in country_slugs:
        urls.append(f"https://{HOST}/country/{slug}/")
        for lang in LANGS:
            urls.append(f"https://{HOST}/{lang}/country/{slug}/")

    # Continent pages -- one per continent with at least one live tournament.
    continent_map = load_continent_map()
    continent_slugs_by_code = {
        "EU": "europe", "AS": "asia", "NA": "north-america",
        "SA": "south-america", "AF": "africa", "OC": "oceania",
    }
    active_continents = {
        continent_map[t["countryCode"]]
        for t in all_items
        if t.get("countryCode") and t["countryCode"] in continent_map
    }
    for code in active_continents:
        slug = continent_slugs_by_code.get(code)
        if not slug:
            continue
        urls.append(f"https://{HOST}/continent/{slug}/")
        for lang in LANGS:
            urls.append(f"https://{HOST}/{lang}/continent/{slug}/")

    return urls


def load_slugs():
    all_items = load_items()
    urls = []

    # Only currently-live (upcoming) tournament pages -- concluded tournaments
    # are intentionally noindex, so they shouldn't be submitted for indexing.
    slugs = [t["slug"] for t in all_items if t.get("slug")]
    for slug in slugs:
        urls.append(f"https://{HOST}/tournament/{slug}/")
        for lang in LANGS:
            urls.append(f"https://{HOST}/{lang}/tournament/{slug}/")

    urls += location_urls(all_items)

    # Home page, static pages, and their language variants
    urls += [f"https://{HOST}/", f"https://{HOST}/contact/"]
    for lang in LANGS:
        urls += [f"https://{HOST}/{lang}/", f"https://{HOST}/{lang}/contact/"]

    return urls


def submit(urls):
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        INDEXNOW_URL,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Response: {resp.status} {resp.reason}")
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)


def main():
    urls = load_slugs()
    # IndexNow accepts up to 10,000 URLs per request
    BATCH = 10000
    print(f"Submitting {len(urls)} URLs to IndexNow...")
    for i in range(0, len(urls), BATCH):
        batch = urls[i:i + BATCH]
        print(f"  Batch {i // BATCH + 1}: {len(batch)} URLs")
        submit(batch)
    print("Done.")


if __name__ == "__main__":
    main()
