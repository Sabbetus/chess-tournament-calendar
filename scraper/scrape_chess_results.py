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
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

# IndexNow submission is handled by the deploy workflow (.github/workflows/
# deploy.yml), which runs after the site is live so engines don't crawl
# not-yet-deployed URLs.

OUTPUT_PATH = Path(__file__).parent.parent / "public" / "data" / "tournaments.json"
ARCHIVE_PATH = Path(__file__).parent.parent / "public" / "data" / "archive.json"
META_PATH = Path(__file__).parent.parent / "public" / "data" / "meta.json"
SEARCH_URL = "https://chess-results.com/TurnierSuche.aspx?lan=1"
BASE_URL = "https://chess-results.com/"
MIN_DURATION_DAYS = 1
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
    "TPE": "TW",
    "SRI": "LK", "NPL": "NP", "UZB": "UZ", "KGZ": "KG", "TKM": "TM",
    "MGL": "MN", "UAE": "AE", "QAT": "QA", "KUW": "KW", "KSA": "SA",
    "IRI": "IR", "IRQ": "IQ", "JOR": "JO", "LBN": "LB", "SYR": "SY",
    "AND": "AD", "CAT": "ES", "MDV": "MV", "ALG": "DZ",
    "URU": "UY", "BOT": "BW", "GCI": "GG", "ECU": "EC",
    "CIV": "CI", "CPV": "CV", "CRC": "CR", "CUB": "CU", "DOM": "DO",
    "FAI": "FO", "GUA": "GT", "HKG": "HK", "KEN": "KE", "KOS": "XK",
    "NZL": "NZ", "OMA": "OM", "PAN": "PA", "PUR": "PR", "ZAM": "ZM",
    "BRN": "BH", "HON": "HN", "JAM": "JM", "LCA": "LC", "MNC": "MC",
    "NCA": "NI", "NEP": "NP", "NGR": "NG", "PLE": "PS", "TTO": "TT",
    "UGA": "UG", "ZIM": "ZW",
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
    "TPE": "Taiwan",
    "PAK": "Pakistan", "BAN": "Bangladesh", "SRI": "Sri Lanka",
    "NPL": "Nepal", "MGL": "Mongolia", "UZB": "Uzbekistan",
    "KGZ": "Kyrgyzstan", "TKM": "Turkmenistan", "UAE": "United Arab Emirates",
    "QAT": "Qatar", "KUW": "Kuwait", "KSA": "Saudi Arabia",
    "IRI": "Iran", "IRQ": "Iraq", "JOR": "Jordan", "LBN": "Lebanon",
    "SYR": "Syria", "MEX": "Mexico", "COL": "Colombia", "PER": "Peru",
    "CHI": "Chile", "VEN": "Venezuela", "URU": "Uruguay", "ECU": "Ecuador",
    "BOT": "Botswana", "GCI": "Guernsey", "ACC": "ASEAN",
    "CIV": "Côte d'Ivoire", "CPV": "Cape Verde", "CRC": "Costa Rica",
    "CUB": "Cuba", "DOM": "Dominican Republic", "FAI": "Faroe Islands",
    "GUA": "Guatemala", "HKG": "Hong Kong", "KEN": "Kenya", "KOS": "Kosovo",
    "NZL": "New Zealand", "OMA": "Oman", "PAN": "Panama",
    "PUR": "Puerto Rico", "ZAM": "Zambia",
    "BRN": "Bahrain", "JAM": "Jamaica", "LCA": "Saint Lucia",
    "MNC": "Monaco", "NCA": "Nicaragua", "NEP": "Nepal",
    "NGR": "Nigeria", "PLE": "Palestine", "UGA": "Uganda",
    "HON": "Honduras", "TTO": "Trinidad and Tobago", "ZIM": "Zimbabwe",
    "ZZZ": "Unknown",
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
    """Keep a tournament if its name is predominantly Latin-script *letters*.

    We only inspect letters — digits, punctuation, whitespace, and symbols/emoji
    (e.g. ♚ ♛ ⚡ wrapped around an otherwise plain-Latin title) are ignored, so a
    few decorative characters can't disqualify an entry. Names that are mostly
    non-Latin script (Cyrillic, Greek, CJK, Arabic, …) are still excluded.
    """
    latin = non_latin = 0
    for c in name:
        if not c.isalpha():
            continue
        try:
            if "LATIN" in unicodedata.name(c):
                latin += 1
            else:
                non_latin += 1
        except ValueError:
            non_latin += 1
    if latin + non_latin == 0:
        return True  # no letters at all (numbers/symbols only) — don't exclude
    return latin >= non_latin



