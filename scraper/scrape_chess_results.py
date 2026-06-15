"""
Scraper for chess-results.com tournament listings.

Fetches upcoming tournaments with duration >= 7 days and writes
the result to data/tournaments.json in the repo root.

chess-results.com tournament search URL:
  https://chess-results.com/TournamentSearch.aspx
The search form POSTs and returns HTML; we parse the results table.
"""

import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://chess-results.com/"
SEARCH_URL = "https://chess-results.com/TournamentSearch.aspx"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "tournaments.json"

MIN_DURATION_DAYS = 7
REQUEST_DELAY = 1.5  # seconds between requests, be polite

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ChessTournamentCalendarBot/1.0; "
        "+https://github.com/sabbe-the-technomage/chess-tournament-calendar)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

COUNTRY_TO_CODE = {
    "Finland": "FI", "Sweden": "SE", "Norway": "NO", "Denmark": "DK",
    "Iceland": "IS", "Germany": "DE", "France": "FR", "Spain": "ES",
    "Italy": "IT", "Netherlands": "NL", "Belgium": "BE", "Austria": "AT",
    "Switzerland": "CH", "Poland": "PL", "Czech Republic": "CZ",
    "Hungary": "HU", "Romania": "RO", "Bulgaria": "BG", "Serbia": "RS",
    "Croatia": "HR", "Greece": "GR", "Portugal": "PT", "United Kingdom": "GB",
    "Ireland": "IE", "Russia": "RU", "Ukraine": "UA", "United States": "US",
    "Canada": "CA", "India": "IN", "China": "CN", "Japan": "JP",
    "Brazil": "BR", "Argentina": "AR", "Australia": "AU",
    "Turkey": "TR", "Israel": "IL", "Armenia": "AM", "Georgia": "GE",
    "Azerbaijan": "AZ", "Kazakhstan": "KZ",
}


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def parse_date(raw: str) -> date | None:
    """Parse dates in formats like '04.10.2026' or '2026-10-04'."""
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def duration_days(start: date, end: date) -> int:
    return (end - start).days + 1


def country_code(country: str) -> str | None:
    return COUNTRY_TO_CODE.get(country)


def parse_int(s: str | None) -> int | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d]", "", s)
    return int(cleaned) if cleaned else None


def parse_prize(s: str | None) -> tuple[int | None, str | None]:
    """Return (amount, currency) from strings like '€5.000' or '$ 10,000'."""
    if not s:
        return None, None
    s = s.strip()
    currency = None
    if "€" in s or "EUR" in s.upper():
        currency = "EUR"
    elif "$" in s or "USD" in s.upper():
        currency = "USD"
    elif "£" in s or "GBP" in s.upper():
        currency = "GBP"
    amount = parse_int(s)
    return amount, currency


def fetch_search_page(session: requests.Session, page: int = 0) -> BeautifulSoup | None:
    """
    chess-results.com uses ASP.NET WebForms with ViewState.
    We need to first GET the page to get the ViewState tokens,
    then POST with search parameters.
    """
    try:
        resp = session.get(SEARCH_URL, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] GET {SEARCH_URL}: {e}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract ASP.NET form state
    viewstate = soup.find("input", {"id": "__VIEWSTATE"})
    viewstate_gen = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})
    event_validation = soup.find("input", {"id": "__EVENTVALIDATION"})

    today = date.today()
    date_from = today.strftime("%d.%m.%Y")
    date_to = (today + timedelta(days=365)).strftime("%d.%m.%Y")

    payload = {
        "__VIEWSTATE": viewstate["value"] if viewstate else "",
        "__VIEWSTATEGENERATOR": viewstate_gen["value"] if viewstate_gen else "",
        "__EVENTVALIDATION": event_validation["value"] if event_validation else "",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        # Search fields — target future events
        "ctl00$ContentPlaceHolder1$txt_dv": date_from,
        "ctl00$ContentPlaceHolder1$txt_db": date_to,
        "ctl00$ContentPlaceHolder1$txt_na": "",
        "ctl00$ContentPlaceHolder1$ddl_la": "0",  # language: all
        "ctl00$ContentPlaceHolder1$ddl_fe": "0",  # federation: all
        "ctl00$ContentPlaceHolder1$btn_su": "Search",
    }

    try:
        time.sleep(REQUEST_DELAY)
        resp = session.post(SEARCH_URL, data=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] POST {SEARCH_URL}: {e}", file=sys.stderr)
        return None

    return BeautifulSoup(resp.text, "html.parser")


