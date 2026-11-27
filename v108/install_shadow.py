"""One-time opt-in installation for PRIVATE Windows V1.08 SHADOW scans.

Keeps existing V1.07.2 push scheduled task unchanged. This installer creates
a SEPARATE login-only shadow task. It never enables strategy push or orders.
"""
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from .key_store import save_key, SecretStoreError
from .shadow_loop import ROOT, SETTINGS, STATUS

TASK = "AI-Daytrade-V108-Shadow"
TW = ZoneInfo("Asia/Taipei")


def _save_settings():
    data = {
        "mode": "shadow-no-push",
        "personal_fugle_use_confirmed": True,
        "broker_permission_verified": True,
        "broker_sell_first_verified": True,
        "confirmed_at": datetime.now(TW).isoformat(),
    }
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS)


def _schedule_args(pythonw, script):
    return [
        "schtasks.exe", "/Create", "/F", "/TN", TASK,
        "/SC", "ONLOGON",
        "/TR", f'"{pythonw}" "{script}"',
    ]


def main():
    if sys.platform != "win32":
        print("此安裝器只支援 Windows。")
        return 1
    print("V1.08 私人 Fugle 背景影子掃描安裝器")
    print("每天正常台股交易日 09:07–13:20 約每五分鐘檢查一次。")
    print("只留本機匿名統計，不會發正式多空推播，也不會下單。")
    print("原本的 V1.07.2 iPhone 推播、配對碼與 Tailscale 不會更動。")
    if input("Fugle 已確認你描述的本人私人用途，輸入 YES：").strip() != "YES":
        print("未確認授權，沒有安裝。")
        return 1
    if input("本人券商先買後賣、先賣後買現股當沖皆已開通，輸入 YES：").strip() != "YES":
        print("未確認券商資格，沒有安裝。")
        return 1
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script = Path(__file__).resolve().with_name("start_hidden.py")
    if not pythonw.is_file() or not script.is_file():
        print("找不到 Windows pythonw.exe 或 V1.08 啟動檔；沒有安裝。")
        return 1
    key = getpass.getpass("Fugle API Key（本機輸入，不回顯）：").strip()
    if not key:
        print("沒有輸入 Key，已停止。")
        return 1
    try:
        save_key(key)
    except SecretStoreError:
        print("Windows 使用者金鑰保護失敗；已停止。")
        return 1
    finally:
        key = None
    _save_settings()
    try:
        completed = subprocess.run(
            _schedule_args(pythonw, script), capture_output=True,
            text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Windows 工作排程器無法執行。未完成自動安裝；請檢查權限。")
        return 1
    if completed.returncode:
        print("建立排程工作失敗（錯誤碼", completed.returncode, "）。")
        print("未修改原本的私人 Web Push 排程。")
        return 1
    print("影子掃描排程已建立：", TASK)
    print("下次登入 Windows 將自動啟動；若要立即啟動，可在工作排程器按「執行」。")
    print("本機狀態：", STATUS)
    print("此工作只在登入目前 Windows 使用者時運作；睡眠／關機不會掃描。")
    print("正式多空訊號推播：仍然關閉。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
