"""Read-only Windows preflight for V1.08.2 private signal notifications.

Does NOT enable live notifications, send a test push, reveal secrets,
contact Fugle, or modify the existing Windows scheduled tasks.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from .local_dispatch import PRIVATE_ROOT, OPT_IN, _config, owner_device_matches


def inspect(root=PRIVATE_ROOT, config=OPT_IN):
    root = Path(root)
    info = {
        "fugle_key_exists": (root / "fugle-key-v108.dpapi").is_file(),
        "vapid_key_exists": (root / "vapid-private.pem").is_file(),
        "push_db_exists": (root / "push.sqlite3").is_file(),
        "subscribed_device_count": 0,
        "local_owner_opted_in": _config(config) is not None,
        "private_push_mode": "SHADOW_DISABLED",
    }
    if info["push_db_exists"]:
        try:
            uri = (root / "push.sqlite3").resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db, db:
                info["subscribed_device_count"] = db.execute(
                    "SELECT COUNT(*) FROM subscriptions").fetchone()[0]
        except (sqlite3.Error, ValueError):
            pass
    cfg = _config(config)
    if (info["fugle_key_exists"] and info["vapid_key_exists"] and
        info["push_db_exists"] and info["subscribed_device_count"] == 1 and
        cfg and owner_device_matches(root, cfg["device_sha256"])):
        info["private_push_mode"] = "LOCAL_PRIVATE_ENABLED"
    return info


def main():
    info = inspect()
    print("V1.08.2 本機私人通知預先檢查（唯讀，不發送訊號）")
    print("Fugle 加密金鑰存在：", info["fugle_key_exists"])
    print("既有 Apple Web Push 私鑰存在：", info["vapid_key_exists"])
    print("既有本機訂閱資料庫存在：", info["push_db_exists"])
    print("已訂閱裝置數：", info["subscribed_device_count"])
    print("本人正式訊號本機選擇加入：", info["local_owner_opted_in"])
    print("目前可啟用的模式：", info["private_push_mode"])
    print("注意：此預檢不代表 iPhone 真機顯示了多空通知。")
    print("測試與部署驗收未完成前，不應建立 enabled=true 的正式通知設定。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
