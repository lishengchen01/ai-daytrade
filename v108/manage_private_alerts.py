"""V1.08.2 owner-only iPhone private signal alert activation controls.

Local Windows only. Requires explicit owner confirmation, current running
shadow scanner, sole existing validated Apple subscription, DPAPI decryption
and matching VAPID key. No Fugle or broker orders, HTTP or Apple push calls.
"""
from contextlib import closing
from datetime import datetime, timezone
import argparse
import getpass
import hashlib
import json
import locale
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile

from v1071.push_service import _is_apple_endpoint
from .key_store import load_key, SecretStoreError
from .local_dispatch import PRIVATE_ROOT, OPT_IN, _config, owner_device_matches
from .shadow_loop import SETTINGS, STATUS, VERSION, read_settings

TASK = "AI-Daytrade-V108-Shadow"
MAX_STATUS_AGE_SECONDS = 660


def _local_task_matches(project_root):
    if sys.platform != "win32":
        return False
    try:
        process = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", TASK, "/XML"],
            capture_output=True, timeout=20, check=False
        )
        raw = process.stdout
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            xml = raw.decode("utf-16", errors="replace")
        else:
            xml = raw.decode(locale.getpreferredencoding(False), errors="replace")
        expected = str((project_root / "v108" / "start_hidden.py").resolve())
        return process.returncode == 0 and expected.casefold() in xml.casefold()
    except (OSError, subprocess.TimeoutExpired):
        return False


