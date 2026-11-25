"""Private Windows launcher for V1.07.1: live Fugle scanner and Apple Web Push.

One command after Fugle confirms the intended private derived alert use.
Always fail closed on missing authorization, broker eligibility or subscription.
No orders; no key stored; no public market data published.
"""
import base64
from contextlib import closing
from getpass import getpass
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen


PRIVATE = Path.home() / ".ai-daytrade-private"
ORIGIN = "https://lishengchen01.github.io"
HEALTH = "http://127.0.0.1:8787/api/v1/health"


def server_online():
    try:
        with urlopen(Request(HEALTH, headers={"Origin": ORIGIN}), timeout=3) as r:
            return r.status == 200 and json.load(r).get("status") == "online"
    except (OSError, ValueError, TimeoutError):
        return False


def subscriptions_count(db_path):
    if not db_path.is_file():
        return 0
    try:
        with closing(sqlite3.connect(str(db_path), timeout=5)) as db:
            return int(db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0])
    except (sqlite3.Error, ValueError, TypeError):
        return 0


def local_config(path):
    """Broker verification is always explicitly confirmed on this Windows PC."""
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if data.get("broker_permission_verified") is not True or data.get("broker_sell_first_verified") is not True:
            raise ValueError("私人設定尚未確認雙向現股當沖資格；停止掃描")
        return data
    confirm = input("本人已向券商確認『先買後賣』與『先賣後買』權限？輸入 BROKER：").strip()
    if confirm != "BROKER":
        raise ValueError("尚未確認雙向現股當沖資格；停止掃描")
    data = {"market_index_symbol": "", "broker_permission_verified": True,
            "broker_sell_first_verified": True}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def vapid_public(private_key_path):
    from cryptography.hazmat.primitives.serialization import (load_pem_private_key, Encoding, PublicFormat)
    with private_key_path.open("rb") as f:
        key = load_pem_private_key(f.read(), password=None)
    raw = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main():
    print("AI 台股智慧當沖 Pro V1.07.1｜私人盤中掃描 + iPhone 推播")
    print("只提醒多空研究條件，不下單；任何授權或資料不足均不發正式訊號。")
    print("Fugle 官方未明確確認用途前，請不要輸入 LICENSED。")
    license_confirm = input("已獲 Fugle 明確確認可在本人裝置接收私人衍生訊號？輸入 LICENSED：").strip()
    if license_confirm != "LICENSED":
        print("停止：Fugle 私人衍生訊號推播用途尚未確認，不會啟動掃描或發通知。")
        return 2

    private_key = PRIVATE / "vapid-private.pem"
    pairing = PRIVATE / "pairing-token.txt"
    db_path = PRIVATE / "push.sqlite3"
    conf_path = PRIVATE / "private-config.json"
    if not private_key.is_file() or not pairing.is_file():
        print("停止：找不到原本的私人 Web Push 設定。請勿重新產生金鑰取代既有訂閱。")
        return 2
    if len(pairing.read_text(encoding="utf-8").strip()) < 32:
        print("停止：原本的私人配對碼無效。")
        return 2
    count = subscriptions_count(db_path)
    if count == 0:
        print("停止：找不到已訂閱的 iPhone。先用 APP 測試遠端推播；不重設金鑰。")
        return 2
    try:
        local_config(conf_path)
        public = vapid_public(private_key)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("停止：私人設定異常：", type(exc).__name__, str(exc))
        return 2

    contact = input("輸入先前 VAPID 使用的聯絡 Email（僅存在本次程序）：").strip()
    if not contact or "@" not in contact:
        print("停止：沒有有效的聯絡 Email。")
        return 2
    key = getpass("輸入 Fugle API Key（不顯示、不寫檔）：").strip()
    if not key:
        print("停止：Fugle API Key 為空。")
        return 2

    env = os.environ.copy()
    env.update({"FUGLE_API_KEY": key,
                "FUGLE_PRIVATE_USE_CONFIRMED": "YES",
                "WEBPUSH_DERIVED_SIGNAL_ALLOWED": "YES",
                "PRIVATE_CONFIG_FILE": str(conf_path),
                "DAYTRADE_DB_PATH": str(db_path),
                "VAPID_PRIVATE_KEY_PATH": str(private_key),
                "VAPID_PUBLIC_KEY": public,
                "VAPID_SUBJECT": contact if contact.startswith("mailto:") else "mailto:" + contact,
                "PUSH_PAIRING_TOKEN": pairing.read_text(encoding="utf-8").strip()})
    del key
    server = None
    try:
        if not server_online():
            # Server receives only push secrets, never the Fugle market-data key.
            server_env = env.copy()
            server_env.pop("FUGLE_API_KEY", None)
            server = subprocess.Popen([sys.executable, "-m", "v1071.serve"], env=server_env)
            for _ in range(20):
                if server_online():
                    break
                if server.poll() is not None:
                    break
                time.sleep(0.25)
            if not server_online():
                print("停止：私人推播伺服器未正常啟動（8787 連接埠）。")
                return 2
        print(f"私人推播服務正常；已訂閱裝置：{count}。Tailscale HTTPS 仍須保持運作。")
        print("只在交易日 09:07～13:20 執行真實策略掃描。按 Ctrl+C 結束。")
        # Real scanner has its own fail-closed checks; NEVER disable them here.
        scanner_env = env.copy()
        scanner_env.pop("PUSH_PAIRING_TOKEN", None)  # scanning needs VAPID signing, not phone subscription auth
        return subprocess.call([sys.executable, "-m", "v1071.scan_loop"], env=scanner_env)
    except KeyboardInterrupt:
        print("已停止私人掃描。")
        return 0
    finally:
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