def parse_tournament_row(row) -> dict | None:
    """Parse a single <tr> from the search results table."""
    cells = row.find_all("td")
    if len(cells) < 5:
        return None

    try:
        # Typical columns: Nr | Name | City | Country | Start | End | Rounds | Players
        # Column order varies; we find by position and content heuristics
        texts = [c.get_text(strip=True) for c in cells]

        # Find the link (tournament detail URL)
        link_tag = row.find("a", href=True)
        detail_url = urljoin(BASE_URL, link_tag["href"]) if link_tag else None

        # Name is usually in the cell containing the link
        name = link_tag.get_text(strip=True) if link_tag else texts[1]

        # Try to extract dates — look for cells matching date pattern
        date_pattern = re.compile(r"\d{2}\.\d{2}\.\d{4}")
        dates_found = [(i, parse_date(t)) for i, t in enumerate(texts) if date_pattern.match(t)]

        if len(dates_found) < 2:
            return None

        start_date = dates_found[0][1]
        end_date = dates_found[1][1]

        if not start_date or not end_date or end_date < date.today():
            return None  # skip past tournaments

        days = duration_days(start_date, end_date)
        if days < MIN_DURATION_DAYS:
            return None

        # Location: look for city/country columns (non-date, non-numeric text)
        location_candidates = [
            t for i, t in enumerate(texts)
            if t and not date_pattern.match(t) and not t.isdigit() and t != name
        ]
        city = location_candidates[0] if len(location_candidates) > 0 else ""
        country = location_candidates[1] if len(location_candidates) > 1 else ""

        # Rounds: look for small integer
        rounds = None
        for t in texts:
            if t.isdigit() and 3 <= int(t) <= 20:
                rounds = int(t)
                break

        # Players: look for larger integer
        players = None
        for t in texts:
            if t.isdigit() and int(t) > 20:
                players = int(t)
                break

        tid = re.search(r"[Tt]NR=(\d+)", detail_url) if detail_url else None
        tournament_id = f"chess-results-{tid.group(1)}" if tid else f"chess-results-{hash(name + str(start_date))}"

        return {
            "id": tournament_id,
            "name": name,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "city": city,
            "country": country,
            "countryCode": country_code(country),
            "rounds": rounds,
            "timeControl": None,
            "playersRegistered": players,
            "prizePool": None,
            "currency": None,
            "ratingRequirement": None,
            "open": True,
            "registrationOpen": True,
            "registrationUrl": detail_url,
            "websiteUrl": detail_url,
            "description": None,
            "source": "chess-results",
        }

    except Exception as e:
        print(f"[WARN] Failed to parse row: {e}", file=sys.stderr)
        return None


def fetch_all_tournaments(session: requests.Session) -> list[dict]:
    print("[INFO] Fetching tournament search results…")
    soup = fetch_search_page(session)
    if not soup:
        return []

    # Find results table
    table = soup.find("table", {"id": re.compile(r"ctl00.*GridView", re.I)})
    if not table:
        # Fallback: find any table with many rows
        tables = soup.find_all("table")
        table = max(tables, key=lambda t: len(t.find_all("tr")), default=None)

    if not table:
        print("[WARN] No results table found.", file=sys.stderr)
        return []

    rows = table.find_all("tr")[1:]  # skip header row
    print(f"[INFO] Found {len(rows)} rows in results table.")

    tournaments = []
    for row in rows:
        t = parse_tournament_row(row)
        if t:
            tournaments.append(t)

    # Sort by start date
    tournaments.sort(key=lambda t: t["startDate"])
    print(f"[INFO] {len(tournaments)} tournaments pass the {MIN_DURATION_DAYS}+ day filter.")
    return tournaments


def main():
    session = get_session()
    tournaments = fetch_all_tournaments(session)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(tournaments, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Wrote {len(tournaments)} tournaments to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
