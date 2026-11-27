"""V1.07.4: ONE-SHOT private real-market audit; never sends notifications or orders.

Usage: py -m v1071.audit_live
No key saved. This command reads today's REAL Fugle data only while TW market
is open. It intentionally does not import or call the push backend.
"""
from datetime import datetime, time
import getpass
import os
from zoneinfo import ZoneInfo

from .fugle import FugleClient, MarketDataError
from .scanner import scan_real

TW = ZoneInfo("Asia/Taipei")


def audit_once(client, now=None, daily=None):
    now = (now or datetime.now(TW)).astimezone(TW)
    if now.weekday() > 4 or not (time(9, 7) <= now.time() <= time(13, 20)):
        return {"status": "outside_market", "signals": [], "requests": 0}
    # These permissions must be explicitly attested in the CLI, separately
    # from the current day's symbol-specific trading eligibility.
    config = {
        "broker_permission_verified": True,
        "broker_sell_first_verified": True,
    }
    # In this CLI, personal-use acknowledgement is set ONLY for the one-shot
    # process; no environment variable, registry or file is persisted.
    prior = os.environ.get("FUGLE_PRIVATE_USE_CONFIRMED")
    os.environ["FUGLE_PRIVATE_USE_CONFIRMED"] = "YES"
    diagnostics = {}
    try:
        signals, reason = scan_real(
            config, client=client, now=now, daily=daily,
            diagnostics=diagnostics,
        )
    finally:
        if prior is None:
            os.environ.pop("FUGLE_PRIVATE_USE_CONFIRMED", None)
        else:
            os.environ["FUGLE_PRIVATE_USE_CONFIRMED"] = prior
    # The original CLI still prints minimal tuples. The in-memory
    # verified_signals are for V1.08.1's second, stricter push-readiness
    # gate; do not serialize them in history or publish them to GitHub.
    accepted = [s for s in signals
                if s.get("sample") is False and s.get("checks")
                and all(s["checks"].values())]
    return {
        "status": "completed",
        "signals": [(s["symbol"], s["direction"]) for s in accepted],
        "verified_signals": accepted,
        "reason": reason,
        "requests": getattr(client, "requests_made", None),
        "diagnostics": diagnostics,
    }


def main():
    now = datetime.now(TW)
    print("V1.07.4 Fugle 私人真實盤中驗證（只在本機輸出，不發送推播、無下單）")
    if now.weekday() > 4 or not (time(9, 7) <= now.time() <= time(13, 20)):
        print("目前非驗證時段；請於台股交易日 09:07–13:20 執行。")
        return 0
    if input("Fugle 已書面允許你描述的『僅本人使用＋私人 iPhone 推播』用途？輸入 YES 確認：").strip() != "YES":
        print("未確認個人用途；停止")
        return 1
    if input("本人的證券戶先買後賣及先賣後買現股當沖均已開通？輸入 YES 確認：").strip() != "YES":
        print("券商帳戶資格未確認；停止")
        return 1
    key = getpass.getpass("請在 Windows 本機輸入 Fugle API Key（不會回顯、不會保存）：").strip()
    if len(key) < 12:
        print("未提供有效格式的 API Key；停止")
        return 1
    try:
        client = FugleClient(key=key)
        result = audit_once(client, now=datetime.now(TW))
    except (MarketDataError, ValueError, RuntimeError, OSError) as exc:
        print("本次驗證未完成，沒有發出任何推播。錯誤類別：", type(exc).__name__)
        return 1
    print("掃描狀態：", result["status"])
    print("本次 REST 請求數：", result.get("requests"))
    print("通過全部條件的候選數：", len(result.get("signals", [])))
    for symbol, direction in result.get("signals", []):
        print(symbol, "偏多" if direction == "LONG_CONDITIONS" else "偏空",
              "（僅本機研究、不是下單指令）")
    print("判斷：", result.get("reason", ""))
    print("候選過濾原因統計（只有數量，不顯示原始行情）：")
    counts = result.get("diagnostics", {})
    if counts:
        for gate, n in counts.items():
            print(" -", gate, ":", n)
    else:
        print(" - 無可顯示統計；請確認是否停在整體前置條件")
    print("注意：0 候選也可能是資料不齊或 API 拒絕後的安全跳過；不能解讀為市場完全沒有機會。")
    print("本次絕不傳送手機訊號。正式自動推播仍需獨立驗證與部署。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
