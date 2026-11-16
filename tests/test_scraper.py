"""Tests for the chess-results filters. Run: python3 -m unittest discover tests"""
import sys
import types
import unittest
from pathlib import Path

# The parsers are pure; don't require Playwright just to import the module.
try:
    import playwright.sync_api  # noqa: F401
except ImportError:
    pw = types.ModuleType("playwright"); sync = types.ModuleType("playwright.sync_api")
    sync.sync_playwright = None; pw.sync_api = sync
    sys.modules.update({"playwright": pw, "playwright.sync_api": sync})

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))
import scrape_chess_results as s  # noqa: E402


class Blitz(unittest.TestCase):
    def test_totals(self):
        self.assertEqual(s.time_control_totals("15 min + 10 sec"), [25])
        self.assertEqual(s.time_control_totals("3+2"), [5])
        self.assertEqual(s.time_control_totals("90 min + 30 sec"), [120])
        self.assertEqual(s.time_control_totals(""), [])

    def test_blitz_dropped(self):
        self.assertTrue(s.is_blitz_only("Friday Blitz", "3+2"))
        self.assertTrue(s.is_blitz_only("Open", "5 min + 3 sec"))

    def test_rapid_and_classical_kept(self):
        self.assertFalse(s.is_blitz_only("Open", "15 min + 10 sec"))
        self.assertFalse(s.is_blitz_only("Open", "90 min + 30 sec"))
        self.assertFalse(s.is_blitz_only("Open", ""))

    def test_mixed_and_named_rapid_kept(self):
        self.assertFalse(s.is_blitz_only("Rapid & Blitz", "5+3 / 15+10"))
        self.assertFalse(s.is_blitz_only("City Rapid Open", "5+3"))

    def test_other_notations_not_misread(self):
        # 15" + 5' is 15 s + 5 min in some countries' notation; must not read as blitz.
        self.assertFalse(s.is_blitz_only("Open", "15\" + 5'"))
        self.assertFalse(s.is_blitz_only("Open", "15 + 10"))


class Online(unittest.TestCase):
    def test_online_locations(self):
        for loc in ["Online", "Zoom", "lichess.org", "Chess.com", "Tornelo", "https://tornelo.com/x"]:
            self.assertTrue(s.is_online_event("Open", loc), loc)

    def test_online_name_without_venue(self):
        self.assertTrue(s.is_online_event("Online Open", ""))
        self.assertTrue(s.is_online_event("Online Open", "https://example.org"))

    def test_real_venues_kept(self):
        self.assertFalse(s.is_online_event("Helsinki Open", "Helsinki"))
        self.assertFalse(s.is_online_event("Hybrid Online Open", "Madrid"))
        self.assertFalse(s.is_online_event("Open (online registration)", ""))


if __name__ == "__main__":
    unittest.main()
