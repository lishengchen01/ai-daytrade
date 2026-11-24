"""Private Web Push server. Use ONLY behind trusted HTTPS reverse proxy.
No Fugle API key or quotes are served to browser. No auto-order endpoints.
"""
from datetime import datetime, timezone
from contextlib import closing
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, jsonify, request, make_response

DEFAULT_DB = str(Path.home() / ".ai-daytrade-private" / "push.sqlite3")
ORIGIN = "https://lishengchen01.github.io"


def connect_db():
    path = Path(os.environ.get("DAYTRADE_DB_PATH", DEFAULT_DB)).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS subscriptions(
        endpoint TEXT PRIMARY KEY, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
        created_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS sent(
        signal_id TEXT PRIMARY KEY, sent_at TEXT NOT NULL)""")
    db.commit()
    return db


def _is_apple_endpoint(url):
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.username is None and u.password is None
                and u.port in (None, 443) and bool(u.hostname) and
                (u.hostname == "push.apple.com" or u.hostname.endswith(".push.apple.com"))
                and u.path.startswith("/") and len(url) <= 4096)
    except (ValueError, AttributeError, TypeError):
        return False


def _valid_sub(obj):
    if not isinstance(obj, dict):
        return None
    endpoint = obj.get("endpoint")
    keys = obj.get("keys")
    if not isinstance(endpoint, str) or not _is_apple_endpoint(endpoint):
        return None
    if not isinstance(keys, dict) or any(
            not isinstance(keys.get(k), str) or not 20 <= len(keys[k]) <= 200 for k in ("p256dh", "auth")):
        return None
    return endpoint, keys["p256dh"], keys["auth"]


def _auth():
    expected = os.environ.get("PUSH_PAIRING_TOKEN", "")
    sent = request.headers.get("Authorization", "")
    return len(expected) >= 32 and hmac.compare_digest(sent, "Bearer " + expected)


def _allowed_origin():
    return request.headers.get("Origin") == ORIGIN


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 8192

    @app.after_request
    def cors(resp):
        if _allowed_origin() and request.path.startswith("/api/v1/"):
            resp.headers["Access-Control-Allow-Origin"] = ORIGIN
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.before_request
    def guard():
        if not request.path.startswith("/api/v1/"):
            return jsonify(error="not_found"), 404
        if request.method == "OPTIONS":
            return ("", 204) if _allowed_origin() else (jsonify(error="origin"), 403)
        if not _allowed_origin():
            return jsonify(error="origin"), 403

    def require_auth(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not _auth():
                return jsonify(error="not_authorized"), 401
            return fn(*args, **kwargs)
        return wrapped

    @app.get("/api/v1/health")
    def health():
        return jsonify(status="online", mode="private-research", place_order=False)

    @app.get("/api/v1/vapid-public-key")
    def vapid_public_key():
        public = os.environ.get("VAPID_PUBLIC_KEY", "")
        if not public or len(public) < 75:
            return jsonify(error="public_key_not_configured"), 503
        return jsonify(publicKey=public)

    @app.post("/api/v1/subscribe")
    @require_auth
    def subscribe():
        sub = _valid_sub(request.get_json(silent=True))
        if not sub:
            return jsonify(error="invalid_apple_subscription"), 400
        with closing(connect_db()) as db, db:
            count = db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
            exists = db.execute("SELECT 1 FROM subscriptions WHERE endpoint=?", (sub[0],)).fetchone()
            if count >= 5 and not exists:
                return jsonify(error="device_limit"), 409
            db.execute("INSERT OR REPLACE INTO subscriptions VALUES (?,?,?,?)",
                       (*sub, datetime.now(timezone.utc).isoformat()))
        return jsonify(registered=True, live_signals_enabled=(
            os.environ.get("WEBPUSH_DERIVED_SIGNAL_ALLOWED") == "YES"))

    @app.post("/api/v1/unsubscribe")
    @require_auth
    def unsubscribe():
        payload = request.get_json(silent=True)
        sub = _valid_sub(payload)
        if not sub:
            return jsonify(error="invalid_apple_subscription"), 400
        with closing(connect_db()) as db, db:
            db.execute("DELETE FROM subscriptions WHERE endpoint=?", (sub[0],))
        return jsonify(registered=False)

    @app.post("/api/v1/test")
    @require_auth
    def test_remote():
        # This is a genuine remote push, never described as a trading signal.
        count = deliver({
            "schema": "daytrade-push-v1", "type": "connection-test", "test": True,
            "issuedAt": datetime.now(timezone.utc).isoformat()
        }, allow_test=True)
        return jsonify(sent=count)

    return app


def deliver(payload, *, allow_test=False):
    """Only send app-owned minimal signal metadata through Apple Web Push."""
    test = allow_test and payload.get("type") == "connection-test" and payload.get("test") is True
    if not test:
        if (os.environ.get("WEBPUSH_DERIVED_SIGNAL_ALLOWED") != "YES" or
            payload.get("schema") != "daytrade-push-v1" or
            payload.get("type") != "strategy-signal" or
            payload.get("verified") is not True or payload.get("sample") is not False or
            payload.get("direction") not in ("LONG_CONDITIONS", "SHORT_CONDITIONS") or
            not (isinstance(payload.get("symbol"), str) and payload["symbol"].isdigit()) or
            not isinstance(payload.get("signalId"), str) or
            not isinstance(payload.get("issuedAt"), str)):
            return 0
        try:
            t = datetime.fromisoformat(payload["issuedAt"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - t.astimezone(timezone.utc)).total_seconds()
            if age < 0 or age > 90:
                return 0
        except (ValueError, TypeError, OverflowError):
            return 0
    if not os.environ.get("VAPID_PRIVATE_KEY_PATH") or not os.environ.get("VAPID_SUBJECT"):
        return 0
    from pywebpush import webpush, WebPushException

    key_path = Path(os.environ["VAPID_PRIVATE_KEY_PATH"]).expanduser()
    if not key_path.is_file():
        return 0
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with closing(connect_db()) as db, db:
        if not test:
            previously = db.execute("SELECT 1 FROM sent WHERE signal_id=?",
                                    (payload["signalId"],)).fetchone()
            if previously:
                return 0
        subs = db.execute("SELECT endpoint,p256dh,auth FROM subscriptions").fetchall()
        delivered = 0
        for endpoint, p256dh, auth in subs:
            try:
                webpush(
                    subscription_info={"endpoint": endpoint,
                                       "keys": {"p256dh": p256dh, "auth": auth}},
                    data=serialized,
                    vapid_private_key=str(key_path),
                    vapid_claims={"sub": os.environ["VAPID_SUBJECT"]},
                    ttl=90,
                    timeout=10
                )
                delivered += 1
            except WebPushException as exc:
                if getattr(getattr(exc, "response", None), "status_code", None) in (404, 410):
                    db.execute("DELETE FROM subscriptions WHERE endpoint=?", (endpoint,))
            except Exception:
                pass
        if delivered and not test:
            db.execute("INSERT OR IGNORE INTO sent VALUES (?,?)",
                       (payload["signalId"], datetime.now(timezone.utc).isoformat()))
        return delivered
