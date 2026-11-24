"""Safe Windows setup for private push service. No Fugle key collected or saved.
Run: py -m v1071.start_windows
For live strategy, use separate py -m v1071.scan_loop after necessary authorizations.
"""
from pathlib import Path
import base64
import os
import secrets
import subprocess
import sys
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PublicFormat

from .create_vapid_keys import generate


def main():
    root = Path.home() / ".ai-daytrade-private"
    root.mkdir(exist_ok=True)
    private = root / "vapid-private.pem"
    token_path = root / "pairing-token.txt"
    if not private.exists():
        generate(str(private))
    with open(private, "rb") as fh:
        key = load_pem_private_key(fh.read(), password=None)
    public = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_b64 = base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii")
    if not token_path.exists():
        with open(token_path, "x", encoding="utf-8") as fh:
            fh.write(secrets.token_urlsafe(48))
        try:
            os.chmod(token_path, 0o600)
        except OSError:
            pass
    token = token_path.read_text(encoding="utf-8").strip()
    print("私人配對碼已存在此電腦私人目錄：", str(token_path))
    print("請自行開啟該檔，將內容輸入 iPhone 的「私人配對碼」欄位；")
    print("不要在聊天、GitHub、截圖、公開網頁或網址中洩露配對碼。")
    print("這個啟動器不使用 Fugle API Key，不會產生任何真實交易訊號。")
    subject = os.getenv("VAPID_SUBJECT") or input("輸入自己的聯絡 Email（僅供 VAPID 標識，不是 API Key）：").strip()
    if not subject or "@" not in subject:
        sys.exit("必須設定有效聯絡 Email，已停止")
    env = os.environ.copy()
    env.pop("FUGLE_API_KEY", None)
    env["PUSH_PAIRING_TOKEN"] = token
    env["VAPID_PRIVATE_KEY_PATH"] = str(private)
    env["VAPID_PUBLIC_KEY"] = public_b64
    env["VAPID_SUBJECT"] = subject if subject.startswith("mailto:") else "mailto:" + subject
    # Explicitly prevent live signal delivery in this bootstrap process.
    env["WEBPUSH_DERIVED_SIGNAL_ALLOWED"] = "NO"
    print("私人推播服務將在 http://127.0.0.1:8787 啟動。")
    print("這是本機 HTTP，iPhone 還需要 Tailscale Funnel 等合法 HTTPS 入口。")
    print("按 Ctrl+C 停止服務，Windows 休眠時推播也會停止。")
    proc = subprocess.Popen([sys.executable, "-m", "v1071.serve"], env=env)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
