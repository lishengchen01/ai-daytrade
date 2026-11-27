"""Fugle REAL stock data -> qualified private research signals. Never a broker order.
All sources fail CLOSED. Market and industry checks are inferred from actual Fugle
index/peer data, not from simulation/checkboxes.
"""
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
import json
import os
import urllib.request

from .fugle import FugleClient
from .strategy import evaluate, microseconds_to_time

TW = ZoneInfo("Asia/Taipei")
DAILY_URL = "https://lishengchen01.github.io/ai-daytrade/quotes.json"
REQUIRED = ("date", "symbol")


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < float("inf")


def _valid_quote(q, symbol, now, expected_type="EQUITY"):
    if not isinstance(q, dict) or q.get("date") != now.date().isoformat() or q.get("symbol") != symbol:
        return False
    if q.get("type") != expected_type or q.get("isTrial") is True:
        return False
    if q.get("tradingHalt") and q["tradingHalt"].get("isHalted"):
        return False
    t = (q.get("lastTrade") or {}).get("time") if expected_type == "EQUITY" else (
        q.get("closeTime") or q.get("lastUpdated") or (q.get("total") or {}).get("time"))
    if not _finite(t):
        return False
    try:
        last = microseconds_to_time(t)
    except (ValueError, OverflowError, OSError):
        return False
    return now >= last and now - last <= timedelta(seconds=90) and all(
        _finite(q.get(k)) for k in ("previousClose", "closePrice"))


def _direction(q):
    a, b = q["closePrice"], q["previousClose"]
    return 1 if a > b else -1 if a < b else 0


def _get_daily(url=DAILY_URL):
    # No Fugle API key in this request; public daily TWSE/TPEx candidate source.
    with urllib.request.urlopen(urllib.request.Request(
        url, headers={"User-Agent": "PrivateDaytrade-v1071"}), timeout=12) as response:
        j = json.load(response)
    if not isinstance(j, dict) or not isinstance(j.get("rows"), list) or not j.get("fetched"):
        raise ValueError("缺少已更新的官方盤後初篩資料；停止掃描")
    return j


def _candidate_rows(daily, today):
    rows = [r for r in daily["rows"] if isinstance(r, dict) and
            isinstance(r.get("date"), str) and r["date"] < today and
            isinstance(r.get("symbol"), str) and r["symbol"].isdigit() and
            len(r["symbol"]) in (4, 5, 6) and _finite(r.get("volume"))]
    if not rows:
        return [], []
    latest = max(r["date"] for r in rows)
    # Avoid selecting from stale prior sessions or fake snapshot dates.
    if (datetime.fromisoformat(today).date() -
        datetime.fromisoformat(latest).date()).days > 4:
        return [], []
    prev = [r for r in rows if r["date"] == latest]
    eligible = [r for r in prev if isinstance(r.get("change"), (float, int)) and
                not isinstance(r["change"], bool) and 2 <= abs(r["change"]) <= 4 and
                r["volume"] >= 500]
    return sorted(eligible, key=lambda r: -r["volume"])[:5], prev


def _index_symbol(client, config, today):
    """Prefer Fugle's officially documented TAIEX ticker IX0001.

    The previous name-search required exactly one name containing both
    「加權」and「指數」and failed for different/duplicate index names.
    Never guess from a fuzzy search. Verify date, symbol, type and exchange
    on every real call; any mismatch fails closed.
    """
    index = config.get("market_index_symbol") or "IX0001"
    if not isinstance(index, str) or index != "IX0001":
        raise ValueError("僅支援已核實的加權指數 IX0001")
    ticker = client.ticker(index)
    if (not isinstance(ticker, dict) or
            ticker.get("symbol") != index or
            ticker.get("type") != "INDEX" or
            ticker.get("exchange") != "TWSE" or
            ticker.get("date") != today):
        raise ValueError("加權指數 IX0001 資料驗證失敗（代碼、日期、類型或交易所）")
    return index


