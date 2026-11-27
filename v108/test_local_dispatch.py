"""V1.08.2 offline private Apple Push dispatch/security regressions.

No market-data calls and no Apple Push traffic. Delivery is always stubbed.
"""
from contextlib import closing
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from v1071.strategy import TW
from v1071.push_service import create_app
from .local_dispatch import (
    _config, dispatch_from_private_audit, MODE_DISABLED, MODE_LIVE,
)
from .signal_bridge import REQUIRED_CHECKS


class PrivateDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "v1082-private-notify.json"
        self.now = datetime(2026, 11, 27, 11, 15, 0, tzinfo=TW)
        self.signal = {
            "symbol": "6148", "direction": "LONG_CONDITIONS",
            "sample": False,
            "at": (self.now - timedelta(seconds=20)).isoformat(),
            "checks": {name: True for name in REQUIRED_CHECKS},
        }
        self.result = {"status": "completed", "verified_signals": [self.signal]}
        self.optin = {
            "mode": "private-owner-alerts", "enabled": True,
            "personal_fugle_use_confirmed": True,
            "broker_permission_verified": True,
            "broker_sell_first_verified": True,
            "iphone_connection_test_confirmed": True,
            "vapid_subject": "mailto:unit-test@example.org",
        }

    def _write_config(self, data=None):
        self.config.write_text(json.dumps(
            self.optin if data is None else data), encoding="utf-8")

    def _prepare_local_device(self):
        (self.root / "vapid-private.pem").write_text(
            "TEST FILE ONLY - no real key", encoding="utf-8")
        with closing(sqlite3.connect(str(self.root / "push.sqlite3"))) as db, db:
            db.execute("CREATE TABLE subscriptions(endpoint TEXT PRIMARY KEY)")
            db.execute(
                "INSERT INTO subscriptions(endpoint) VALUES (?)",
                ("https://web.push.apple.com/unit-fixture-only",),
            )
            db.execute(
                "CREATE TABLE sent(signal_id TEXT PRIMARY KEY, sent_at TEXT NOT NULL)"
            )

    def _dispatch(self, **kw):
        return dispatch_from_private_audit(
            self.result, now=self.now, config_path=self.config,
            private_root=self.root, clock_source=lambda: self.now,
            **kw
        )

    def test_without_local_optin_never_delivers(self):
        def should_not_call(payload):
            self.fail("SHADOW mode cannot call push sender")
        out = self._dispatch(delivery=should_not_call)
        self.assertEqual(out["push_mode"], MODE_DISABLED)
        self.assertEqual(out["push_ready_count"], 1)
        self.assertEqual(out["notifications_sent"], 0)
        self.assertEqual(out["attempted_alerts"], 0)
        self.assertFalse((self.root / "push.sqlite3").exists())

    def test_true_local_optin_and_subscriber_required(self):
        self._write_config()
        out = self._dispatch(delivery=lambda p: 1)
        self.assertEqual(out["push_mode"], MODE_DISABLED)
        self._prepare_local_device()
        out = self._dispatch(delivery=lambda p: 1)
        self.assertEqual(out["push_mode"], MODE_LIVE)
        self.assertEqual(out["attempted_alerts"], 1)
        self.assertEqual(out["notifications_sent"], 1)

    def test_durable_dedup_survives_restart_and_no_secret_env_leak(self):
        self._write_config()
        self._prepare_local_device()
        delivered = []
        def stub(payload):
            self.assertEqual(os.environ["WEBPUSH_DERIVED_SIGNAL_ALLOWED"], "YES")
            self.assertEqual(os.environ["DAYTRADE_DB_PATH"],
                             str(self.root / "push.sqlite3"))
            delivered.append(payload)
            return 1
        with patch.dict(os.environ, {
            "WEBPUSH_DERIVED_SIGNAL_ALLOWED": "NO",
            "VAPID_SUBJECT": "original",
        }):
            first = self._dispatch(delivery=stub)
            second = self._dispatch(delivery=stub)
            self.assertEqual(os.environ["WEBPUSH_DERIVED_SIGNAL_ALLOWED"], "NO")
            self.assertEqual(os.environ["VAPID_SUBJECT"], "original")
        self.assertEqual(first["attempted_alerts"], 1)
        self.assertEqual(second["attempted_alerts"], 0)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(
            delivered[0]["signalId"], "2026-11-27:6148:LONG_CONDITIONS")
        with sqlite3.connect(str(self.root / "push.sqlite3")) as db:
            self.assertEqual(db.execute(
                "SELECT provider_accepted FROM local_dispatch_attempts"
            ).fetchone()[0], 1)

    def test_failed_or_unknown_send_does_not_retry_after_restart(self):
        self._write_config()
        self._prepare_local_device()
        def fail(*args):
            raise ConnectionError("temporary simulated failure")
        first = self._dispatch(delivery=fail)
        self.assertEqual(first["notifications_sent"], 0)
        self.assertEqual(first["attempted_alerts"], 1)
        second = self._dispatch(delivery=lambda p: 1)
        self.assertEqual(second["attempted_alerts"], 0)
        self.assertEqual(second["notifications_sent"], 0)

    def test_stale_at_actual_send_time_fails_closed(self):
        self._write_config()
        self._prepare_local_device()
        later = self.now + timedelta(seconds=75)
        delivery_count = []
        out = dispatch_from_private_audit(
            self.result, now=self.now, clock_source=lambda: later,
            config_path=self.config, private_root=self.root,
            delivery=lambda p: delivery_count.append(p) or 1,
        )
        self.assertEqual(out["push_ready_count"], 1)
        self.assertEqual(out["attempted_alerts"], 0)
        self.assertFalse(delivery_count)

    def test_bad_source_or_fake_or_missing_checks_never_delivers(self):
        self._write_config()
        self._prepare_local_device()
        for broken in (
            {"status": "blocked_or_error", "verified_signals": [self.signal]},
            {"status": "completed", "verified_signals": []},
            {"status": "completed", "verified_signals": [
                dict(self.signal, sample=True)]},
            {"status": "completed", "verified_signals": [
                dict(self.signal, checks={"gap2to4": True})]},
        ):
            out = dispatch_from_private_audit(
                broken, now=self.now, config_path=self.config,
                private_root=self.root, clock_source=lambda: self.now,
                delivery=lambda p: self.fail("invalid signal sent"),
            )
            self.assertEqual(out["notifications_sent"], 0)

    def test_malformed_config_is_blocked(self):
        self._prepare_local_device()
        bad = dict(self.optin, enabled="true")
        self._write_config(bad)
        self.assertIsNone(_config(self.config))
        self.assertEqual(self._dispatch(delivery=lambda p: 1)["push_mode"],
                         MODE_DISABLED)

    def test_public_flask_has_no_signal_submission_api(self):
        app = create_app().test_client()
        headers = {"Origin": "https://lishengchen01.github.io"}
        response = app.post("/api/v1/signal", json={
            "symbol": "6148", "verified": True}, headers=headers)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
