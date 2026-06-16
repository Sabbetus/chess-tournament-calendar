"""
Scraper for chess-results.com using Playwright (headless browser).

Fetches upcoming tournaments with duration >= 7 days and writes
the result to data/tournaments.json in the repo root.

Result row structure (classes CRg1/CRg2):
  [0] row number
  [1] name (with link tnrNNNNN.aspx)
  [2] country code (3-letter)
  [3] flag div
  [4] "X Days Y Hours" (time since last update)
  [5] start date YYYY/MM/DD
  [6] end date YYYY/MM/DD
  [7] rounds (may be empty)
  [8] organiser
  [9] chief arbiter
  [10] arbiter
  [11] arbiter 2
  [12] city
  [13] time control
  [14] country code again
  [15] ?
  [16] online flag
  [17] players registered
  [18] TNR number
  [19] FIDE event id
"""

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path(__file__).parent.parent / "public" / "data" / "tournaments.json"
META_PATH = Path(__file__).parent.parent / "public" / "data" / "meta.json"
SEARCH_URL = "https://chess-results.com/TurnierSuche.aspx?lan=1"
BASE_URL = "https://chess-results.com/"
MIN_DURATION_DAYS = 2
MAX_DURATION_DAYS = 10

# 3-letter FIDE codes to ISO 2-letter
FIDE_TO_ISO = {
    "FIN": "FI", "SWE": "SE", "NOR": "NO", "DEN": "DK", "ISL": "IS",
    "GER": "DE", "FRA": "FR", "ESP": "ES", "ITA": "IT", "NED": "NL",
    "BEL": "BE", "AUT": "AT", "SUI": "CH", "POL": "PL", "CZE": "CZ",
    "HUN": "HU", "ROU": "RO", "BUL": "BG", "SRB": "RS", "CRO": "HR",
    "GRE": "GR", "POR": "PT", "ENG": "GB", "SCO": "GB", "WLS": "GB",
    "GBR": "GB", "IRL": "IE", "RUS": "RU", "UKR": "UA", "USA": "US",
    "CAN": "CA", "IND": "IN", "CHN": "CN", "JPN": "JP", "BRA": "BR",
    "ARG": "AR", "AUS": "AU", "TUR": "TR", "ISR": "IL", "ARM": "AM",
    "GEO": "GE", "AZE": "AZ", "KAZ": "KZ", "SVK": "SK", "SLO": "SI",
    "LAT": "LV", "LTU": "LT", "EST": "EE", "BLR": "BY", "MDA": "MD",
    "ALB": "AL", "MKD": "MK", "BIH": "BA", "MNE": "ME", "LUX": "LU",
    "MLT": "MT", "CYP": "CY", "KOR": "KR", "RSA": "ZA", "EGY": "EG",
    "MAR": "MA", "TUN": "TN", "MEX": "MX", "COL": "CO", "PER": "PE",
    "CHI": "CL", "VEN": "VE", "PHI": "PH", "INA": "ID", "MAS": "MY",
    "SGP": "SG", "THA": "TH", "VIE": "VN", "PAK": "PK", "BAN": "BD",
    "SRI": "LK", "NPL": "NP", "UZB": "UZ", "KGZ": "KG", "TKM": "TM",
    "MGL": "MN", "UAE": "AE", "QAT": "QA", "KUW": "KW", "KSA": "SA",
    "IRI": "IR", "IRQ": "IQ", "JOR": "JO", "LBN": "LB", "SYR": "SY",
    "AND": "AD", "CAT": "ES", "MDV": "MV", "ALG": "DZ",
    "URU": "UY", "BOT": "BW", "GCI": "GG", "ECU": "EC",
}

