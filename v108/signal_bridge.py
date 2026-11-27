"""V1.08.1 verified candidate -> private Web Push *preparation* gate.

This module prepares only app-owned minimal metadata. It NEVER calls a
sender, the push backend, or a broker API. A future separately approved
deployment may use this gate before dispatch, with independent live checks.
"""
from datetime import datetime, time, timedelta
import re

from v1071.strategy import TW

REQUIRED_CHECKS = frozenset((
    "gap2to4", "first5m_direction", "close_end_wick20pct",
    "first5m_volume10pct", "vwap", "market_and_sector",
    "breakout_retest", "daytrade_qualification",
    "private_license_acknowledged",
))
ALLOWED_DIRECTIONS = frozenset(("LONG_CONDITIONS", "SHORT_CONDITIONS"))
MAX_AGE = timedelta(seconds=90)


def _verified_time(value):
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            return None
        return instant.astimezone(TW)
    except (ValueError, TypeError, OverflowError):
        return None


def prepare_private_push_payloads(signals, *, now=None):
    """Validate a fully verified scan, fail closed, keep data in memory only.

    No raw quotes, candles, prices, API keys or subscription details are
    copied. The issuedAt timestamp is the actual verified scan timestamp,
    never artificially refreshed to the time of sending.
    """
    now = (now or datetime.now(TW)).astimezone(TW)
    if now.weekday() >= 5 or not time(9, 7) <= now.time() <= time(13, 20):
        return []
    if not isinstance(signals, (list, tuple)):
        return []
    accepted, seen = [], set()
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        symbol = signal.get("symbol")
        direction = signal.get("direction")
        checks = signal.get("checks")
        t = _verified_time(signal.get("at"))
        if (signal.get("sample") is not False or
            direction not in ALLOWED_DIRECTIONS or
            not isinstance(symbol, str) or
            not re.fullmatch(r"[0-9]{4,6}", symbol) or
            not isinstance(checks, dict) or
            any(checks.get(name) is not True for name in REQUIRED_CHECKS) or
            any(value is not True for value in checks.values()) or
            t is None or t.date() != now.date() or
            t > now or now - t > MAX_AGE or
            not time(9, 7) <= t.time() <= time(13, 20)):
            continue
        signal_id = t.date().isoformat() + ":" + symbol + ":" + direction
        if signal_id in seen:
            continue
        seen.add(signal_id)
        accepted.append({
            "schema": "daytrade-push-v1",
            "type": "strategy-signal", "verified": True, "sample": False,
            "symbol": symbol, "direction": direction,
            "signalId": signal_id, "issuedAt": t.isoformat(),
        })
    return accepted


def shadow_push_summary(signals, *, now=None):
    """Safe diagnostic. No private signal metadata is written to the disk."""
    candidates = prepare_private_push_payloads(signals, now=now)
    return {
        "push_mode": "SHADOW_DISABLED",
        "push_ready_count": len(candidates),
        "notifications_sent": 0,
    }
