"""Offline tests for V1.07.2 Windows background push, no network or orders."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, NoEncryption,
)
from v1071.push_background import prepare_environment


class PrivateBackgroundTests(unittest.TestCase):
    def test_missing_private_files_fail_closed(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "missing private"):
                prepare_environment(Path(tmp))

    def test_existing_keys_preserved_and_live_signals_forced_off(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = ec.generate_private_key(ec.SECP256R1())
            raw = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
            priv = root / "vapid-private.pem"
            priv.write_bytes(raw)
            (root / "pairing-token.txt").write_text("q" * 48, encoding="utf-8")
            (root / "push-background.json").write_text(
                json.dumps({"vapid_contact_email": "owner@example.com"}), encoding="utf-8")
            with patch.dict(os.environ, {
                "FUGLE_API_KEY": "must-not-survive",
                "FUGLE_PRIVATE_USE_CONFIRMED": "YES",
                "WEBPUSH_DERIVED_SIGNAL_ALLOWED": "YES",
            }):
                public = prepare_environment(root)
                self.assertTrue(len(public) > 75)
                self.assertEqual(os.environ["WEBPUSH_DERIVED_SIGNAL_ALLOWED"], "NO")
                self.assertNotIn("FUGLE_API_KEY", os.environ)
                self.assertNotIn("FUGLE_PRIVATE_USE_CONFIRMED", os.environ)
                self.assertEqual(os.environ["VAPID_SUBJECT"], "mailto:owner@example.com")
                self.assertEqual(os.environ["DAYTRADE_DB_PATH"], str(root / "push.sqlite3"))
            self.assertEqual(priv.read_bytes(), raw)

    def test_invalid_pairing_token_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("vapid-private.pem", "pairing-token.txt"):
                (root / name).write_text("short", encoding="utf-8")
            (root / "push-background.json").write_text(
                '{"vapid_contact_email":"owner@example.com"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid pairing"):
                prepare_environment(root)


if __name__ == "__main__":
    unittest.main()