FIDE_TO_NAME = {
    "FIN": "Finland", "SWE": "Sweden", "NOR": "Norway", "DEN": "Denmark",
    "ISL": "Iceland", "GER": "Germany", "FRA": "France", "ESP": "Spain",
    "ITA": "Italy", "NED": "Netherlands", "BEL": "Belgium", "AUT": "Austria",
    "SUI": "Switzerland", "POL": "Poland", "CZE": "Czech Republic",
    "HUN": "Hungary", "ROU": "Romania", "BUL": "Bulgaria", "SRB": "Serbia",
    "CRO": "Croatia", "GRE": "Greece", "POR": "Portugal", "ENG": "England",
    "SCO": "Scotland", "WLS": "Wales", "GBR": "United Kingdom",
    "IRL": "Ireland", "RUS": "Russia", "UKR": "Ukraine", "USA": "United States",
    "CAN": "Canada", "IND": "India", "CHN": "China", "JPN": "Japan",
    "BRA": "Brazil", "ARG": "Argentina", "AUS": "Australia",
    "TUR": "Türkiye", "ISR": "Israel", "ARM": "Armenia", "GEO": "Georgia",
    "AZE": "Azerbaijan", "KAZ": "Kazakhstan", "SVK": "Slovakia",
    "SLO": "Slovenia", "LAT": "Latvia", "LTU": "Lithuania", "EST": "Estonia",
    "BLR": "Belarus", "ALB": "Albania", "MKD": "North Macedonia",
    "BIH": "Bosnia & Herzegovina", "MNE": "Montenegro", "LUX": "Luxembourg",
    "MLT": "Malta", "CYP": "Cyprus", "AND": "Andorra", "CAT": "Catalonia",
    "MAR": "Morocco", "MDV": "Maldives", "RSA": "South Africa",
    "THA": "Thailand", "VIE": "Vietnam", "EGY": "Egypt", "TUN": "Tunisia",
    "ALG": "Algeria", "KOR": "South Korea", "MAS": "Malaysia",
    "PHI": "Philippines", "INA": "Indonesia", "SGP": "Singapore",
    "PAK": "Pakistan", "BAN": "Bangladesh", "SRI": "Sri Lanka",
    "NPL": "Nepal", "MGL": "Mongolia", "UZB": "Uzbekistan",
    "KGZ": "Kyrgyzstan", "TKM": "Turkmenistan", "UAE": "UAE",
    "QAT": "Qatar", "KUW": "Kuwait", "KSA": "Saudi Arabia",
    "IRI": "Iran", "IRQ": "Iraq", "JOR": "Jordan", "LBN": "Lebanon",
    "SYR": "Syria", "MEX": "Mexico", "COL": "Colombia", "PER": "Peru",
    "CHI": "Chile", "VEN": "Venezuela", "URU": "Uruguay", "ECU": "Ecuador",
    "BOT": "Botswana", "GCI": "Guernsey", "ACC": "ASEAN",
}


