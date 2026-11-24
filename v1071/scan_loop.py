"""Run on PRIVATE always-on machine, never inside GitHub Pages or Actions.
Real Fugle scans once per minute (basic tier cap is 60 calls/minute).
No simulation, broker orders, raw quote export, or public JSON output.
"""
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import sys
import time as clock

from .fugle import FugleClient
from .scanner import scan_real
from .push_service import deliver

TW = ZoneInfo("Asia/Taipei")


def run_once(config, client=None, now=None, daily=None):
    signals, reason = scan_real(config, client=client, now=now, daily=daily)
    sent = 0
    for s in signals:
        # An actual signal is valid only if all prerequisite checks passed.
        if not s["checks"] or not all(s["checks"].values()):
            continue
        ts = datetime.fromisoformat(s["at"])
        sid = ts.date().isoformat() + ":" + s["symbol"] + ":" + s["direction"]
        payload = {"schema": "daytrade-push-v1", "type": "strategy-signal",
                   "verified": True, "sample": False, "symbol": s["symbol"],
                   "direction": s["direction"], "signalId": sid, "issuedAt": s["at"]}
        sent += deliver(payload)
    return {"candidates": len(signals), "notifications": sent, "reason": reason}


def main():
    if not os.getenv("FUGLE_API_KEY"):
        sys.exit("停止：FUGLE_API_KEY 未設定，不會使用測試資料代替")
    if os.getenv("FUGLE_PRIVATE_USE_CONFIRMED") != "YES":
        sys.exit("停止：需要先確認資料供應商允許此私人用途")
    config_file = os.getenv("PRIVATE_CONFIG_FILE")
    if not config_file:
        sys.exit("停止：PRIVATE_CONFIG_FILE 未設定；不能假設券商交易資格")
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    client = FugleClient()
    while True:
        start = clock.monotonic()
        now = datetime.now(TW)
        if now.weekday() < 5 and time(9, 7) <= now.time() <= time(13, 20):
            try:
                res = run_once(config, client=client, now=now)
                print(now.isoformat(), "候選:", res["candidates"],
                      "已送:", res["notifications"], res["reason"], flush=True)
            except Exception as exc:
                # Keep credentials, endpoint and licensed market payloads off logs.
                print(now.isoformat(), "連線／資料異常，訊號已停止。",
                      exc.__class__.__name__, flush=True)
        else:
            print(now.isoformat(), "非交易掃描時段", flush=True)
        clock.sleep(max(1, 60 - (clock.monotonic() - start)))


if __name__ == "__main__":
    main()
