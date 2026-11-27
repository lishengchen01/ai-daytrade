# V1.08.2｜Windows 本機路徑 → iPhone 一次性連線測試（不發多空訊號）

## 目的
2026-11-27 iPhone 已經收到過既有私人推播伺服器發送的連線測試；Windows 的 V1.08.2 背景掃描也已獨立通過實機驗證。但新加入的「在同一 Windows 本機 Python 程序直接交給 Apple Web Push」路徑還未在實機驗證。本工具只測試此路徑，不測試股票資料或交易策略。

## 本版只做什麼
- 新增 `v108/test_local_iphone_push.py`：在 Windows 本機經本人輸入 `YES` 後，從同一私人 Windows 帳戶的 `vapid-private.pem` 和 `push.sqlite3` 讀取原本已配對的 iPhone 訂閱，輸入**以前設私人推播所用的 VAPID 聯絡 Email**，直接呼叫原本 `v1071.push_service.deliver(..., allow_test=True)`。
- 這是 **connection-test**，不使用 `v108.local_dispatch.dispatch_from_private_audit` 的模擬合格股票資料來冒充真實策略，亦不需讀/輸入 Fugle API Key。不產生任何 LONG / SHORT 交易 metadata，不寫 `v1082-private-notify.json`，臨時環境設置 `WEBPUSH_DERIVED_SIGNAL_ALLOWED=NO` 並立即還原。
- 訊息會透過 Apple Web Push 交由既有 iPhone APP service worker 顯示：**「智慧當沖｜私人遠端推播測試」**。Apple 接受請求與 iPhone 實際顯示是兩個不同驗收結果；務必看手機確認。
- 既有私鑰、配對碼、Tailscale、背景工作與股票選股風控、當沖資格設定均不修改。若 Apple 訂閱無效，既有 `deliver` 安全邏輯可能移除 404/410 失效裝置。
- Windows CI mock 網路發送，驗證必須有人確認、只發 test payload、正式多空通知不能順便打開、環境設置還原、無 Apple 訂閱或無效 Email 不發送。本次 CI **不會真的發到 iPhone**。

## Windows 本機操作（本工具已合併、安裝後）
在既有 Windows 帳戶開普通 CMD，進入既有 `C:\智慧當沖3\ai-daytrade-main`，**一行一行輸入**：
```cmd
cd /d "C:\智慧當沖3\ai-daytrade-main"
curl.exe -fL "https://raw.githubusercontent.com/lishengchen01/ai-daytrade/main/v108/test_local_iphone_push.py" -o "v108\test_local_iphone_push.py"
py -m v108.test_local_iphone_push
```
必須在第二行下載 100% 無誤後才進第三行。第三行會確認是否只發一則測試通知；輸入 `YES` 再輸入聯絡 Email。**輸入的是聯絡 Email，不是 Fugle Key、配對碼、密碼**；Email 只用於當次 VAPID 請求，不會被寫進腳本、GitHub 或日誌。

正常結果 `Apple Web Push 供應商接受請求數: 1`（或視裝置數而定），**仍需要 iPhone 實際收到通知**才能驗收成功。若結果 0 或例外，保持正式推播關閉並只提供不含 Email 和私人金鑰的錯誤截圖。

## 仍未完成
正式股票偏多/偏空推播的自願啟用、真正通過全部條件時的 iPhone 送達驗證、失敗/重試可靠性、假日與重啟驗證仍未完成。**測試成功不代表已可正式交易推播，更不代表自動下單。**
