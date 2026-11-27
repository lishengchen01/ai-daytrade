"""Public, delayed official TWSE/TPEx daily quote collection (NO Fugle key).

Fail closed: a GitHub Actions green check must never publish empty, failed or
incoherent market dates as a "successful" public data update.
"""
import datetime
import json
import urllib.request

SOURCES = [
    ("上市", "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"),
    ("上櫃", "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"),
]
TW = datetime.timezone(datetime.timedelta(hours=8))
MAX_AGE_DAYS = 4


def num(value):
    return float(str(value).replace(",", ""))


def parse_date(value):
    s = str(value).replace("/", "").replace("-", "")
    y = int(s[:-4])
    return datetime.date(
        y + 1911 if y < 1911 else y,
        int(s[-4:-2]), int(s[-2:]),
    ).isoformat()


def pick(row, *keys):
    for key in keys:
        if key in row:
            return row[key]
    raise KeyError(keys)


def parse(row, market):
    symbol = str(pick(row, "Code", "SecuritiesCompanyCode"))
    name = pick(row, "Name", "CompanyName", "SecuritiesCompanyName")
    close = num(pick(row, "ClosingPrice", "Close"))
    change = num(pick(row, "Change", "ChangePrice"))
    volume = num(pick(row, "TradeVolume", "TradingShares", "TradingVolume"))
    day = parse_date(pick(row, "Date", "TradeDate"))
    if len(symbol) != 4 or not symbol.isdigit() or close <= 0 or close - change <= 0 or volume < 0:
        return None
    return dict(symbol=symbol, name=name, market=market, date=day,
                close=close, change=change / (close - change) * 100,
                volume=volume / 1000)


def validate_release(rows, sources, *, today=None):
    """Raises before any quotes.json or GitHub Pages artifact is published."""
    today = today or datetime.datetime.now(TW).date()
    if len(sources) != len(SOURCES) or any(
        source.get("ok") is not True or source.get("count", 0) < 1
        for source in sources
    ):
        raise ValueError("上市或上櫃公開報價擷取失敗，不發布新的 quotes.json")
    if not rows:
        raise ValueError("公開報價無資料，不發布")
    dates_by_market = {}
    for market, _ in SOURCES:
        dates = {r["date"] for r in rows if r["market"] == market}
        if len(dates) != 1:
            raise ValueError("公開來源同市場交易日不一致，不發布")
        dates_by_market[market] = dates.pop()
    if len(set(dates_by_market.values())) != 1:
        raise ValueError("上市與上櫃交易日不一致，不發布")
    date = datetime.date.fromisoformat(next(iter(dates_by_market.values())))
    age = (today - date).days
    if not 0 <= age <= MAX_AGE_DAYS:
        raise ValueError("公開盤後資料日期超前或過舊，不發布")
    return date.isoformat()


def main():
    rows, status = [], []
    for market, url in SOURCES:
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Daytrade research dashboard"})
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response)
            if not isinstance(data, list):
                raise ValueError("資料來源格式不是列表")
            valid = []
            for row in data:
                try:
                    item = parse(row, market)
                    if item:
                        valid.append(item)
                except (ValueError, KeyError, TypeError):
                    pass
            if not valid:
                raise ValueError("資料來源沒有任何可解析行情")
            rows += valid
            status.append(dict(market=market, ok=True,
                               count=len(valid), url=url))
        except Exception:
            # Errors do not include private information. No market payloads
            # are persisted, and a failed source must fail the whole run.
            status.append(dict(market=market, ok=False, count=0, url=url))

    latest = validate_release(rows, status)
    payload = {
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sources": status,
        "rows": rows,
    }
    with open("quotes.json", "w", encoding="utf-8") as out:
        json.dump(payload, out, ensure_ascii=False)
    print("VALIDATED PUBLIC QUOTES", latest,
          "rows", len(rows),
          "sources", [(s["market"], s["count"]) for s in status])


if __name__ == "__main__":
    main()
