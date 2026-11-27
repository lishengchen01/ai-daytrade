"""Offline regression: authentic-looking fixtures are test-only, never dispatched to users."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from v1071.scanner import scan_real, _quote_rejection_reason, _sector_direction, _valid_quote
from v1071.push_service import create_app, _is_apple_endpoint, deliver
from v1071.create_vapid_keys import generate

TW = ZoneInfo("Asia/Taipei")


class FakeFugle:
    def __init__(self, now):
        self.now = now
        self.date = now.date().isoformat()
        self.sector_up = True

    def ticker(self, symbol):
        if symbol == "IX0001":
            return {"date": self.date, "symbol": symbol, "type": "INDEX", "exchange": "TWSE"}
        return {"date": self.date, "symbol": symbol, "type": "EQUITY",
                "exchange": "TWSE", "industry": "24", "securityStatus": "NORMAL",
                "isDisposition": False, "matchingInterval": 0,
                "canDayTrade": True, "canBuyDayTrade": True}

    def tickers(self, **kwargs):
        return {"date": self.date, "data": [
            {"symbol": "6148"}, {"symbol": "1111"}, {"symbol": "2222"}]}

    def quote(self, symbol):
        now = self.now
        stamp = int((now - timedelta(seconds=15)).timestamp() * 1_000_000)
        if symbol == "IX0001":
            return {"symbol": symbol, "date": self.date, "type": "INDEX",
                    "previousClose": 10000, "closePrice": 10060, "closeTime": stamp}
        if symbol == "6148":
            return {"symbol": symbol, "date": self.date, "type": "EQUITY",
                    "previousClose": 100, "closePrice": 104.4, "avgPrice": 103.5,
                    "lastTrade": {"time": stamp}}
        return {"symbol": symbol, "date": self.date, "type": "EQUITY",
                "previousClose": 100, "closePrice": 101 if self.sector_up else 99,
                "avgPrice": 100, "lastTrade": {"time": stamp}}

    def minute_candles(self, symbol):
        points = [(103.0, 104.0, 102.9, 103.7, 300),
                  (103.7, 104.0, 103.4, 103.8, 200),
                  (103.8, 104.0, 103.6, 103.9, 250),
                  (103.9, 104.2, 103.7, 104.0, 350),
                  (104.0, 104.2, 103.8, 104.1, 400),
                  (104.1, 104.6, 104.1, 104.5, 100),
                  (104.4, 104.55, 104.19, 104.4, 200)]
        bars = []
        for minute, (o, h, l, c, v) in enumerate(points):
            t = self.now.replace(hour=9, minute=minute, second=0, microsecond=0)
            bars.append(dict(date=t.isoformat(), open=o, high=h, low=l, close=c,
                             volume=v))
        return dict(symbol=symbol, date=self.date, timeframe="1", data=bars)


class RealScannerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 9, 10, tzinfo=TW)
        self.client = FakeFugle(self.now)
        self.config = {"market_index_symbol": "IX0001",
                       "broker_permission_verified": True,
                       "broker_sell_first_verified": True}
        self.daily = {"fetched": self.now.isoformat(), "rows": [
            {"date": "2026-11-24", "symbol": "6148", "volume": 10000, "change": 3.0},
            {"date": "2026-11-24", "symbol": "1111", "volume": 8000, "change": 1.1},
            {"date": "2026-11-24", "symbol": "2222", "volume": 7000, "change": 1.2}]}

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_genuine_conditions_generate_research_candidate_only(self):
        rows, _ = scan_real(self.config, client=self.client, now=self.now, daily=self.daily, clock=lambda: self.now)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["direction"], "LONG_CONDITIONS")
        self.assertTrue(all(rows[0]["checks"].values()))
        self.assertNotIn("closePrice", rows[0])
        self.assertNotIn("place_order", rows[0])

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_opt_in_diagnostic_counts_do_not_change_signals(self):
        baseline, _ = scan_real(self.config, client=self.client,
                                now=self.now, daily=self.daily, clock=lambda: self.now)
        stats = {}
        observed, _ = scan_real(self.config, client=self.client,
                                now=self.now, daily=self.daily, clock=lambda: self.now,
                                diagnostics=stats)
        self.assertEqual(observed, baseline)
        self.assertEqual(stats["盤後初篩候選數"], 1)
        self.assertEqual(stats["完整多空條件通過"], 1)
        self.assertNotIn("closePrice", str(stats))
        self.assertNotIn("6148", str(stats))

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_rejected_candidate_has_aggregated_reason(self):
        self.client.sector_up = False
        stats = {}
        observed, _ = scan_real(self.config, client=self.client,
                                now=self.now, daily=self.daily, clock=lambda: self.now,
                                diagnostics=stats)
        self.assertEqual(observed, [])
        self.assertEqual(stats["盤後初篩候選數"], 1)
        self.assertEqual(stats["五分鐘策略或當沖資格條件未全數通過"], 1)

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_failed_strategy_gates_are_counted_without_triggering_signal(self):
        self.client.sector_up = False
        stats = {}
        selected, _ = scan_real(
            self.config, client=self.client, now=self.now, daily=self.daily,
            clock=lambda: self.now, diagnostics=stats,
        )
        self.assertEqual(selected, [])
        self.assertEqual(stats["五分鐘策略或當沖資格條件未全數通過"], 1)
        self.assertEqual(stats["策略未通過：大盤與族群同方向條件未符合"], 1)
        self.assertNotIn("6148", str(stats))
        self.assertNotIn("closePrice", str(stats))

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_strategy_precheck_failure_reports_safe_fixed_reason(self):
        original = self.client.minute_candles
        def incomplete(symbol):
            bars = original(symbol)
            bars["data"] = bars["data"][1:]  # missing 09:00 candle
            return bars
        self.client.minute_candles = incomplete
        stats = {}
        selected, _ = scan_real(
            self.config, client=self.client, now=self.now, daily=self.daily,
            clock=lambda: self.now, diagnostics=stats,
        )
        self.assertEqual(selected, [])
        self.assertEqual(stats["策略前置：首根五分鐘K尚未完整"], 1)

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_bad_sector_does_not_alert(self):
        self.client.sector_up = False
        rows, _ = scan_real(self.config, client=self.client, now=self.now, daily=self.daily, clock=lambda: self.now)
        self.assertEqual(rows, [])

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_quote_age_rejection_is_counted_without_changing_decision(self):
        original = self.client.quote
        def stale(symbol):
            q = original(symbol)
            if symbol == "6148":
                q["lastTrade"]["time"] -= 200_000_000
            return q
        self.client.quote = stale
        stats = {}
        rows, _ = scan_real(self.config, client=self.client,
                            now=self.now, daily=self.daily, clock=lambda: self.now, diagnostics=stats)
        self.assertEqual(rows, [])
        self.assertEqual(stats["個股即時報價不完整或過期"], 1)
        self.assertEqual(stats["個股報價原因：最後成交已超過90秒"], 1)

    def test_missing_peer_is_categorized_without_quotes_or_symbols(self):
        ticker = self.client.ticker("6148")
        stats = {}
        direction = _sector_direction(self.client, ticker,
                                      [{"symbol":"6148","volume":10000}],
                                      self.now, diagnostics=stats)
        self.assertEqual(direction, 0)
        self.assertEqual(stats["可比較的前日同產業股票不足兩檔"], 1)
        self.assertNotIn("6148", str(stats))

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_quotes_arriving_after_scan_start_are_not_false_future(self):
        # This previously failed on real data: 'now' was frozen at
        # scan start but sequential REST calls delivered new trades.
        start = self.now
        received = start + timedelta(seconds=8)
        original = self.client.quote
        def new_trade(symbol):
            q = original(symbol)
            if symbol != "IX0001":
                q["lastTrade"]["time"] = int(
                    (start + timedelta(seconds=3)).timestamp() * 1_000_000)
            return q
        self.client.quote = new_trade
        rows, _ = scan_real(self.config, client=self.client,
                            now=start, daily=self.daily, clock=lambda: received)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["direction"], "LONG_CONDITIONS")
        self.assertEqual(rows[0]["at"], received.isoformat())

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_truly_future_trade_still_fails_closed(self):
        start = self.now
        received = start + timedelta(seconds=8)
        original = self.client.quote
        def out_of_order(symbol):
            q = original(symbol)
            if symbol == "6148":
                q["lastTrade"]["time"] = int(
                    (received + timedelta(seconds=15)).timestamp() * 1_000_000)
            return q
        self.client.quote = out_of_order
        diagnostics = {}
        rows, _ = scan_real(
            self.config, client=self.client, now=start, daily=self.daily,
            clock=lambda: received, diagnostics=diagnostics)
        self.assertEqual(rows, [])
        self.assertEqual(diagnostics["個股報價原因：行情時間晚於檢查時間"], 1)

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_stale_daily_does_not_alert(self):
        self.daily["rows"][0]["date"] = "2026-11-10"
        self.daily["rows"][1]["date"] = "2026-11-10"
        self.daily["rows"][2]["date"] = "2026-11-10"
        rows, _ = scan_real(self.config, client=self.client, now=self.now, daily=self.daily, clock=lambda: self.now)
        self.assertEqual(rows, [])

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_no_personal_broker_permission(self):
        self.config["broker_permission_verified"] = False
        rows, _ = scan_real(self.config, client=self.client, now=self.now, daily=self.daily, clock=lambda: self.now)
        self.assertEqual(rows, [])

    @patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "YES"})
    def test_stale_stock_trade_is_not_live(self):
        original = self.client.quote
        def stale(symbol):
            q = original(symbol)
            if symbol == "6148":
                q["lastTrade"]["time"] -= 200_000_000
            return q
        self.client.quote = stale
        rows, _ = scan_real(self.config, client=self.client, now=self.now, daily=self.daily, clock=lambda: self.now)
        self.assertEqual(rows, [])

    def test_no_market_data_license_confirmation(self):
        with patch.dict(os.environ, {"FUGLE_PRIVATE_USE_CONFIRMED": "NO"}):
            rows, _ = scan_real(self.config, client=self.client, now=self.now, daily=self.daily, clock=lambda: self.now)
            self.assertEqual(rows, [])


class PrivatePushTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "DAYTRADE_DB_PATH": self.temp.name + "/push.sqlite3",
            "PUSH_PAIRING_TOKEN": "x" * 40,
            "VAPID_PUBLIC_KEY": "A" * 87,
        })
        self.env.start()
        self.app = create_app().test_client()
        self.origin = {"Origin": "https://lishengchen01.github.io"}
        self.auth = {**self.origin, "Authorization": "Bearer " + "x" * 40}
        self.sub = {"endpoint": "https://web.push.apple.com/Q-TEST-ONLY",
                    "keys": {"p256dh": "A" * 87, "auth": "B" * 22}}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_origin_required_even_for_public_key(self):
        r = self.app.get("/api/v1/vapid-public-key")
        self.assertEqual(r.status_code, 403)

    def test_invalid_auth_not_accepted(self):
        r = self.app.post("/api/v1/subscribe", json=self.sub, headers=self.origin)
        self.assertEqual(r.status_code, 401)

    def test_ssrf_endpoints_blocked(self):
        self.assertFalse(_is_apple_endpoint("https://127.0.0.1/"))
        self.assertFalse(_is_apple_endpoint("https://evil-push.apple.com.attacker.test/Q"))
        self.assertFalse(_is_apple_endpoint("http://web.push.apple.com/Q"))
        self.assertTrue(_is_apple_endpoint("https://web.push.apple.com/Q-TEST-ONLY"))
        r = self.app.post("/api/v1/subscribe", json={
            **self.sub, "endpoint": "https://127.0.0.1/"}, headers=self.auth)
        self.assertEqual(r.status_code, 400)

    def test_subscribe_and_revoke(self):
        r = self.app.post("/api/v1/subscribe", json=self.sub, headers=self.auth)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json["registered"])
        r = self.app.post("/api/v1/unsubscribe", json=self.sub, headers=self.auth)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json["registered"])

    def test_no_live_send_from_simulated_or_unauthorized(self):
        payload = {"schema": "daytrade-push-v1", "type": "strategy-signal",
                   "verified": True, "sample": True, "symbol": "6148",
                   "direction": "LONG_CONDITIONS", "signalId": "d:x:y",
                   "issuedAt": datetime.now(TW).isoformat()}
        with patch.dict(os.environ, {"WEBPUSH_DERIVED_SIGNAL_ALLOWED": "YES"}):
            self.assertEqual(deliver(payload), 0)
            payload["sample"] = False
            payload["verified"] = False
            self.assertEqual(deliver(payload), 0)
        with patch.dict(os.environ, {"WEBPUSH_DERIVED_SIGNAL_ALLOWED": "NO"}):
            payload["verified"] = True
            self.assertEqual(deliver(payload), 0)

    def test_generate_vapid_never_overwrites(self):
        pem = self.temp.name + "/private.pem"
        path, public = generate(pem)
        self.assertTrue(os.path.isfile(path))
        self.assertGreater(len(public), 80)
        with self.assertRaises(FileExistsError):
            generate(pem)


if __name__ == "__main__":
    unittest.main()
