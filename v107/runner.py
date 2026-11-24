"""Private-only personal trading research runner. No web serving, no orders."""
import argparse
from datetime import datetime
import json
import os
import time
import urllib.request
from zoneinfo import ZoneInfo

from fugle import FugleClient, MarketDataError
from strategy import evaluate

TW = ZoneInfo("Asia/Taipei")
PUBLIC_DAILY = "https://lishengchen01.github.io/ai-daytrade/quotes.json"


def get_daily(url):
    with urllib.request.urlopen(url, timeout=12) as resp:
        data = json.load(resp)
    if not isinstance(data.get("rows"), list):
        raise ValueError("無效盤後候選資料")
    return data


def watchlist(data, today, limit=5):
    dates = [r.get("date") for r in data["rows"] if
             isinstance(r.get("date"), str) and r["date"] < today]
    if not dates:
        return []
    latest = max(dates)
    rows = [r for r in data["rows"] if r.get("date") == latest
            and isinstance(r.get("symbol"), str)
            and isinstance(r.get("change"), (int, float))
            and isinstance(r.get("volume"), (int, float))
            and 2 <= abs(r["change"]) <= 4 and r["volume"] >= 500]
    rows.sort(key=lambda r: -r["volume"])
    return rows[:limit]


def scan(client, daily, context, now):
    picks = watchlist(daily, now.date().isoformat())
    output = []
    for p in picks:
        symbol = p["symbol"]
        try:
            q = client.quote(symbol)
            candles = client.minute_candles(symbol)
            analysis = evaluate(symbol, q, candles, p["volume"], context, now)
        except (MarketDataError, ValueError, KeyError, TypeError) as exc:
            analysis = {"symbol": symbol, "direction": "WAIT",
                        "reason": str(exc), "trade_action_enabled": False}
        output.append(analysis)
    return output


def main():
    parser = argparse.ArgumentParser(description="Private Fugle REST strategy research")
    parser.add_argument("--daily-source", default=PUBLIC_DAILY,
                        help="Official-derived public daily watchlist JSON source")
    parser.add_argument("--context", default="", help="Private independently verified market/eligibility context JSON")
    parser.add_argument("--loop", action="store_true", help="Poll at >=30s intervals when continuously hosted")
    args = parser.parse_args()
    if not os.getenv("FUGLE_API_KEY"):
        raise SystemExit("尚未設定 FUGLE_API_KEY。請向 Fugle 申請後透過私人環境變數設定；不可寫入 GitHub Pages。")
    client = FugleClient()
    while True:
        now = datetime.now(TW)
        context = {}
        if args.context:
            with open(args.context, encoding="utf-8") as fh:
                context = json.load(fh)
        try:
            daily = get_daily(args.daily_source)
            signals = scan(client, daily, context, now)
            # No raw licensed quote/candle contents ever written or published.
            print(json.dumps({"checked_at": now.isoformat(), "provider": "Fugle REST",
                              "results": signals, "private_only": True}, ensure_ascii=False), flush=True)
        except Exception:
            print(json.dumps({"checked_at": now.isoformat(),
                              "status": "WAIT", "reason": "行情來源／前日資料不可用",
                              "private_only": True}, ensure_ascii=False), flush=True)
        if not args.loop:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
