"""No-network CI for V1.08 private background shadow runner."""
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v108 import shadow_loop as shadow
from v108.install_shadow import _schedule_args, TASK
from v108.key_store import _dpapi, SecretStoreError

TW = shadow.TW


class ShadowModeTests(unittest.TestCase):
    def test_session_gate(self):
        self.assertTrue(shadow.is_market_session(datetime(2026, 11, 27, 9, 7, tzinfo=TW)))
        self.assertFalse(shadow.is_market_session(datetime(2026, 11, 27, 9, 6, tzinfo=TW)))
        self.assertFalse(shadow.is_market_session(datetime(2026, 11, 27, 13, 21, tzinfo=TW)))
        self.assertFalse(shadow.is_market_session(datetime(2026, 11, 28, 10, 0, tzinfo=TW)))
        self.assertEqual(shadow.PERIOD_SECONDS, 300)

    def test_outside_session_does_not_touch_client(self):
        def forbidden(*args, **kwargs):
            self.fail("no scan may run off-session")
        summary = shadow.scan_summary(None, now=datetime(2026, 11, 28, 10, 0, tzinfo=TW),
                                      audit=forbidden)
        self.assertEqual(summary["status"], "outside_session")
        self.assertEqual(summary["requests"], 0)

    def test_safe_aggregate_does_not_store_ticker_or_secrets(self):
        raw = {
            "策略未通過：跳空幅度未達2至4%": 2,
            "個股報價原因：6148": 1,
            "api_key": 1,
            "private_token": 1,
            "lastTradePrice": 1,
            "量能不足": 3,
            "壞資料": "raw quote",
        }
        cleaned = shadow._safe_aggregate(raw)
        self.assertEqual(cleaned, {
            "策略未通過：跳空幅度未達2至4%": 2,
            "量能不足": 3,
        })

    def test_qualified_stock_names_never_persist(self):
        class FakeClient:
            pass
        def fake_audit(_client, now):
            return {
                "status": "completed",
                "requests": 29,
                "signals": [("6148", "LONG_CONDITIONS"), ("2330", "SHORT_CONDITIONS")],
                "diagnostics": {"盤後初篩候選數": 5, "策略未通過：首根K方向": 2},
            }
        out = shadow.scan_summary(FakeClient(), now=datetime(2026, 11, 27, 10, 0, tzinfo=TW),
                                  audit=fake_audit)
        text = json.dumps(out, ensure_ascii=False)
        self.assertEqual(out["qualified_count"], 2)
        self.assertEqual(out["requests"], 29)
        self.assertNotIn("6148", text)
        self.assertNotIn("2330", text)
        self.assertNotIn("LONG_CONDITIONS", text)
        self.assertNotIn("Fugle API Key", text)

    def test_auth_and_broker_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "settings.json"
            for data in [
                {}, {"personal_fugle_use_confirmed": True},
                {"personal_fugle_use_confirmed": True,
                 "broker_permission_verified": True},
            ]:
                p.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    shadow.read_settings(p)
            p.write_text(json.dumps({
                "personal_fugle_use_confirmed": True,
                "broker_permission_verified": True,
                "broker_sell_first_verified": True,
            }), encoding="utf-8")
            self.assertTrue(shadow.read_settings(p)["broker_sell_first_verified"])

    def test_local_status_atomic_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "status.json"
            shadow._atomic_json(target, {"status":"completed", "count":4})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["count"], 4)

    def test_task_install_does_not_touch_existing_private_push_task(self):
        args = _schedule_args(r"C:\Python\pythonw.exe",
                              r"C:\智慧當沖2\ai-daytrade-main\v108\start_hidden.py")
        self.assertIn("ONLOGON", args)
        self.assertIn(TASK, args)
        self.assertNotIn("AI-Daytrade-Private-Push", " ".join(args))
        self.assertIn("start_hidden.py", " ".join(args))

    def test_windows_dpapi_is_user_scoped(self):
        import sys
        if sys.platform != "win32":
            with self.assertRaises(SecretStoreError):
                _dpapi(b"fake", False)
        else:
            clear = b"fake-only-ci-key-1234567"
            encrypted = _dpapi(clear, False)
            self.assertNotEqual(clear, encrypted)
            self.assertEqual(_dpapi(encrypted, True), clear)


if __name__ == "__main__":
    unittest.main()
