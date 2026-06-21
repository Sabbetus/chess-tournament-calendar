#!/usr/bin/env python3
"""
One-time (and reusable) IndexNow URL submission script.
Submits all tournament pages to Bing/IndexNow for fast indexing.
"""
import json
import urllib.request
import sys
import os

HOST = "chesstournamentcalendar.com"
KEY = "d3a6913ec3c84c58bf5edd4a2542ce02"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
INDEXNOW_URL = "https://api.indexnow.org/indexnow"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_slugs():
    urls = []

    # All archive tournament pages
    archive_path = os.path.join(BASE_DIR, "public", "data", "archive.json")
    with open(archive_path) as f:
        archive = json.load(f)
    for t in archive:
        if t.get("slug"):
            urls.append(f"https://{HOST}/tournament/{t['slug']}/")

    # Featured tournaments (Nordic Chess Festival etc.)
    featured_path = os.path.join(BASE_DIR, "data", "featured.json")
    with open(featured_path) as f:
        featured = json.load(f)
    for t in featured:
        if t.get("slug"):
            urls.append(f"https://{HOST}/tournament/{t['slug']}/")

    # Home page and static pages
    urls += [
        f"https://{HOST}/",
        f"https://{HOST}/contact/",
    ]

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
