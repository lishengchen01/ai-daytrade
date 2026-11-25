"""Run V1.07.1 *test-only* Web Push service silently on Windows logon.

Requires existing private VAPID key, pairing token, and iPhone subscription.
Does not read Fugle market data and cannot enable derived strategy signals.
"""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, load_pem_private_key,
)

PRIVATE = Path.home() / ".ai-daytrade-private"
ORIGIN = "https://lishengchen01.github.io"


def prepare_environment(private=PRIVATE):
    """Fail closed and reuse existing keys; don't generate/overwrite anything."""
    required = ("vapid-private.pem", "pairing-token.txt", "push-background.json")
    missing = [name for name in required if not (private / name).is_file()]
    if missing:
        raise ValueError("missing private configuration: " + ", ".join(missing))

    token = (private / "pairing-token.txt").read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise ValueError("invalid pairing token")
    config = json.loads((private / "push-background.json").read_text(encoding="utf-8"))
    email = config.get("vapid_contact_email", "")
    if not isinstance(email, str) or "@" not in email or any(c.isspace() for c in email):
        raise ValueError("invalid contact email")

    key_path = private / "vapid-private.pem"
    with key_path.open("rb") as f:
        priv = load_pem_private_key(f.read(), password=None)
    pub = priv.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_key = base64.urlsafe_b64encode(pub).rstrip(b"=").decode("ascii")

    # Explicit test-only mode regardless of machine-wide variables.
    os.environ.pop("FUGLE_API_KEY", None)
    os.environ.pop("FUGLE_PRIVATE_USE_CONFIRMED", None)
    os.environ["WEBPUSH_DERIVED_SIGNAL_ALLOWED"] = "NO"
    os.environ["DAYTRADE_DB_PATH"] = str(private / "push.sqlite3")
    os.environ["PUSH_PAIRING_TOKEN"] = token
    os.environ["VAPID_PRIVATE_KEY_PATH"] = str(key_path)
    os.environ["VAPID_PUBLIC_KEY"] = public_key
    os.environ["VAPID_SUBJECT"] = "mailto:" + email.removeprefix("mailto:")
    return public_key


def main():
    PRIVATE.mkdir(exist_ok=True)
    log = PRIVATE / "push-background.log"
    # pythonw.exe has no console. Record only general service state, never tokens,
    # subscription endpoints, private key contents, or market data.
    with log.open("a", encoding="utf-8") as out:
        sys.stdout = out
        sys.stderr = out
        print(datetime.now(timezone.utc).isoformat(), "Starting test-only push backend", flush=True)
        try:
            prepare_environment(PRIVATE)
            from waitress import serve
            from .push_service import create_app
            serve(create_app(), host="127.0.0.1", port=8787, threads=4)
        except Exception as exc:
            print(datetime.now(timezone.utc).isoformat(),
                  "Background service failed:", type(exc).__name__, flush=True)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