def parse_date(raw):
    raw = raw.strip()
    for fmt in ("%Y/%m/%d", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def duration_days(start, end):
    return (end - start).days + 1


def is_latin_name(name):
    return all(ord(c) <= 0x024F for c in name)



TIME_CONTROL_MAP = [
    (re.compile(r'\b(blitz|blitz)\b', re.I), 'Blitz'),
    (re.compile(r'\b(rapid|schnell|rapide)\b', re.I), 'Rapid'),
    # Classical: 90min or more, or explicit keyword
    (re.compile(r'(classical|klassisch|classique|\b(90|100|110|120)\s*(\'|min|m\b))', re.I), 'Classical'),
    # Rapid by time: 15-60 min
    (re.compile(r'\b(15|20|25|30|45|60)\s*(\'|min|m\b)', re.I), 'Rapid'),
    # Blitz by time: under 15
    (re.compile(r'\b([3-9]|10|12)\s*(\'|min|m\b)', re.I), 'Blitz'),
]

def normalize_time_control(raw):
    if not raw:
        return None
    for pattern, label in TIME_CONTROL_MAP:
        if pattern.search(raw):
            return label
    return None

def parse_int(s):
    if not s:
        return None
    cleaned = re.sub(r"[^\d]", "", str(s))
    return int(cleaned) if cleaned else None


def parse_rows(page):
    today = date.today()
    tournaments = []
    seen_ids = set()

    rows = page.query_selector_all("tr.CRg1, tr.CRg2")
    print(f"[INFO] Found {len(rows)} result rows.")

    for row in rows:
        cells = row.query_selector_all("td")
        if len(cells) < 7:
            continue

        texts = [c.inner_text().strip() for c in cells]

        # Dates at index 5 and 6
        start_date = parse_date(texts[5]) if len(texts) > 5 else None
        end_date   = parse_date(texts[6]) if len(texts) > 6 else None

        if not start_date or not end_date:
            continue
        if start_date <= today:
            continue
        if start_date > end_date:
            continue

        days = duration_days(start_date, end_date)
        if days < MIN_DURATION_DAYS or days > MAX_DURATION_DAYS:
            continue

        # Name and link
        link_el = row.query_selector("a[href*='tnr']")
        name = link_el.inner_text().strip() if link_el else texts[1]
        href = link_el.get_attribute("href") if link_el else None
        detail_url = urljoin(BASE_URL, href) if href else None

        tnr_match = re.search(r"tnr(\d+)", detail_url or "")
        tid = f"chess-results-{tnr_match.group(1)}" if tnr_match else f"cr-{abs(hash(name + str(start_date))) % 10**8}"

        if not is_latin_name(name):
            continue

        if tid in seen_ids:
            continue
        seen_ids.add(tid)

        # Country: 3-letter FIDE code at index 2
        fide_code = texts[2] if len(texts) > 2 else ""
        if fide_code == "XXX":
            fide_code = ""
        country_name = FIDE_TO_NAME.get(fide_code, fide_code) if fide_code else ""
        iso_code = FIDE_TO_ISO.get(fide_code)

        # City at index 12
        city = texts[12] if len(texts) > 12 else ""

        # Rounds at index 7 (may be empty or like "7")
        rounds = parse_int(texts[7]) if len(texts) > 7 else None
        if rounds and not (3 <= rounds <= 30):
            rounds = None

        # Players at index 17
        players = parse_int(texts[17]) if len(texts) > 17 else None

        tournaments.append({
            "id": tid,
            "name": name,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "city": city,
            "country": country_name,
            "countryCode": iso_code,
            "rounds": rounds,
            "timeControl": normalize_time_control(texts[13] if len(texts) > 13 else None),
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
        })

    tournaments.sort(key=lambda t: t["startDate"])
    return tournaments


def month_windows(start: date, days_ahead: int = 365):
    """Yield (from_date, to_date) pairs covering one quarter each."""
    current = start
    end_limit = start + timedelta(days=days_ahead)
    while current < end_limit:
        window_end = min(current + timedelta(days=91), end_limit)
        yield current, window_end
        current = window_end + timedelta(days=1)


def search_window(page, date_from: str, date_to: str):
    page.fill('input[name="ctl00$P1$txt_von_tag"]', date_from)
    page.fill('input[name="ctl00$P1$txt_bis_tag"]', date_to)
    page.select_option('select[name="ctl00$P1$combo_bedenkzeit"]', "1")  # Standard only
    page.select_option('select[name="ctl00$P1$combo_anzahl_zeilen"]', "5")  # 2000 rows
    print(f"[INFO] Searching {date_from} → {date_to}…")
    page.click('input[name="ctl00$P1$cb_suchen"]', force=True)
    page.wait_for_load_state("domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    page.evaluate("document.querySelectorAll('[id*=\"Cookiebot\"],[id*=\"cookiebot\"]').forEach(e => e.remove());")


def scrape():
    today = date.today()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        context.add_cookies([{
            "name": "CookieConsent",
            "value": "{stamp:%27-1%27%2Cnecessary:true%2Cpreferences:true%2Cstatistics:true%2Cmarketing:true%2Cmethod:%27implied%27%2Cver:1%2Cutc:1718496000000%2Cregion:%27fi%27}",
            "domain": ".chess-results.com",
            "path": "/",
        }])

        page = context.new_page()
        print(f"[INFO] Loading {SEARCH_URL}")
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)

        all_tournaments = {}  # id → tournament, deduped across windows
        for win_from, win_to in month_windows(today):
            search_window(page, win_from.strftime("%Y-%m-%d"), win_to.strftime("%Y-%m-%d"))
            batch = parse_rows(page)
            for t in batch:
                all_tournaments[t["id"]] = t

        browser.close()

    tournaments = sorted(all_tournaments.values(), key=lambda t: t["startDate"])
    return tournaments


def main():
    tournaments = scrape()
    print(f"[INFO] {len(tournaments)} tournaments pass the {MIN_DURATION_DAYS}-{MAX_DURATION_DAYS} day filter.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(tournaments, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Written to {OUTPUT_PATH}")

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump({"lastUpdated": datetime.utcnow().isoformat() + "Z"}, f, indent=2)
    print(f"[INFO] Written to {META_PATH}")


if __name__ == "__main__":
    main()
