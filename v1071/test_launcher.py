"""Offline launcher regression tests: no real APIs, no orders, no secrets."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .launch_live_windows import local_config, subscriptions_count, main


class LauncherTests(unittest.TestCase):
    def test_unconfirmed_fugle_license_never_launches(self):
        with patch("builtins.input", return_value="NO"), patch("subprocess.call") as call:
            self.assertEqual(main(), 2)
            call.assert_not_called()

    def test_missing_private_secrets_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp, patch("builtins.input", return_value="LICENSED"):
            with patch("v1071.launch_live_windows.PRIVATE", Path(tmp)):
                with patch("subprocess.call") as call:
                    self.assertEqual(main(), 2)
                    call.assert_not_called()

    def test_subscription_count_closes_sqlite_for_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "push.sqlite3"
            self.assertEqual(subscriptions_count(db_path), 0)
            with sqlite3.connect(str(db_path)) as db:
                db.execute("CREATE TABLE subscriptions(endpoint TEXT PRIMARY KEY)")
                db.execute("INSERT INTO subscriptions VALUES ('https://web.push.apple.com/foo')")
            self.assertEqual(subscriptions_count(db_path), 1)
            db_path.unlink()
            self.assertFalse(db_path.exists())

    def test_broker_config_requires_local_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private-config.json"
            with patch("builtins.input", return_value="NO"):
                with self.assertRaises(ValueError):
                    local_config(path)
            self.assertFalse(path.exists())
            with patch("builtins.input", return_value="BROKER"):
                data = local_config(path)
            self.assertTrue(data["broker_permission_verified"])
            self.assertTrue(data["broker_sell_first_verified"])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), data)
            data["broker_sell_first_verified"] = False
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                local_config(path)


if __name__ == "__main__":
    unittest.main()
