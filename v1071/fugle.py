"""Server-side Fugle market data client; NEVER use in public browser JS."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


class MarketDataError(RuntimeError):
    pass


class FugleClient:
    BASE = "https://api.fugle.tw/marketdata/v1.0/stock/"

    def __init__(self, key=None, transport=None):
        self.key = key or os.getenv("FUGLE_API_KEY")
        if not self.key:
            raise MarketDataError("FUGLE_API_KEY 未設定；不會執行真實行情請求")
        self.transport = transport or self._http

    def _http(self, path):
        req = urllib.request.Request(
            urllib.parse.urljoin(self.BASE, path),
            headers={"X-API-KEY": self.key, "Accept": "application/json",
                     "User-Agent": "PersonalDaytradeResearch/1.07"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise MarketDataError("Fugle API 達到速率限制（429）") from exc
            raise MarketDataError("Fugle API HTTP " + str(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise MarketDataError("Fugle 行情連線失敗") from exc

    @staticmethod
    def _symbol(symbol):
        if not re.fullmatch(r"(?:[0-9]{4,6}[A-Z]?|IX[0-9]{4,6})", symbol):
            raise MarketDataError("股票代碼不合法")
        return symbol

    def ticker(self, symbol):
        """Fugle trading eligibility/industry flags. Must also verify broker permissions."""
        return self.transport("intraday/ticker/" + self._symbol(symbol))

    def tickers(self, *, industry, exchange="TWSE"):
        if not re.fullmatch(r"[0-9]{2}", industry):
            raise MarketDataError("invalid industry")
        return self.transport("intraday/tickers?type=EQUITY&exchange="
                              + exchange + "&industry=" + industry + "&isNormal=true")

    def quote(self, symbol):
        return self.transport("intraday/quote/" + self._symbol(symbol))

    def minute_candles(self, symbol):
        return self.transport("intraday/candles/" + self._symbol(symbol)
                              + "?timeframe=1&sort=asc")
