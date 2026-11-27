# V1.08.2 開發紀錄 — 本機可信掃描 → 私人 Apple Web Push

## 已核實的前提（2026-11-27）
- 既有 Windows V1.08.1 背景排程 `AI-Daytrade-V108-Shadow` 已於台灣時間 12:08:11 完成實機掃描、29 次 REST、0 個真正通過全部多空條件候選、`push_ready_count=0`、`SHADOW_DISABLED`。
- iPhone 已接收過私人「連線測試」通知，**不等於**真正交易多空推播已端對端驗證。
- GitHub Pages 公開前日行情 1,978 筆，上市 1,099、上櫃 879，交易日 2026-11-26（11/27 盤中屬正常）。
- 用戶現有 Windows 資料夾 `C:\智慧當沖3\ai-daytrade-main`，本次 GitHub PR **不會自動更新**該資料夾。

## 本版新增的本機傳送機制
- `v108/local_dispatch.py`：只有 **audit_once() 真實掃描完成**、九項條件全通過、`sample=False`、當日交易時段與 90 秒內訊號，才可在記憶體中準備 APP 自有最小 metadata。
- **不新增可由 Tailscale Funnel 網址呼叫的 /signal 或任何網路提交 API**。由現有 Windows 背景掃描程序，於本人**另行選擇加入**後，在同一個程序直接呼叫 `v1071.push_service.deliver`；原本的 HTTP 服務仍只保留私人訂閱/取消與測試通知接口。獨立工作 `AI-Daytrade-Private-Push`、Funnel、手機配對碼與 VAPID 金鑰均不會因此被覆寫。
- 僅讀取同一個 Windows 使用者私人目錄中的既有 `push.sqlite3`（內有 Apple 訂閱）與 `vapid-private.pem`。必須有至少一個既有訂閱裝置。絕對不讀取 Fugle Key 發送給手機、不放交易所原始報價、價格、K線、API Key 或私人配對碼。
- Windows 掃描器在本機、沒有預先設定時仍是 `SHADOW_DISABLED`，`notifications_sent=0`。只在本機的 `v1082-private-notify.json` 明確 `enabled=true`、多個授權/券商/手機測試確認皆嚴格 `true`，且 `vapid_subject` 有效，才會進入 `LOCAL_PRIVATE_ENABLED`；目前未提供啟用指令，尚待真機驗收。
- 每個訊號 `signalId=YYYY-MM-DD:股碼:方向`，在私人 SQLite `local_dispatch_attempts` 中於呼叫 Apple Web Push **之前**做原子保留；即使程式重啟，遇到同一日期、股票、方向，也不能自動重複通知。現有 `sent` 表會交叉檢查。這是**at-most-once 發送嘗試**：若 Apple 連線暫時失敗或程序在請求途中崩潰，為避免重複，不自動重試該 ID；可能漏掉提醒，必須明確向使用者揭露。
- 每次實際嘗試發送前再次以新時間驗證 90 秒有效期；不能刷新舊訊號的 issuedAt。
- 狀態僅保存 `attempted_alerts`、`notifications_sent`、`push_ready_count` 和模式等匿名合計；**notifications_sent 只是 Apple 供應商接受請求的次數，不代表 iPhone 最終有顯示**。
- `v108/preflight_private_push.py`：只讀取本機 VAPID/DB/授權設定存在與訂閱數，永遠不發送、不啟用正式交易訊號，也不讀 Fugle 金鑰內容。
- 既有原多空策略、API 頻率、90 秒時效與資安/當沖資格規則不放寬，不包含任何券商下單功能，也不實施自我修改真倉策略。

## 測試與上線門檻
- 目前 GitHub Actions 使用 mock 假訊號、mock sender 只做**離線防護驗證**，不會送至 Apple，不能當作真人盤中實際訊號測試。
- 在 Windows 更新程序之前，需再完成有回滾的 V1.08.2 安裝/更新工具（備份、停/啟 `AI-Daytrade-V108-Shadow`）和同一 Windows 使用者相容性檢查。
- 使用者仍須自行確認本機既有訂閱資料庫、VAPID 聯絡信箱、私人授權；確認 iPhone 與後台正常、手機接收連線測試，明確同意正式多空提醒，**才可另行建立 opt-in**。
- 需要逐一驗證：資料不足/過期、試撮、假行情、連線中斷、重複訊號、Windows 休眠與重啟、iPhone 接收後顯示的時間/方向、Apple Web Push 接受≠實際送達。真實盤中完整合格訊號可能長時間為 0，不得強制放寬策略門檻來製造通知。
- **這次 PR 只發布預設關閉的安全機制，不讓使用者以為已經開啟正式多空推播**。

## V1.08.2 預檢命令（未部署前不可用）
```cmd
cd /d "C:\智慧當沖3\ai-daytrade-main"
py -m v108.preflight_private_push
```
此命令僅在 V1.08.2 程式已安全部署到該電腦後才可執行。
