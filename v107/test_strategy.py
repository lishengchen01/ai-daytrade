"""Synthetic regression tests only; no production source calls, no credentials."""
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fugle import FugleClient
from strategy import evaluate
from runner import watchlist

TW = ZoneInfo("Asia/Taipei")


def sample(now=None, short=False):
    now = now or datetime(2026, 11, 25, 9, 10, tzinfo=TW)
    date = now.date().isoformat()
    first = [
        (103.0, 104.0, 102.9, 103.7, 300),
        (103.7, 104.0, 103.4, 103.8, 200),
        (103.8, 104.0, 103.6, 103.9, 250),
        (103.9, 104.2, 103.7, 104.0, 350),
        (104.0, 104.2, 103.8, 104.1, 400),
        (104.1, 104.6, 104.1, 104.5, 100),
        (104.4, 104.55, 104.19, 104.4, 200),
    ]
    bars = []
    for m, (o, h, l, c, v) in enumerate(first):
        dt = now.replace(hour=9, minute=m, second=0, microsecond=0)
        bars.append({"date": dt.isoformat(), "open": o, "high": h,
                     "low": l, "close": c, "volume": v})
    q = {"symbol": "6148", "date": date, "previousClose": 100,
         "closePrice": 104.4, "avgPrice": 103.5,
         "lastTrade": {"time": int((now - timedelta(seconds=15)).timestamp() * 1_000_000)}}
    c = {"symbol": "6148", "date": date, "data": bars}
    ctx = {"trading_date": date, "is_trade_day": True, "sample": False,
           "source": "verified index feed", "eligibility_source": "official verified",
           "verified_at": (now - timedelta(seconds=20)).isoformat(),
           "market_direction": 1, "sector_directions": {"6148": 1},
           "eligibility": {"6148": {"date": date, "buy_then_sell": True,
                                     "sell_then_buy": True}},
           "licensed_private_use": True}
    return q, c, ctx


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 9, 10, tzinfo=TW)
        self.q, self.c, self.ctx = sample(self.now)

    def run_evaluation(self):
        return evaluate("6148", self.q, self.c, 10000, self.ctx, self.now)

    def test_all_conditions_only_on_authorized_verified_data(self):
        r = self.run_evaluation()
        self.assertEqual(r["direction"], "LONG_CONDITIONS")
        self.assertTrue(all(r["checks"].values()))
        self.assertFalse(r["place_order"])

    def test_sample_never_signals(self):
        self.q["sample"] = True
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_no_provider_license(self):
        self.ctx["licensed_private_use"] = False
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_no_qualification(self):
        self.ctx["eligibility"] = {}
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_quote_stale(self):
        self.q["lastTrade"]["time"] -= 180_000_000
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_incomplete_five_minute_candle(self):
        self.c["data"] = self.c["data"][1:]
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_no_broad_market_confirmation(self):
        self.ctx["market_direction"] = None
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_wrong_date(self):
        self.ctx["trading_date"] = "2026-11-24"
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_no_context(self):
        self.assertEqual(evaluate("6148", self.q, self.c, 10000, {}, self.now)["direction"], "WAIT")

    def test_after_hours(self):
        self.assertEqual(evaluate("6148", self.q, self.c, 10000, self.ctx,
                        self.now.replace(hour=18))["direction"], "WAIT")

    def test_daily_shortlist_is_limited_and_previous_day(self):
        data = {"rows": [{"symbol": "6148", "date": "2026-11-24", "change": 3,
                          "volume": 2000}, {"symbol": "2330", "date": "2026-11-24",
                          "change": 0.5, "volume": 5000}]}
        self.assertEqual(len(watchlist(data, "2026-11-25")), 1)

    def test_short_conditions_require_sell_then_buy(self):
        def flip(x): return 200 - x
        for bar in self.c["data"]:
            o,h,l,c = (bar[k] for k in ("open","high","low","close"))
            bar.update(open=flip(o), high=flip(l), low=flip(h), close=flip(c))
        self.q["closePrice"] = 95.6
        self.q["avgPrice"] = 96.5
        self.ctx["market_direction"] = -1
        self.ctx["sector_directions"]["6148"] = -1
        self.assertEqual(self.run_evaluation()["direction"], "SHORT_CONDITIONS")
        self.ctx["eligibility"]["6148"]["sell_then_buy"] = False
        self.assertEqual(self.run_evaluation()["direction"], "WAIT")

    def test_fugle_path_without_real_network(self):
        captured = []
        f = FugleClient(key="TEST-ONLY", transport=lambda path: captured.append(path) or {})
        f.quote("6148")
        f.minute_candles("6148")
        self.assertEqual(captured, ["intraday/quote/6148",
                                   "intraday/candles/6148?timeframe=1&sort=asc"])


if __name__ == "__main__":
    unittest.main()
