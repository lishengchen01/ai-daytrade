"""Offline regressions for V1.08.2 local iPhone connection-test path."""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from .test_local_iphone_push import (
    send_local_connection_test, _validate_contact_email, main,
    TEST_LABEL,
)


class LocalIPhonePushTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "vapid-private.pem").write_text(
            "TEST PLACEHOLDER ONLY - NOT A PRIVATE KEY", encoding="utf-8")
        self.database = self.root / "push.sqlite3"
        with closing(sqlite3.connect(str(self.database))) as db, db:
            db.execute(
                "CREATE TABLE subscriptions (endpoint TEXT PRIMARY KEY, "
                "p256dh TEXT, auth TEXT, created_at TEXT)"
            )
            db.execute(
                "INSERT INTO subscriptions VALUES (?,?,?,?)",
                ("https://web.push.apple.com/FAKE-FIXTURE",
                 "A"*87, "B"*22, "2026-11-27T00:00:00Z"),
            )
        self.now = datetime(2026, 11, 27, 4, 0, tzinfo=timezone.utc)

    def test_valid_only_connection_test_and_no_live_enable(self):
        seen = []
        def fake_sender(payload, *, allow_test=False):
            self.assertEqual(os.environ["WEBPUSH_DERIVED_SIGNAL_ALLOWED"], "NO")
            self.assertTrue(allow_test)
            seen.append(dict(payload))
            return 1
        with patch.dict(os.environ, {
            "WEBPUSH_DERIVED_SIGNAL_ALLOWED": "YES",
            "VAPID_SUBJECT": "mailto:old@example.org",
        }):
            result = send_local_connection_test(
                root=self.root, subject="owner@example.org",
                sender=fake_sender, now=self.now)
            self.assertEqual(os.environ["WEBPUSH_DERIVED_SIGNAL_ALLOWED"], "YES")
            self.assertEqual(os.environ["VAPID_SUBJECT"], "mailto:old@example.org")
        self.assertEqual(result["provider_accepted"], 1)
        self.assertFalse(result["live_signal_enabled"])
        self.assertEqual(result["strategy_signals_sent"], 0)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["type"], TEST_LABEL)
        self.assertTrue(seen[0]["test"])
        self.assertEqual(set(seen[0]), {"schema","type","test","issuedAt"})
        self.assertNotIn("symbol", json.dumps(seen[0]))
        self.assertNotIn("LONG_CONDITIONS", json.dumps(seen[0]))

    def test_sender_failure_keeps_env_and_does_not_log_secrets(self):
        def fail(_payload, *, allow_test):
            self.assertEqual(os.environ["WEBPUSH_DERIVED_SIGNAL_ALLOWED"], "NO")
            raise RuntimeError("offline simulated sender failure")
        with patch.dict(os.environ, {
            "WEBPUSH_DERIVED_SIGNAL_ALLOWED": "NO",
            "DAYTRADE_DB_PATH": "unchanged",
        }):
            with self.assertRaises(RuntimeError):
                send_local_connection_test(
                    root=self.root, subject="owner@example.org",
                    sender=fail, now=self.now)
            self.assertEqual(os.environ["DAYTRADE_DB_PATH"], "unchanged")

    def test_no_db_or_no_subscriptions_never_sends(self):
        sent = []
        def fake_sender(payload, *, allow_test):
            sent.append(payload)
            return 1
        with closing(sqlite3.connect(str(self.database))) as db, db:
            db.execute("DELETE FROM subscriptions")
        with self.assertRaises(RuntimeError):
            send_local_connection_test(
                root=self.root, subject="owner@example.org",
                sender=fake_sender)
        self.assertFalse(sent)
        self.database.unlink()
        with self.assertRaises(RuntimeError):
            send_local_connection_test(
                root=self.root, subject="owner@example.org",
                sender=fake_sender)
        self.assertFalse(sent)

    def test_bad_email_never_sends(self):
        self.assertEqual(_validate_contact_email(
            "mailto:owner@example.org"), "mailto:owner@example.org")
        for value in ("", "NOT AN EMAIL", "mailto:abc", "owner@example.org\nBearer KEY"):
            with self.assertRaises(ValueError):
                send_local_connection_test(
                    root=self.root, subject=value,
                    sender=lambda *_args, **_kwargs: self.fail("unsafe send")
                )

    def test_no_confirmation_never_runs_send(self):
        with patch("builtins.input", return_value="NO"), patch(
            "v108.test_local_iphone_push.send_local_connection_test",
            side_effect=AssertionError("must not send")
        ):
            self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()
