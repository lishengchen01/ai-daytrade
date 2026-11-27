"""Deterministic offline checks: never publish bogus daily public quotes."""
import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fetch_quotes as fq


class PublicQuotesSafetyTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.date(2026, 11, 27)
        self.rows = [
            {"symbol": "2330", "market": "上市", "date": "2026-11-26"},
            {"symbol": "6148", "market": "上櫃", "date": "2026-11-26"},
        ]
        self.status = [
            {"market": "上市", "ok": True, "count": 1},
            {"market": "上櫃", "ok": True, "count": 1},
        ]

    def test_public_roc_and_ad_dates(self):
        self.assertEqual(fq.parse_date("115/11/26"), "2026-11-26")
        self.assertEqual(fq.parse_date("2026-11-26"), "2026-11-26")

    def test_prior_day_valid_before_market_close(self):
        self.assertEqual(fq.validate_release(
            self.rows, self.status, today=self.today), "2026-11-26")

    def test_empty_and_partial_source_fail_closed(self):
        with self.assertRaises(ValueError):
            fq.validate_release([], self.status, today=self.today)
        data = [dict(x) for x in self.status]
        data[1]["ok"] = False
        with self.assertRaises(ValueError):
            fq.validate_release(self.rows, data, today=self.today)

    def test_dates_from_two_markets_must_match(self):
        mixed = [dict(x) for x in self.rows]
        mixed[1]["date"] = "2026-11-25"
        with self.assertRaises(ValueError):
            fq.validate_release(mixed, self.status, today=self.today)

    def test_future_or_stale_dates_fail_closed(self):
        for date in ("2026-11-28", "2026-11-20"):
            altered = [dict(x, date=date) for x in self.rows]
            with self.assertRaises(ValueError):
                fq.validate_release(altered, self.status, today=self.today)

    def test_failure_must_not_overwrite_existing_file(self):
        # A failed external feed must halt before replacing an already
        # published public quote file on the runner.
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, *args):
                return b"[]"
        with tempfile.TemporaryDirectory() as tmp:
            here = Path.cwd()
            try:
                os.chdir(tmp)
                Path("quotes.json").write_text("KNOWN_GOOD", encoding="utf-8")
                with patch.object(fq.urllib.request, "urlopen", return_value=FakeResponse()):
                    with self.assertRaises(ValueError):
                        fq.main()
                self.assertEqual(Path("quotes.json").read_text(encoding="utf-8"),
                                 "KNOWN_GOOD")
            finally:
                os.chdir(here)


if __name__ == "__main__":
    unittest.main()