def slugify(name, tnr_id):
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    tnr_num = tnr_id.replace("chess-results-", "").replace("cr-", "")
    return f"{slug}-{tnr_num}"


def parse_int(s):
    if not s:
        return None
    cleaned = re.sub(r"[^\d]", "", str(s))
    return int(cleaned) if cleaned else None


def parse_rows(page, time_control="1"):
    # chess-results' own search bucket is the source of truth for the time
    # control: window "2" is Rapid, everything else (we only query "1") is
    # Standard/Classical. This is far more reliable than regex-parsing the
    # freeform time-control string (e.g. "10 min + 5 sec", which chess-results
    # classes as Rapid but a naive parser reads as Blitz).
    tc_label = "Rapid" if time_control == "2" else "Classical"
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
        slug = slugify(name, tid)

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

        # City at index 12 — may contain ", Country Name" suffix for team events
        city = texts[12] if len(texts) > 12 else ""
        all_country_names = set(FIDE_TO_NAME.values())
        for known_country in sorted(all_country_names, key=len, reverse=True):
            suffix = f", {known_country}"
            if city.endswith(suffix):
                city = city[: -len(suffix)].strip()
                # Override country only if current mapping looks wrong
                fide_for_city = next(
                    (k for k, v in FIDE_TO_NAME.items() if v == known_country), None
                )
                if fide_for_city and known_country != country_name:
                    country_name = known_country
                    iso_code = FIDE_TO_ISO.get(fide_for_city, iso_code)
                break

        # Rounds at index 7 (may be empty or like "7")
        rounds = parse_int(texts[7]) if len(texts) > 7 else None
        if rounds and not (3 <= rounds <= 30):
            rounds = None

        # Players at index 17
        players = parse_int(texts[17]) if len(texts) > 17 else None

        raw_tc = texts[13] if len(texts) > 13 else None
        tournaments.append({
            "id": tid,
            "slug": slug,
            "name": name,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "city": city,
            "country": country_name,
            "countryCode": iso_code,
            "rounds": rounds,
            "timeControl": tc_label,
            "timeControlRaw": raw_tc if raw_tc else None,
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


def search_windows(today: date):
    """Return four search windows as (date_from, date_to, time_control) tuples."""
    one_month_out = today + timedelta(days=31)
    one_year_out = today + timedelta(days=365)
    far_from = one_month_out + timedelta(days=1)
    return [
        (today,      one_month_out, "1"),  # Standard, next month
        (today,      one_month_out, "2"),  # Rapid, next month
        (far_from,   one_year_out,  "1"),  # Standard, months 2-12
        (far_from,   one_year_out,  "2"),  # Rapid, months 2-12
    ]


def remove_cookie_banner(page):
    """Strip the Cookiebot consent overlay. It otherwise sits on top of the
    search form and can swallow the first submit, making a whole search window
    come back empty (see the retry in scrape())."""
    page.evaluate("document.querySelectorAll('[id*=\"Cookiebot\"],[id*=\"cookiebot\"]').forEach(e => e.remove());")


def search_window(page, date_from: str, date_to: str, time_control: str = "1"):
    page.fill('input[name="ctl00$P1$txt_von_tag"]', date_from)
    page.fill('input[name="ctl00$P1$txt_bis_tag"]', date_to)
    page.select_option('select[name="ctl00$P1$combo_bedenkzeit"]', time_control)
    page.select_option('select[name="ctl00$P1$combo_art"]', "0")  # Swiss-System only
    page.select_option('select[name="ctl00$P1$combo_anzahl_zeilen"]', "5")  # 2000 rows
    tc_label = {"0": "All", "1": "Standard", "2": "Rapid"}.get(time_control, time_control)
    print(f"[INFO] Searching {date_from} → {date_to} ({tc_label}, Swiss-System)…")
    page.click('input[name="ctl00$P1$cb_suchen"]', force=True)
    page.wait_for_load_state("domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    remove_cookie_banner(page)


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
        # Clear the consent overlay up front so the very first search isn't
        # swallowed by it (this previously dropped the entire near-term Standard
        # window in CI, silently losing all upcoming classical tournaments).
        page.wait_for_timeout(1000)
        remove_cookie_banner(page)

        all_tournaments = {}  # id → tournament, deduped across windows
        for win_from, win_to, time_control in search_windows(today):
            # None of our searches should ever return 0 rows; if one does it's a
            # transient failure (overlay, slow load), so retry before trusting it.
            batch = []
            for attempt in range(1, 4):
                search_window(page, win_from.strftime("%Y-%m-%d"), win_to.strftime("%Y-%m-%d"), time_control)
                batch = parse_rows(page, time_control)
                if batch:
                    break
                print(f"[WARN] Window returned 0 rows (attempt {attempt}/3); retrying…")
                page.wait_for_timeout(2000)
            if not batch:
                print("[ERROR] Window still empty after 3 attempts — aborting to avoid writing a partial dataset.")
                browser.close()
                sys.exit(1)
            for t in batch:
                all_tournaments[t["id"]] = t

        browser.close()

    tournaments = sorted(all_tournaments.values(), key=lambda t: t["startDate"])
    return tournaments


MIN_ABSOLUTE_TOURNAMENTS = 200


def previous_tournament_count():
    if not OUTPUT_PATH.exists():
        return None
    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            return len(json.load(f))
    except (json.JSONDecodeError, OSError):
        return None


def load_archive():
    if ARCHIVE_PATH.exists():
        try:
            with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    # Seed from tournaments.json on first run
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            print(f"[INFO] Seeding archive from {OUTPUT_PATH} ({len(existing)} entries).")
            return existing
        except (json.JSONDecodeError, OSError):
            pass
    return []


def merge_into_archive(scraped, archive):
    today = date.today().isoformat()
    by_id = {t["id"]: t for t in archive}

    for t in scraped:
        existing = by_id.get(t["id"])
        if existing:
            existing.update({
                "name": t["name"],
                "slug": t["slug"],
                "startDate": t["startDate"],
                "endDate": t["endDate"],
                "city": t["city"],
                "country": t["country"],
                "countryCode": t["countryCode"],
                "rounds": t["rounds"],
                "timeControl": t["timeControl"],
                "timeControlRaw": t["timeControlRaw"],
                "playersRegistered": t["playersRegistered"],
                "registrationUrl": t["registrationUrl"],
                "websiteUrl": t["websiteUrl"],
                "lastSeen": today,
            })
        else:
            t["firstSeen"] = today
            t["lastSeen"] = today
            by_id[t["id"]] = t

    for t in by_id.values():
        t["status"] = "concluded" if t["startDate"] <= today else "upcoming"
        # Ensure slug exists on entries seeded from old data
        if "slug" not in t:
            t["slug"] = slugify(t["name"], t["id"])
        # Ensure new fields exist on old entries
        if "timeControlRaw" not in t:
            t["timeControlRaw"] = None
        if "firstSeen" not in t:
            t["firstSeen"] = today
        if "lastSeen" not in t:
            t["lastSeen"] = today

    return sorted(by_id.values(), key=lambda t: t["startDate"])


def main():
    tournaments = scrape()
    print(f"[INFO] {len(tournaments)} tournaments pass the {MIN_DURATION_DAYS}-{MAX_DURATION_DAYS} day filter.")

    previous_count = previous_tournament_count()
    floor = max(MIN_ABSOLUTE_TOURNAMENTS, (previous_count or 0) // 2)
    if len(tournaments) < floor:
        print(
            f"[ERROR] Only {len(tournaments)} tournaments found, which is below the "
            f"safety floor of {floor} (previous run had {previous_count}). "
            f"This looks like a partial scrape failure (e.g. a search window "
            f"returned 0 results unexpectedly). Refusing to overwrite "
            f"{OUTPUT_PATH} and {META_PATH}."
        )
        sys.exit(1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write upcoming-only list (front page payload)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(tournaments, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Written to {OUTPUT_PATH}")

    # Merge into archive
    archive = load_archive()
    merged = merge_into_archive(tournaments, archive)
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Archive updated: {len(merged)} total entries ({sum(1 for t in merged if t['status'] == 'upcoming')} upcoming, {sum(1 for t in merged if t['status'] == 'concluded')} concluded). Written to {ARCHIVE_PATH}")

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump({"lastUpdated": datetime.utcnow().isoformat() + "Z"}, f, indent=2)
    print(f"[INFO] Written to {META_PATH}")


if __name__ == "__main__":
    main()
