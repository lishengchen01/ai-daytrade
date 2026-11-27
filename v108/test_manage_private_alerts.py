"""Offline owner-only activation and emergency-disable safety regressions.

No actual secret, Fugle quote, order or Apple Web Push traffic.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from v108 import manage_private_alerts as cli
from v108.local_dispatch import _config, owner_device_matches


class OwnerActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.email = "owner-test@example.org"
        self.now = datetime(2026, 11, 27, 17, 45, tzinfo=timezone(timedelta(hours=8)))
        self.endpoint = "https://web.push.apple.com/only-iphone"
        self.db_file = self.root / "push.sqlite3"
        with closing(sqlite3.connect(str(self.db_file))) as db, db:
            db.execute("""CREATE TABLE subscriptions(
                endpoint TEXT PRIMARY KEY, p256dh TEXT, auth TEXT, created_at TEXT
            )""")
            db.execute(
                "INSERT INTO subscriptions VALUES (?,?,?,?)",
                (self.endpoint, "p"*87, "a"*22, self.now.isoformat()),
            )
        (self.root / "shadow-v108-settings.json").write_text(
            json.dumps({"personal_fugle_use_confirmed": True,
                        "broker_permission_verified": True,
                        "broker_sell_first_verified": True}), encoding="utf-8"
        )
        self._write_status(self.now)
        (self.root / "fugle-key-v108.dpapi").write_bytes(b"MOCK-ENCRYPTED-DATA-NO-REAL-KEY")
        (self.root / "vapid-private.pem").write_bytes(b"MOCK-ONLY")
        self.patches = [
            patch.object(cli, "load_key", return_value="fake-only-key-long-enough"),
            patch.object(cli, "_private_key_check", return_value=True),
        ]
        for patched in self.patches:
            patched.start()
            self.addCleanup(patched.stop)

    def _write_status(self, at):
        (self.root / "shadow-v108-status.json").write_text(json.dumps({
            "version": "V1.08.2-shadow", "status": "outside_session",
            "checked_at": at.isoformat(),
        }), encoding="utf-8")

    def _enable(self, answer="ENABLE", **kw):
        email = kw.pop("email", self.email)
        return cli.enable(
            root=self.root, require_windows=False, clock=lambda: self.now,
            answer=answer, email=email, **kw
        )

    def test_explicit_enable_and_matching_sole_device(self):
        self.assertFalse((self.root / "v1082-private-notify.json").exists())
        self.assertTrue(self._enable())
        cfg = _config(self.root / "v1082-private-notify.json")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["vapid_subject"], "mailto:" + self.email)
        self.assertEqual(cfg["device_sha256"], hashlib.sha256(
            self.endpoint.encode("utf-8")).hexdigest())
        self.assertTrue(owner_device_matches(self.root, cfg["device_sha256"]))
        data = (self.root / "v1082-private-notify.json").read_text(encoding="utf-8")
        self.assertNotIn(self.endpoint, data)
        self.assertNotIn("fake-only-key", data)
        self.assertNotIn("pairing-token", data)
        with self.assertRaises(RuntimeError):
            self._enable()  # never silently overwrite a live opt-in

    def test_denied_optin_must_not_write(self):
        with self.assertRaises(RuntimeError):
            self._enable(answer="NO")
        self.assertFalse((self.root / "v1082-private-notify.json").exists())
        with self.assertRaises(ValueError):
            self._enable(email="not-an-email")

    def test_stale_or_wrong_version_blocks_activation(self):
        self._write_status(self.now - timedelta(minutes=15))
        with self.assertRaises(RuntimeError):
            self._enable()
        self._write_status(self.now)
        (self.root / "shadow-v108-status.json").write_text(json.dumps({
            "version": "V1.08.1-shadow", "status": "completed",
            "checked_at": self.now.isoformat(),
        }), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self._enable()

    def test_only_matching_one_device_allowed(self):
        with closing(sqlite3.connect(str(self.db_file))) as db, db:
            db.execute("INSERT INTO subscriptions VALUES (?,?,?,?)",
                       ("https://web.push.apple.com/other-device",
                        "x"*87, "y"*22, self.now.isoformat()))
        with self.assertRaises(RuntimeError):
            self._enable()
        self.assertFalse((self.root / "v1082-private-notify.json").exists())

    def test_swapped_or_extra_subscription_automatically_disables_status(self):
        self._enable()
        with closing(sqlite3.connect(str(self.db_file))) as db, db:
            db.execute("DELETE FROM subscriptions")
            db.execute(
                "INSERT INTO subscriptions VALUES (?,?,?,?)",
                ("https://web.push.apple.com/replaced-device",
                 "x"*87, "y"*22, self.now.isoformat()),
            )
        cfg = _config(self.root / "v1082-private-notify.json")
        self.assertIsNotNone(cfg)
        self.assertFalse(owner_device_matches(self.root, cfg["device_sha256"]))

    def test_disable_is_safe_and_never_unsubscribes(self):
        self._enable()
        self.assertTrue(cli.disable(root=self.root))
        self.assertIsNone(_config(self.root / "v1082-private-notify.json"))
        with closing(sqlite3.connect(str(self.db_file))) as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0], 1
            )
        self.assertTrue(cli.disable(root=self.root))

    def test_unreadable_dpapi_blocks_without_exposing_key(self):
        from v108.key_store import SecretStoreError
        with patch.object(cli, "load_key",
                          side_effect=SecretStoreError("bad secret")):
            with self.assertRaises(RuntimeError) as ex:
                self._enable()
            self.assertNotIn("bad secret", str(ex.exception))
        self.assertFalse((self.root / "v1082-private-notify.json").exists())


if __name__ == "__main__":
    unittest.main()
