"""V1.08.2 PRIVATE local dispatch; never exposed as HTTP endpoint.

Only an authorized local Windows shadow scan may pass its in-memory result
through this module. No Fugle key, raw prices, candles, or push credentials
are exposed to GitHub Pages or the browser. Live mode is DEFAULT OFF.

A durable SQLite reservation is written BEFORE attempting Apple Web Push:
this favors at-most-once alert attempts over duplicates after a crash. HTTP
push provider acceptance is not proof that an iPhone showed a notification.
"""
from contextlib import contextmanager, closing
from datetime import datetime, time
import json
import os
from pathlib import Path
import re
import sqlite3

from v1071.strategy import TW
from .signal_bridge import prepare_private_push_payloads, _verified_time, MAX_AGE

PRIVATE_ROOT = Path.home() / ".ai-daytrade-private"
OPT_IN = PRIVATE_ROOT / "v1082-private-notify.json"
LOCAL_DB = PRIVATE_ROOT / "push.sqlite3"
VAPID_KEY = PRIVATE_ROOT / "vapid-private.pem"
MODE_DISABLED = "SHADOW_DISABLED"
MODE_LIVE = "LOCAL_PRIVATE_ENABLED"


def _config(path=OPT_IN):
    """Require EXPLICIT local opt-in; malformed or absent files fail closed."""
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(cfg, dict):
        return None
    if (cfg.get("mode") != "private-owner-alerts" or
        cfg.get("enabled") is not True or
        cfg.get("personal_fugle_use_confirmed") is not True or
        cfg.get("broker_permission_verified") is not True or
        cfg.get("broker_sell_first_verified") is not True or
        cfg.get("iphone_connection_test_confirmed") is not True):
        return None
    subject = cfg.get("vapid_subject")
    if not (isinstance(subject, str) and
            re.fullmatch(r"mailto:[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", subject)):
        return None
    return cfg


@contextmanager
def _temporary_private_delivery_environment(cfg, *, root=PRIVATE_ROOT):
    """Set backend credentials for THIS worker only; do not modify push task."""
    names = ("WEBPUSH_DERIVED_SIGNAL_ALLOWED", "VAPID_PRIVATE_KEY_PATH",
             "VAPID_SUBJECT", "DAYTRADE_DB_PATH")
    original = {name: os.environ.get(name) for name in names}
    try:
        os.environ.update({
            "WEBPUSH_DERIVED_SIGNAL_ALLOWED": "YES",
            "VAPID_PRIVATE_KEY_PATH": str(root / "vapid-private.pem"),
            "VAPID_SUBJECT": cfg["vapid_subject"],
            "DAYTRADE_DB_PATH": str(root / "push.sqlite3"),
        })
        yield
    finally:
        for name, previous in original.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


def _reserve_attempt(payload, *, db_path=LOCAL_DB, now=None):
    """Atomically reserve one symbol/day/direction before network send.

    A failure or crash leaves a pending reservation and will NOT auto-retry
    this signal. This is an intentional fail-closed trade-off.
    """
    signal_id = payload["signalId"]
    stamp = (now or datetime.now(TW)).isoformat()
    with closing(sqlite3.connect(str(db_path), timeout=10)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS local_dispatch_attempts (
            signal_id TEXT PRIMARY KEY,
            reserved_at TEXT NOT NULL,
            provider_accepted INTEGER NOT NULL DEFAULT 0
        )""")
        already_sent = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sent'"
        ).fetchone()
        if already_sent and db.execute(
            "SELECT 1 FROM sent WHERE signal_id=?", (signal_id,)
        ).fetchone():
            return False
        cursor = db.execute(
            "INSERT OR IGNORE INTO local_dispatch_attempts(signal_id,reserved_at)"
            " VALUES(?,?)", (signal_id, stamp)
        )
        return cursor.rowcount == 1


def _record_provider_acceptance(signal_id, accepted, *, db_path=LOCAL_DB):
    with closing(sqlite3.connect(str(db_path), timeout=10)) as db, db:
        db.execute(
            "UPDATE local_dispatch_attempts SET provider_accepted=? "
            "WHERE signal_id=?",
            (int(accepted), signal_id),
        )


def dispatch_from_private_audit(
    audit_result, *, now=None, config_path=OPT_IN, private_root=PRIVATE_ROOT,
    delivery=None, clock_source=None
):
    """Return ONLY aggregate metadata; never store individual quote payloads.

    A caller may inject a fake delivery function for offline tests. Production
    calls backend deliver() directly within this same local Python process,
    so no new Tailscale-accessible webhook or bearer-token endpoint exists.
    """
    out = {
        "push_mode": MODE_DISABLED,
        "push_ready_count": 0,
        "notifications_sent": 0,
        "attempted_alerts": 0,
    }
    if not isinstance(audit_result, dict) or audit_result.get("status") != "completed":
        return out
    now = (now or datetime.now(TW)).astimezone(TW)
    prepared = prepare_private_push_payloads(
        audit_result.get("verified_signals", []), now=now
    )
    out["push_ready_count"] = len(prepared)
    cfg = _config(config_path)
    if cfg is None:
        return out
    # Enforce real local private Web Push installation, not a test database.
    if not (private_root / "vapid-private.pem").is_file():
        return out
    if not (private_root / "push.sqlite3").is_file():
        return out
    # Do not reserve signals when there is no genuinely subscribed device.
    try:
        with closing(sqlite3.connect(str(private_root / "push.sqlite3"), timeout=3)) as db, db:
            registered = db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
            if registered < 1:
                return out
    except sqlite3.Error:
        return out
    out["push_mode"] = MODE_LIVE
    if not prepared:
        return out
    if delivery is None:
        # Imported ONLY once local opt-in and prerequisites are satisfied.
        from v1071.push_service import deliver
        delivery = deliver
    with _temporary_private_delivery_environment(cfg, root=private_root):
        for payload in prepared:
            # Verify again using a fresh wall clock AFTER the full scan;
            # never refresh the underlying issuedAt to bypass 90s expiry.
            check_at = (clock_source or (lambda: datetime.now(TW)))().astimezone(TW)
            issued = _verified_time(payload.get("issuedAt"))
            if (issued is None or issued.date() != check_at.date()
                or check_at.weekday() >= 5
                or not time(9, 7) <= check_at.time() <= time(13, 20)
                or issued > check_at or check_at - issued > MAX_AGE):
                continue
            if not _reserve_attempt(
                payload, db_path=private_root / "push.sqlite3", now=check_at
            ):
                continue
            out["attempted_alerts"] += 1
            try:
                accepted = delivery(payload)
                accepted = accepted if type(accepted) is int and accepted >= 0 else 0
            except Exception:
                accepted = 0
            out["notifications_sent"] += accepted
            try:
                _record_provider_acceptance(
                    payload["signalId"], accepted,
                    db_path=private_root / "push.sqlite3"
                )
            except sqlite3.Error:
                # Reservation persists, preventing accidental duplicates.
                pass
    return out
