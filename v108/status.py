"""Read ONLY local safe shadow status; never request market data or secrets."""
from datetime import datetime, timezone
import json

from .shadow_loop import STATUS, TW, VERSION


def main():
    if not STATUS.is_file():
        print("尚未找到 V1.08 影子掃描狀態；請確認工作排程器是否已啟動。")
        return 1
    try:
        obj = json.loads(STATUS.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(obj["checked_at"])
        age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
    except (ValueError, KeyError, TypeError, OSError):
        print("狀態檔案無法驗證，不代表背景掃描正常。")
        return 1
    print("版本：", obj.get("version"))
    print("上次狀態：", obj.get("status"))
    print("最近檢查時間：", timestamp.astimezone(TW).isoformat())
    print("本次符合策略條件數：", obj.get("qualified_count"))
    print("本次 API 請求數：", obj.get("requests"))
    print("符合手機推播安全格式數：", obj.get("push_ready_count", 0))
    print("正式通知實際發送數：", obj.get("notifications_sent", 0))
    print("手機正式訊號模式：", obj.get("push_mode", "SHADOW_DISABLED"))
    if obj.get("status") == "outside_session":
        print("目前為非掃描時段，無需收到正式多空通知。")
    elif age > 660 or age < -60:
        print("警告：狀態已超過 11 分鐘或系統時間不一致，請檢查工作排程器。")
    else:
        print("背景掃描狀態時間正常；不代表策略有效或已啟用正式通知。")
    print("本機匿名過濾統計：")
    for label, count in (obj.get("gate_counts") or {}).items():
        print(" -", label, ":", count)
    print("V1.08 影子模式：不發送任何正式多空推播、不會自動下單。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
