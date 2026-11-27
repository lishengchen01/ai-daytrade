"""V1.08 private Windows SHADOW scanner. Research-only, no push or orders.

Runs at most once per 5 minutes during the ordinary Taiwan session.
Sends nothing to GitHub, browsers or the private push server.
Stores only aggregate gate counts in the user's PRIVATE Windows directory.
"""
from datetime import datetime, time
import ctypes
from ctypes import wintypes
import json
import os
import re
from pathlib import Path
import tempfile
import time as clock
from zoneinfo import ZoneInfo

from v1071.audit_live import audit_once
from v1071.fugle import FugleClient
from .key_store import load_key, SecretStoreError

TW = ZoneInfo("Asia/Taipei")
VERSION = "V1.08-shadow.1"
PERIOD_SECONDS = 300
ROOT = Path.home() / ".ai-daytrade-private"
SETTINGS = ROOT / "shadow-v108-settings.json"
STATUS = ROOT / "shadow-v108-status.json"
HISTORY = ROOT / "shadow-v108-history.jsonl"


def is_market_session(now):
    now = now.astimezone(TW)
    return now.weekday() < 5 and time(9, 7) <= now.time() <= time(13, 20)


def read_settings(path=SETTINGS):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or any(
        data.get(key) is not True for key in
        ("personal_fugle_use_confirmed", "broker_permission_verified",
         "broker_sell_first_verified")
    ):
        raise ValueError("私人授權或券商資格沒有確認")
    return data


def _safe_aggregate(diag):
    # Never emit ticker, source quote, price, endpoint or error detail.
    if not isinstance(diag, dict):
        return {}
    return {
        key: value for key, value in diag.items()
        if isinstance(key, str) and len(key) <= 90
        and re.search(r"[0-9]{4,6}", key) is None
        and not any(x in key.lower() for x in
                    ("key", "token", "symbol", "endpoint", "http", "price"))
        and type(value) is int and 0 <= value <= 100
    }


def scan_summary(client, now=None, audit=audit_once):
    now = (now or datetime.now(TW)).astimezone(TW)
    if not is_market_session(now):
        return {"version": VERSION, "checked_at": now.isoformat(),
                "status": "outside_session", "qualified_count": 0,
                "requests": 0, "gate_counts": {}}
    result = audit(client, now=now)
    return {
        "version": VERSION,
        "checked_at": datetime.now(TW).isoformat(),
        "status": result.get("status", "unknown"),
        "qualified_count": len(result.get("signals", [])),
        "requests": result.get("requests"),
        "gate_counts": _safe_aggregate(result.get("diagnostics")),
    }


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".shadow-v108-", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(value, fp, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def _record(state):
    _atomic_json(STATUS, state)
    # History has no per-stock codes or prices. Rotate to bound disk usage.
    if HISTORY.exists() and HISTORY.stat().st_size > 1024 * 1024:
        os.replace(HISTORY, HISTORY.with_suffix(".previous.jsonl"))
    with HISTORY.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n")


class _WindowsSingleton:
    """Prevent two GUI/background scanners on the same Windows login."""
    def __enter__(self):
        if os.name != "nt":
            raise RuntimeError("只支援 Windows 背景模式")
        win = ctypes.WinDLL("kernel32", use_last_error=True)
        win.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        win.CreateMutexW.restype = wintypes.HANDLE
        self.win = win
        self.handle = win.CreateMutexW(None, False, "Local\\AI_Daytrade_V108_Shadow")
        if not self.handle:
            raise RuntimeError("無法建立背景程序單例")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            win.CloseHandle(self.handle)
            self.handle = None
            raise RuntimeError("背景程序已經啟動，不可重複執行")
        return self

    def __exit__(self, *unused):
        if self.handle:
            self.win.CloseHandle(self.handle)


def run_forever():
    # This is deliberately NOT the production signal sender. In particular
    # it never imports v1071.push_service or calls scan_loop.run_once.
    with _WindowsSingleton():
        while True:
            began = clock.monotonic()
            now = datetime.now(TW)
            if not is_market_session(now):
                _atomic_json(STATUS, {
                    "version": VERSION, "checked_at": now.isoformat(),
                    "status": "outside_session", "qualified_count": 0,
                    "requests": 0, "gate_counts": {},
                })
            else:
                try:
                    read_settings()
                    client = FugleClient(key=load_key())
                    state = scan_summary(client, now=now)
                except Exception as exc:
                    # Log ERROR TYPE only. Never include exceptions' string,
                    # market payload, token, API key, or individual tickers.
                    state = {
                        "version": VERSION, "checked_at": now.isoformat(),
                        "status": "blocked_or_error", "error_type": type(exc).__name__,
                        "qualified_count": 0, "requests": 0, "gate_counts": {},
                    }
                _record(state)
            clock.sleep(max(10, PERIOD_SECONDS - (clock.monotonic() - began)))


if __name__ == "__main__":
    run_forever()
