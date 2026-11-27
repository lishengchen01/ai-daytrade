"""No-network V1.08.1 true-signal preparation / private no-push regressions."""
from datetime import datetime, timedelta
import json
import unittest

from v108.signal_bridge import (
    REQUIRED_CHECKS, prepare_private_push_payloads, shadow_push_summary,
)
from v108.shadow_loop import scan_summary
from v1071.strategy import TW


class PushReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 27, 11, 18, 0, tzinfo=TW)
        self.signal = {
            "symbol": "6148",
            "direction": "LONG_CONDITIONS",
            "sample": False,
            "at": (self.now - timedelta(seconds=10)).isoformat(),
            "checks": {key: True for key in REQUIRED_CHECKS},
        }

    def test_real_qualified_signal_becomes_minimal_private_metadata(self):
        signal = dict(self.signal)
        signal["price"] = 987654
        signal["candles"] = [{"secret": "do-not-redistribute"}]
        result = prepare_private_push_payloads([signal], now=self.now)
        self.assertEqual(len(result), 1)
        message = result[0]
        self.assertEqual(message["signalId"], "2026-11-27:6148:LONG_CONDITIONS")
        self.assertEqual(message["issuedAt"], self.signal["at"])
        self.assertEqual(message["type"], "strategy-signal")
        self.assertNotIn("price", json.dumps(message))
        self.assertNotIn("do-not-redistribute", json.dumps(message))
        self.assertEqual(shadow_push_summary([signal], now=self.now)["notifications_sent"], 0)

    def test_no_sample_or_missing_gate_can_pass(self):
        samples = []
        for sample in (True, None):
            obj = dict(self.signal)
            obj["sample"] = sample
            samples.append(obj)
        for field in REQUIRED_CHECKS:
            obj = dict(self.signal)
            obj["checks"] = dict(self.signal["checks"])
            obj["checks"][field] = False
            samples.append(obj)
            obj2 = dict(obj)
            obj2["checks"] = dict(obj["checks"])
            obj2["checks"].pop(field)
            samples.append(obj2)
        self.assertEqual(prepare_private_push_payloads(samples, now=self.now), [])

    def test_future_stale_other_day_and_unauthorized_payloads_are_rejected(self):
        for stamp in (
            self.now + timedelta(seconds=1),
            self.now - timedelta(seconds=91),
            self.now - timedelta(days=1),
        ):
            obj = dict(self.signal, at=stamp.isoformat())
            self.assertEqual(prepare_private_push_payloads([obj], now=self.now), [])
        for symbol in ("IX0001", "../escape", "", "A6148"):
            obj = dict(self.signal, symbol=symbol)
            self.assertEqual(prepare_private_push_payloads([obj], now=self.now), [])
        obj = dict(self.signal, direction="WAIT")
        self.assertEqual(prepare_private_push_payloads([obj], now=self.now), [])

    def test_stable_id_deduplicates_in_single_scan(self):
        obj = dict(self.signal)
        self.assertEqual(len(prepare_private_push_payloads(
            [self.signal, obj], now=self.now)), 1)

    def test_no_signal_after_market_hours(self):
        late = datetime(2026, 11, 27, 13, 21, tzinfo=TW)
        self.assertEqual(prepare_private_push_payloads([self.signal], now=late), [])

    def test_shadow_summary_records_counts_not_ticker_or_payload(self):
        class Client:
            pass
        def fake_audit(client, now):
            return {
                "status": "completed",
                "requests": 29,
                "signals": [("6148", "LONG_CONDITIONS")],
                "verified_signals": [self.signal],
                "diagnostics": {"盤後初篩候選數": 5},
            }
        summary = scan_summary(
            Client(), now=self.now, audit=fake_audit,
            clock_source=lambda: self.now,
        )
        self.assertEqual(summary["push_mode"], "SHADOW_DISABLED")
        self.assertEqual(summary["notifications_sent"], 0)
        self.assertEqual(summary["push_ready_count"], 1)
        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn("6148", serialized)
        self.assertNotIn("signalId", serialized)
        self.assertNotIn("issuedAt", serialized)


if __name__ == "__main__":
    unittest.main()