def _sector_direction(client, ticker, prev, now):
    industry = ticker.get("industry")
    exchange = ticker.get("exchange")
    if not isinstance(industry, str) or industry == "00" or exchange not in ("TWSE", "TPEx"):
        return 0
    group = client.tickers(industry=industry, exchange=exchange)
    if group.get("date") != now.date().isoformat() or not isinstance(group.get("data"), list):
        return 0
    members = set(r.get("symbol") for r in group["data"] if isinstance(r, dict))
    peers = [r for r in prev if r["symbol"] != ticker["symbol"] and r["symbol"] in members]
    peers.sort(key=lambda x: -x["volume"])
    peers = peers[:2]
    if len(peers) < 2:
        return 0
    directions = []
    for r in peers:
        q = client.quote(r["symbol"])
        if not _valid_quote(q, r["symbol"], now):
            return 0
        directions.append(_direction(q))
    return directions[0] if directions[0] and directions[0] == directions[1] else 0


def scan_real(config, client=None, now=None, daily=None):
    """Return only research judgments, no licensed quote redistribution."""
    now = (now or datetime.now(TW)).astimezone(TW)
    if now.weekday() > 4 or not time(9, 7) <= now.time() <= time(13, 20):
        return [], "盤外或首根K與突破回踩尚未完成"
    if os.getenv("FUGLE_PRIVATE_USE_CONFIRMED") != "YES":
        return [], "尚未確認 Fugle 私人使用權限"
    if not config.get("broker_permission_verified"):
        return [], "尚未核實券商個人現股當沖雙向交易資格"
    client = client or FugleClient()
    daily = daily if daily is not None else _get_daily()
    picks, prev = _candidate_rows(daily, now.date().isoformat())
    if not picks:
        return [], "前交易日公開盤後初篩資料缺失或逾期"
    today = now.date().isoformat()
    index = _index_symbol(client, config, today)
    mquote = client.quote(index)
    if not _valid_quote(mquote, index, now, expected_type="INDEX") or not _direction(mquote):
        return [], "無法驗證當日即時大盤方向"
    results = []
    for p in picks:
        symbol = p["symbol"]
        try:
            ticker = client.ticker(symbol)
            if (ticker.get("symbol") != symbol or ticker.get("type") != "EQUITY" or
                ticker.get("date") != today or ticker.get("securityStatus") != "NORMAL" or
                ticker.get("isDisposition") is True or ticker.get("matchingInterval") not in (0, None)):
                continue
            # canDayTrade=True denotes bidirectional stock eligibility; broker permission is a separate gate.
            buy_ok = ticker.get("canDayTrade") is True or ticker.get("canBuyDayTrade") is True
            short_ok = ticker.get("canDayTrade") is True and config.get("broker_sell_first_verified") is True
            peer_dir = _sector_direction(client, ticker, prev, now)
            q = client.quote(symbol)
            bars = client.minute_candles(symbol)
            if not _valid_quote(q, symbol, now) or peer_dir == 0:
                continue
            if bars.get("timeframe") not in ("1", 1):
                continue
            context = {
                "trading_date": today, "is_trade_day": True,
                "verified_at": now.isoformat(),
                "source": "Fugle intraday INDEX and industry peer quotes",
                "eligibility_source": "Fugle intraday ticker + personally verified brokerage eligibility",
                "market_direction": _direction(mquote),
                "sector_directions": {symbol: peer_dir},
                "eligibility": {symbol: {"date": today, "buy_then_sell": buy_ok, "sell_then_buy": short_ok}},
                "licensed_private_use": True, "sample": False,
            }
            outcome = evaluate(symbol, q, bars, p["volume"], context, now)
            if outcome["direction"] in ("LONG_CONDITIONS", "SHORT_CONDITIONS"):
                # Deliberately do not export raw market data, prices or candles.
                results.append({"symbol": symbol, "direction": outcome["direction"],
                                "at": now.isoformat(), "reason": "經核實五分鐘K、量能、VWAP、突破回踩及大盤族群",
                                "checks": outcome["checks"], "sample": False})
        except (KeyError, ValueError, TypeError, RuntimeError):
            continue   # no incomplete or unverified signal
    return results, "真實行情條件掃描完成；候選不代表可成交"
