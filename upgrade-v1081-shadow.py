"""Safely update an existing V1.08 Windows SHADOW task to V1.08.1.

No live notification opt-in. No Fugle key reads or writes, no VAPID access,
no production push service changes, no GitHub credential changes.
Run ONLY from the folder that owns the already installed shadow task.
"""
import ast
from datetime import datetime
import ctypes
import locale
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = "lishengchen01/ai-daytrade"
# Frozen code snapshot verified by GitHub Actions. Never download mutable main
# modules during a running upgrade.
SOURCE_COMMIT = "a7967091f256bd4c845f80e5be4baff930556c73"
TASK = "AI-Daytrade-V108-Shadow"
FILES = (
    "v1071/audit_live.py",
    "v108/shadow_loop.py",
    "v108/status.py",
    "v108/signal_bridge.py",
    "v108/test_signal_bridge.py",
)
MARKERS = {
    "v1071/audit_live.py": "verified_signals",
    "v108/shadow_loop.py": "shadow_push_summary",
    "v108/status.py": "push_ready_count",
    "v108/signal_bridge.py": "SHADOW_DISABLED",
    "v108/test_signal_bridge.py": "PushReadinessTests",
}
UNIT_TESTS = (
    "v108.test_shadow",
    "v108.test_signal_bridge",
    "v1071.test_backend",
    "v1071.test_audit_live",
)


def source_url(name):
    if name not in FILES:
        raise ValueError("不允許更新這個檔案")
    return f"https://raw.githubusercontent.com/{REPO}/{SOURCE_COMMIT}/{name}"


def validate_source(name, source):
    if name not in FILES or not isinstance(source, bytes):
        raise ValueError("下載資料格式不符")
    if not 50 <= len(source) <= 150_000:
        raise ValueError("下載大小不符，停止更新")
    try:
        decoded = source.decode("utf-8")
        ast.parse(decoded, filename=name)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError("下載 Python 語法檢查失敗") from exc
    if MARKERS[name] not in decoded:
        raise ValueError("下載程式版本不符，停止更新")


def decode_windows_output(value):
    if value.startswith((b"\xff\xfe", b"\xfe\xff")):
        return value.decode("utf-16", errors="replace")
    return value.decode(locale.getpreferredencoding(False), errors="replace")


def schtasks(*args):
    p = subprocess.run(
        ["schtasks.exe", *args], capture_output=True, timeout=25,
        check=False,
    )
    return p.returncode, decode_windows_output(p.stdout + b"\n" + p.stderr)


def ensure_same_task(root):
    code, xml = schtasks("/Query", "/TN", TASK, "/XML")
    if code != 0:
        raise RuntimeError("找不到已安裝的 V1.08 背景工作，沒有進行更新")
    expected = str((root / "v108" / "start_hidden.py").resolve()).casefold()
    if expected not in xml.casefold():
        raise RuntimeError(
            "此資料夾不是背景工作實際使用的程式位置；已停止，避免更新錯誤版本")
    if not (Path.home() / ".ai-daytrade-private" / "fugle-key-v108.dpapi").is_file():
        raise RuntimeError(
            "目前 Windows 帳戶找不到原本加密 Fugle Key；請使用最初安裝的帳戶")
    return True


def _restore(root, backup, installed):
    for name in reversed(installed):
        target = root / name
        old = backup / name
        if old.is_file():
            shutil.copy2(old, target)
        elif target.is_file():
            target.unlink()


def upgrade(root):
    if os.name != "nt" or not bool(ctypes.windll.shell32.IsUserAnAdmin()):
        raise RuntimeError("請用原本 Windows 帳戶的系統管理員 CMD 執行")
    if not all((root / x).is_file() for x in (
        "v1071/audit_live.py", "v108/shadow_loop.py",
        "v108/start_hidden.py", "v108/key_store.py",
    )):
        raise RuntimeError("請切換到已安裝的 ai-daytrade-main 程式根資料夾")
    ensure_same_task(root)
    update_root = root / ".shadow-updates"
    update_root.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = update_root / ("backup_v108_" + timestamp)
    if backup.exists():
        raise RuntimeError("備份資料夾名稱衝突，沒有進行更新")
    installed = []
    stopped = False
    successful = False
    backup.mkdir()
    try:
        # Download and validate *before* interrupting the working task.
        with tempfile.TemporaryDirectory(prefix="shadow-stage-", dir=update_root) as td:
            stage = Path(td)
            for name in FILES:
                with urllib.request.urlopen(
                    urllib.request.Request(
                        source_url(name),
                        headers={"User-Agent": "AI-Daytrade-V1081-Private-Shadow-Upgrade"},
                    ), timeout=20,
                ) as response:
                    if response.status != 200:
                        raise RuntimeError("下載來源回應異常，已取消更新")
                    raw = response.read(150_001)
                validate_source(name, raw)
                outfile = stage / name
                outfile.parent.mkdir(parents=True, exist_ok=True)
                outfile.write_bytes(raw)

            # Back up exactly the files about to be replaced.
            for name in FILES:
                src = root / name
                if src.exists():
                    dest = backup / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)

            print("全部程式已完成下載與語法驗證；開始安全切換背景工作。")
            code, info = schtasks("/End", "/TN", TASK)
            if code != 0:
                raise RuntimeError("背景工作未能停止；檔案沒有改動。請檢查排程權限")
            stopped = True
            time.sleep(2)
            try:
                for name in FILES:
                    source = stage / name
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, target)
                    installed.append(name)

                # Offline tests: never call Fugle, Apple Push, or any broker API.
                tested = subprocess.run(
                    [sys.executable, "-m", "unittest", *UNIT_TESTS],
                    cwd=root, capture_output=True, text=True,
                    timeout=120, check=False, errors="replace",
                )
                if tested.returncode != 0:
                    raise RuntimeError(
                        "離線驗證未通過，將還原 V1.08。"
                        "（安全起見不輸出可能含私人資訊的詳細 log）")
                successful = True
            except Exception:
                _restore(root, backup, installed)
                raise
    finally:
        if stopped:
            code, _ = schtasks("/Run", "/TN", TASK)
            if code != 0:
                print("注意：背景工作未能重新啟動！請在工作排程器手動執行：", TASK)
                successful = False
        print("原有 iPhone 私人推播、Tailscale、Fugle Key、配對碼均未變更。")
        print("備份位置：", backup)
    return successful


def main():
    root = Path(__file__).resolve().parent
    print("V1.08.1 安全更新工具：僅升級 V1.08 背景影子掃描。")
    print("正式交易多空通知仍然關閉，不會自動下單。")
    try:
        ok = upgrade(root)
    except Exception as exc:
        print("更新未完成，若檔案曾更動已嘗試還原。原因：", str(exc))
        return 1
    if not ok:
        print("程式已完成處理，但背景啟動尚未確認，請勿視為成功。")
        return 1
    print("V1.08.1 程式更新與離線測試成功，Windows 背景工作已要求重新啟動。")
    print("可查詢：py -m v108.status（等待最近檢查時間更新後再驗證）。")
    print("預期：push_mode=SHADOW_DISABLED，notifications_sent=0。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
