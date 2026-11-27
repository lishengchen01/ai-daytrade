"""Offline regressions: no real Fugle call, no push, no broker orders."""
from datetime import datetime
import os
import time
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from v1071.audit_live import audit_once
from v1071.fugle import FugleClient, MarketDataError
from v1071.scanner import _index_symbol

TW = ZoneInfo("Asia/Taipei")


class VerifiedIndexTests(unittest.TestCase):
    def test_known_taiex_index_is_selected(self):
        class Client:
            def ticker(self, symbol):
                self.assertEqual(symbol, "IX0001")
                return {"symbol": symbol, "type":"INDEX", "exchange":"TWSE",
                        "date":"2026-11-27"}
        # Keep the stub minimal; assert outside the stub because it is not a TestCase.
        client = Client()
        client.ticker = lambda symbol: {
            "symbol":symbol, "type":"INDEX", "exchange":"TWSE", "date":"2026-11-27"
        } if symbol == "IX0001" else {}
        self.assertEqual(_index_symbol(client, {}, "2026-11-27"), "IX0001")

    def test_stale_or_wrong_index_never_passes(self):
        class Client:
            def __init__(self, ticker):
                self.value = ticker
            def ticker(self, _):
                return self.value
        good = {"symbol":"IX0001", "type":"INDEX", "exchange":"TWSE", "date":"2026-11-27"}
        for field, bad_value in [("date","2026-11-26"), ("type","EQUITY"),
                                 ("exchange","TPEx"), ("symbol","IX0002")]:
            item = dict(good)
            item[field] = bad_value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "IX0001"):
                    _index_symbol(Client(item), {}, "2026-11-27")

    def test_no_alternate_index_without_validation(self):
        with self.assertRaisesRegex(ValueError, "IX0001"):
            _index_symbol(None, {"market_index_symbol":"IX9999"}, "2026-11-27")


class LiveAuditSafetyTests(unittest.TestCase):
    def test_reject_nonmarket_without_calls(self):
        class NoClient:
            requests_made = 0
        with patch("v1071.audit_live.scan_real", side_effect=AssertionError("must not call")):
            out = audit_once(NoClient(), now=datetime(2026, 11, 26, 18, 30, tzinfo=TW))
        self.assertEqual(out["status"], "outside_market")
        self.assertEqual(out["requests"], 0)

    def test_rest_client_rejects_more_than_45_per_rolling_minute(self):
        client = FugleClient(key="offline-test-only-key-not-real")
        client._request_times.extend([time.monotonic()] * client.REQUEST_LIMIT)
        with patch("v1071.fugle.urllib.request.urlopen",
                   side_effect=AssertionError("No network permitted")):
            with self.assertRaisesRegex(MarketDataError, "安全預算"):
                client.quote("2330")
        self.assertEqual(client.requests_made, 0)

    def test_approved_personal_use_is_process_local_and_never_pushes(self):
        sample = {"symbol":"2330", "direction":"LONG_CONDITIONS", "sample":False,
                  "checks":{"all":True}}
        class Client:
            requests_made = 7
        now = datetime(2026, 11, 27, 9, 15, tzinfo=TW)
        with patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED":"NO"}):
            with patch("v1071.audit_live.scan_real", return_value=([sample],"offline")) as scan:
                out = audit_once(Client(), now=now, daily={"mock":True})
            self.assertEqual(os.environ["FUGLE_PRIVATE_USE_CONFIRMED"], "NO")
            self.assertEqual(out["signals"], [("2330", "LONG_CONDITIONS")])
            self.assertEqual(out["requests"], 7)
            self.assertTrue(scan.call_args.args[0]["broker_sell_first_verified"])
        # audit_live intentionally has no imported push_service or deliver function
        from v1071 import audit_live
        self.assertFalse(hasattr(audit_live, "deliver"))


if __name__ == "__main__":
    unittest.main()
