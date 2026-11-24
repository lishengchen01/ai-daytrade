"""Fail-closed Taiwan equities intraday 5-minute signal engine, no orders."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import math

TW = ZoneInfo("Asia/Taipei")


def numeric(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def microseconds_to_time(raw):
    # Fugle documents UNIX timestamps in microseconds.
    if not numeric(raw) or raw < 10**14:
        raise ValueError("invalid market timestamp")
    return datetime.fromtimestamp(raw / 1_000_000, tz=timezone.utc).astimezone(TW)


def candle_time(raw):
    if not isinstance(raw, str):
        raise ValueError("missing candle time")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("naive time not accepted")
    return parsed.astimezone(TW)


def result(symbol, direction="WAIT", reason="資料不足", checks=None, sample=False):
    return {
        "symbol": symbol, "direction": direction, "reason": reason,
        "checks": checks or {}, "sample": sample,
        "trade_action_enabled": False, "place_order": False
    }


def breakout_retest(bars, direction, first_high, first_low):
    """Require a completed post-opening breakout bar followed by a retest bar."""
    boundary = first_high if direction == 1 else first_low
    broken = False
    for bar in bars:
        close = bar["close"]
        if not broken:
            if (direction == 1 and close > boundary) or (direction == -1 and close < boundary):
                broken = True
        else:
            low, high = bar["low"], bar["high"]
            near = (low <= boundary * 1.001 if direction == 1
                    else high >= boundary * 0.999)
            held = (close >= boundary if direction == 1 else close <= boundary)
            if near and held:
                return True
    return False


def evaluate(symbol, quote, candles, prior_volume, context, now=None):
    """Only quote/candles from authorized private server; context independently verified.
    A direction is emitted ONLY when ALL safeguards pass. Sample is always WAIT.
    """
    now = (now or datetime.now(TW)).astimezone(TW)
    today = now.date().isoformat()
    status = {}
    if not isinstance(quote, dict) or not isinstance(candles, dict):
        return result(symbol, reason="行情格式錯誤")
    if context.get("sample") or quote.get("sample") or candles.get("sample"):
        return result(symbol, reason="合成資料禁止觸發真實訊號", sample=True)
    if now.weekday() >= 5 or not time(9, 5) <= now.time() <= time(13, 20):
        return result(symbol, reason="非台股正常進場時段")
    if context.get("trading_date") != today or context.get("is_trade_day") is not True:
        return result(symbol, reason="交易日尚未由獨立來源確認")
    if quote.get("symbol") != symbol or candles.get("symbol") != symbol or quote.get("date") != today or candles.get("date") != today:
        return result(symbol, reason="行情股票或日期不一致")
    if quote.get("isTrial") is True or quote.get("tradingHalt", {}).get("isHalted") is True:
        return result(symbol, reason="試撮或暫停交易")
    try:
        last = microseconds_to_time(quote.get("lastTrade", {}).get("time"))
        if last > now or now - last > timedelta(seconds=90) or last.date() != now.date():
            return result(symbol, reason="最後成交時間過期／未來")
    except (ValueError, OverflowError, OSError):
        return result(symbol, reason="缺少有效最後成交時間")
    prices = [quote.get("previousClose"), quote.get("closePrice"), quote.get("avgPrice")]
    if not all(numeric(v) and v > 0 for v in prices):
        return result(symbol, reason="缺少昨收、最新成交價或當日成交均價")
    if not numeric(prior_volume) or prior_volume <= 0:
        return result(symbol, reason="前交易日成交量不足")
    raw = candles.get("data")
    if not isinstance(raw, list):
        return result(symbol, reason="缺少分鐘K線")
    by_minute = {}
    try:
        for b in raw:
            t = candle_time(b.get("date"))
            if t.date().isoformat() != today or t > now:
                continue
            if not all(numeric(b.get(k)) and b.get(k) > 0 for k in ("open", "high", "low", "close")):
                continue
            if not numeric(b.get("volume")) or b["volume"] < 0:
                continue
            if b["high"] < max(b["open"], b["close"]) or b["low"] > min(b["open"], b["close"]):
                continue
            minute = t.strftime("%H:%M")
            if minute in by_minute:  # duplicate data is unsafe
                return result(symbol, reason="分鐘K線時間重複")
            by_minute[minute] = b
    except (ValueError, TypeError):
        return result(symbol, reason="分鐘K線時間或欄位錯誤")
    first_minutes = ["09:0" + str(i) for i in range(5)]
    if any(m not in by_minute for m in first_minutes):
        return result(symbol, reason="首根五分鐘K尚未完整")
    first = [by_minute[m] for m in first_minutes]
    o, h, l, c = first[0]["open"], max(x["high"] for x in first), min(x["low"] for x in first), first[-1]["close"]
    volume = sum(x["volume"] for x in first)
    if h <= l or volume <= 0:
        return result(symbol, reason="首根五分K振幅／成交量無效")
    gap = (o / quote["previousClose"] - 1) * 100
    d = 1 if gap > 0 else -1 if gap < 0 else 0
    wick = (h - c if d == 1 else c - l) / (h - l)
    ratio = volume / prior_volume
    status["gap2to4"] = (2 <= abs(gap) <= 4)
    status["first5m_direction"] = d != 0 and d * (c - o) > 0
    status["close_end_wick20pct"] = wick <= 0.20
    status["first5m_volume10pct"] = ratio >= .10
    status["vwap"] = d != 0 and d * (quote["closePrice"] - quote["avgPrice"]) > 0
    verify_time = context.get("verified_at")
    try:
        verified = candle_time(verify_time)
    except (ValueError, TypeError):
        verified = None
    provenance = context.get("source") and context.get("eligibility_source")
    context_fresh = bool(provenance and verified and verified.date() == now.date()
                         and verified <= now and now - verified <= timedelta(seconds=90))
    status["market_and_sector"] = bool(context_fresh and d != 0 and
         context.get("market_direction") == d and context.get("sector_directions", {}).get(symbol) == d)
    after = [by_minute[k] for k in sorted(by_minute) if "09:05" <= k < now.strftime("%H:%M")]
    status["breakout_retest"] = d != 0 and breakout_retest(after, d, h, l)
    elig = context.get("eligibility", {}).get(symbol, {})
    status["daytrade_qualification"] = bool(context_fresh and
        elig.get("date") == today and elig.get("buy_then_sell") is True and
        (d == 1 or elig.get("sell_then_buy") is True))
    # Even a full technical match cannot override false/unknown licensing.
    status["private_license_acknowledged"] = context.get("licensed_private_use") is True
    if all(status.values()):
        return result(symbol, "LONG_CONDITIONS" if d == 1 else "SHORT_CONDITIONS",
                      "條件全數通過；僅供私人決策，不保證可成交", status)
    return result(symbol, reason="有未確認／未通過條件，不進場", checks=status)
