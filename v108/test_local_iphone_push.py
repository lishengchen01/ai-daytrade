"""One-shot iPhone connection test FROM THE LOCAL WINDOWS PYTHON PROCESS.

Does not need Fugle API Key or live-strategy opt-in. Uses the existing private
local Apple Push subscription + VAPID key, and sends only a genuine
connection-test payload. Never sends a fabricated trade signal or an order.
"""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import getpass
import os
from pathlib import Path
import re
import sqlite3

from .local_dispatch import PRIVATE_ROOT

TEST_LABEL = "connection-test"


def _validate_contact_email(address):
    if not isinstance(address, str):
        return None
    value = address.strip()
    if value.startswith("mailto:"):
        value = value[7:]
    if (len(value) > 254 or
        not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value)):
        return None
    return "mailto:" + value


@contextmanager
def _only_connection_test_environment(root, subject):
    """No strategy-signal enable; always restore caller's prior environment."""
    names = (
        "WEBPUSH_DERIVED_SIGNAL_ALLOWED", "VAPID_PRIVATE_KEY_PATH",
        "VAPID_SUBJECT", "DAYTRADE_DB_PATH",
    )
    previous = {name: os.environ.get(name) for name in names}
    try:
        os.environ.update({
            "WEBPUSH_DERIVED_SIGNAL_ALLOWED": "NO",
            "VAPID_PRIVATE_KEY_PATH": str(root / "vapid-private.pem"),
            "VAPID_SUBJECT": subject,
            "DAYTRADE_DB_PATH": str(root / "push.sqlite3"),
        })
        yield
    finally:
        for name, old in previous.items():
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old


def send_local_connection_test(*, root=PRIVATE_ROOT, subject, sender=None,
                               now=None):
    """Returns minimal aggregate outcome; no API keys or URLs leave this module.

    A positive integer means a push service provider accepted requests, not
    that the iPhone displayed them. Mock sender is used by offline CI only.
    """
    root = Path(root)
    subject = _validate_contact_email(subject)
    if subject is None:
        raise ValueError("VAPID 聯絡 Email 格式錯誤")
    private_key = root / "vapid-private.pem"
    database = root / "push.sqlite3"
    if not private_key.is_file() or not database.is_file():
        raise RuntimeError("找不到原本私人推播資料庫或 Apple 推播私鑰；未發送")
    try:
        uri = database.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=3)) as db:
            registered = db.execute(
                "SELECT COUNT(*) FROM subscriptions"
            ).fetchone()[0]
    except (sqlite3.Error, ValueError) as exc:
        raise RuntimeError("本機私人訂閱資料庫無法讀取；未發送") from exc
    if registered <= 0:
        raise RuntimeError("沒有已訂閱的 iPhone 裝置；未發送")

    payload = {
        "schema": "daytrade-push-v1",
        "type": TEST_LABEL,
        "test": True,
        "issuedAt": (now or datetime.now(timezone.utc)).astimezone(
            timezone.utc).isoformat(),
    }
    if sender is None:
        # No production signal dispatch import, no per-stock payload.
        from v1071.push_service import deliver
        sender = deliver
    with _only_connection_test_environment(root, subject):
        accepted = sender(payload, allow_test=True)
    if type(accepted) is not int or accepted < 0:
        accepted = 0
    return {
        "test_type": TEST_LABEL,
        "subscribed_devices_before": int(registered),
        "provider_accepted": accepted,
        "strategy_signals_sent": 0,
        "orders_placed": 0,
        "live_signal_enabled": False,
    }


def main():
    print("V1.08.2｜Windows 本機 Apple Web Push 連線測試")
    print("只會傳送一則「私人遠端推播測試」到既有 iPhone 訂閱。")
    print("不讀 Fugle 行情，不發做多／做空訊號，不會下單。")
    print("原本的 V1.08.2 影子背景掃描及正式訊號開關均保持不變。")
    answer = input("確認只發送一則連線測試通知，輸入 YES：").strip()
    if answer != "YES":
        print("使用者未確認，未發送。")
        return 1
    print("請輸入設定私人推播服務時使用的 VAPID 聯絡 Email（不是 Fugle Key）。")
    subject = getpass.getpass("VAPID 聯絡 Email（不顯示、不儲存）：")
    try:
        result = send_local_connection_test(subject=subject)
    except Exception as exc:
        # Never include sensitive traceback, endpoint, email or PEM content.
        print("本機測試無法完成：", str(exc))
        return 1
    print("私人訂閱裝置數（發送前）：", result["subscribed_devices_before"])
    print("Apple Web Push 供應商接受請求數：", result["provider_accepted"])
    print("正式多空訊號：仍關閉；下單數：0")
    if result["provider_accepted"] > 0:
        print("請檢查 iPhone 是否收到「智慧當沖｜私人遠端推播測試」。")
        print("注意：供應商接受不代表 iPhone 已實際顯示，需要本人確認。")
        return 0
    print("未獲供應商接受，無法確認送達。請勿啟用正式多空通知。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