def _status_is_fresh(path=STATUS, clock=None):
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if obj.get("version") != VERSION:
            return False
        t = datetime.fromisoformat(obj["checked_at"])
        if t.tzinfo is None:
            return False
        present = (clock or (lambda: datetime.now(timezone.utc)))()
        age = (present.astimezone(timezone.utc) -
               t.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= MAX_STATUS_AGE_SECONDS and obj.get("status") in (
            "completed", "outside_session"
        )
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return False


def _one_owner_subscription(root):
    """Return a fingerprint, NEVER the endpoint, keys or a subscription URL."""
    root = Path(root)
    db_file = root / "push.sqlite3"
    if not db_file.is_file():
        raise RuntimeError("找不到原本的私人推播訂閱資料庫")
    try:
        uri = db_file.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
            rows = db.execute(
                "SELECT endpoint,p256dh,auth FROM subscriptions LIMIT 2"
            ).fetchall()
    except (sqlite3.Error, ValueError, OSError) as exc:
        raise RuntimeError("無法讀取既有 Apple 訂閱資料") from exc
    if len(rows) != 1:
        raise RuntimeError("必須剛好只有 1 台已配對的 iPhone（不能多台）")
    endpoint, p256dh, auth = rows[0]
    if (not _is_apple_endpoint(endpoint) or
        any(not isinstance(k, str) or not 20 <= len(k) <= 200
            for k in (p256dh, auth))):
        raise RuntimeError("既有 iPhone 訂閱內容不合法，不能啟用")
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def _subject(email):
    if not isinstance(email, str):
        raise ValueError("VAPID 聯絡 Email 格式無效")
    email = email.strip()
    if email.startswith("mailto:"):
        email = email[7:]
    if len(email) > 254 or not re.fullmatch(
        r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", email
    ):
        raise ValueError("VAPID 聯絡 Email 格式無效")
    return "mailto:" + email


def _private_key_check(root):
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.primitives.asymmetric import ec
        raw = (Path(root) / "vapid-private.pem").read_bytes()
        key = load_pem_private_key(raw, password=None)
        return isinstance(key, ec.EllipticCurvePrivateKey) and isinstance(
            key.curve, ec.SECP256R1)
    except (OSError, ValueError, TypeError, ImportError):
        return False


def verify_local_readiness(*, root=PRIVATE_ROOT, project_root=None,
                           clock=None, require_windows=True):
    """Local preflight has no network, no write, no public endpoint output."""
    root = Path(root)
    project_root = Path(project_root or Path(__file__).resolve().parents[1])
    if require_windows and sys.platform != "win32":
        raise RuntimeError("只能在原本的 Windows 電腦啟用")
    if require_windows and not _local_task_matches(project_root):
        raise RuntimeError("已安裝背景排程不在此程式資料夾，停止啟用")
    if not _status_is_fresh(root / "shadow-v108-status.json", clock=clock):
        raise RuntimeError("背景掃描不是最新 V1.08.2 或已停更，停止啟用")
    try:
        read_settings(root / "shadow-v108-settings.json")
    except (ValueError, OSError, TypeError):
        raise RuntimeError("私人 Fugle 或券商資格設定未確認，停止啟用")
    # Verify same Windows owner can REALLY decrypt DPAPI without printing it.
    try:
        checked = load_key(root / "fugle-key-v108.dpapi")
        if len(checked) < 12:
            raise RuntimeError("本機加密 Fugle Key 無效")
        checked = None
    except (SecretStoreError, RuntimeError, OSError) as exc:
        raise RuntimeError("此 Windows 帳戶無法解密原本 Fugle Key") from exc
    if not _private_key_check(root):
        raise RuntimeError("既有 VAPID 私鑰讀取或格式驗證失敗")
    return _one_owner_subscription(root)


def _atomic_write_private(path, obj):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = None
    try:
        fd, name = tempfile.mkstemp(prefix=".v1082-optin-", dir=str(path.parent))
        try:
            os.chmod(name, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(obj, fp, ensure_ascii=False, separators=(",", ":"))
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def enable(*, root=PRIVATE_ROOT, project_root=None, clock=None,
           answer=None, email=None, require_windows=True):
    """Raises on failed preflight or unconfirmed explicit local opt-in."""
    root = Path(root)
    fingerprint = verify_local_readiness(
        root=root, project_root=project_root, clock=clock,
        require_windows=require_windows)
    if _config(root / "v1082-private-notify.json") is not None:
        raise RuntimeError("已啟用，避免重複改寫；可先查狀態")
    if answer is None:
        print("僅允許本人已驗證的 1 台 iPhone 收到真實條件提醒。")
        print("無模擬訊號、不得自動下單。沒有合格股票就不會有訊息。")
        print("網路推播故障可能漏訊號，不能當成保證成交或固定獲利。")
        answer = input("確認啟用正式本人多空提醒，請輸入 ENABLE：").strip()
    if answer != "ENABLE":
        raise RuntimeError("未完成本機 ENABLE 確認，保持關閉")
    if email is None:
        print("只輸入原本 Apple Web Push 使用的 VAPID 聯絡 Email；不是 Fugle Key。")
        email = getpass.getpass("VAPID 聯絡 Email（輸入不回顯）：")
    cfg = {
        "mode": "private-owner-alerts",
        "enabled": True,
        "personal_fugle_use_confirmed": True,
        "broker_permission_verified": True,
        "broker_sell_first_verified": True,
        "iphone_connection_test_confirmed": True,
        "vapid_subject": _subject(email),
        "device_sha256": fingerprint,
        "confirmed_at": (clock or (lambda: datetime.now(timezone.utc)))().isoformat(),
    }
    dest = root / "v1082-private-notify.json"
    _atomic_write_private(dest, cfg)
    if _config(dest) is None or not owner_device_matches(root, fingerprint):
        dest.unlink(missing_ok=True)
        raise RuntimeError("啟用後安全複核未通過，已撤銷正式通知")
    return True


def disable(*, root=PRIVATE_ROOT):
    """Disable before any further new scan; never touch push subscription."""
    path = Path(root) / "v1082-private-notify.json"
    if path.exists():
        # Removing the ONLY activation config makes the next check fail closed.
        path.unlink()
    return not path.exists()


def status(*, root=PRIVATE_ROOT):
    """Minimal local status; does not display emails/endpoints/secrets."""
    root = Path(root)
    cfg = _config(root / "v1082-private-notify.json")
    return {
        "enabled": bool(cfg and owner_device_matches(root, cfg["device_sha256"])),
        "sole_device_matches": bool(cfg and owner_device_matches(root, cfg["device_sha256"])),
        "background_recent": _status_is_fresh(root / "shadow-v108-status.json"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="V1.08.2 本人 iPhone 多空通知管理")
    parser.add_argument("action", choices=("check", "enable", "disable"))
    args = parser.parse_args(argv)
    if args.action == "disable":
        disable()
        print("正式多空通知設定已移除；後續掃描不會再送出新訊號。")
        print("極短時間內已開始的推播無法撤回；如需立即中止，請用管理員工作排程器結束影子背景工作。")
        print("iPhone 配對碼、Apple 訂閱、Fugle Key、Tailscale 未被修改。")
        return 0
    if args.action == "check":
        s = status()
        print("V1.08.2 本人 iPhone 正式訊號：",
              "已開啟" if s["enabled"] else "關閉")
        print("既有唯一 iPhone 訂閱綁定：", s["sole_device_matches"])
        print("最近背景掃描時間有效：", s["background_recent"])
        print("Apple 推播供應商接受不等於 iPhone 真正收到。")
        return 0
    try:
        enable()
        print("V1.08.2 本人 iPhone 正式多空提醒已在本機授權。")
        print("僅下次台股有效交易時段出現全條件合格股票才會發送；不會自動下單。")
        print("立即停用：py -m v108.manage_private_alerts disable")
        print("檢查狀態：py -m v108.manage_private_alerts check")
        return 0
    except Exception as exc:
        print("未啟用，錯誤：", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
