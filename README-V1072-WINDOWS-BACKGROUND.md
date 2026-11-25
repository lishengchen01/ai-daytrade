# V1.07.2 Windows 背景推播（不必每天打開 CMD）

本次是 **test-only 的私人 Web Push 常駐服務**。不使用 Fugle API Key，不啟動真實多空策略，不下單。只有合法且已驗證的測試通知能送出；真實策略通知需另外確認行情授權與策略實盤驗證。

## 取得及安裝
先審核本 PR、通過 Windows CI，合併到 main 後取得新版程式。安裝前**不要關閉**原有兩個 CMD；手機原本遠端測試已成功，不需要重新訂閱。

1. 使用已安裝的 Windows 電腦，將新版程式解壓至固定路徑（避免日後移動資料夾使排程失效）。確保 `v1071/push_background.py` 存在。
2. 雙擊 `INSTALL-PRIVATE-PUSH-BACKGROUND.cmd` 一次，輸入與原先推播服務相同的 VAPID 聯絡 Email。只建立使用者登入排程，**不會立即切換現有服務**。若 Windows 排程權限不足，安裝器會顯示錯誤；不要繞過安全檢查。
3. 安裝完成後，先在原本的「私人推播服務 CMD」按 `Ctrl+C` 停止**舊的 8787 服務**。不要刪掉 `%USERPROFILE%\.ai-daytrade-private`。
4. 開啟 Windows「工作排程器」（Task Scheduler），找到 `AI-Daytrade-Private-Push`，右鍵「執行」。或用 PowerShell（只需切換這次）輸入 `Start-ScheduledTask -TaskName "AI-Daytrade-Private-Push"`。
5. 在 Windows 新 CMD 測試（只要測一次）：
   `curl -H "Origin: https://lishengchen01.github.io" http://127.0.0.1:8787/api/v1/health`
   預期 `{"status":"online","mode":"private-research","place_order":false}`。
6. 將 Tailscale 原本的**前景 Funnel CMD** 停止（`Ctrl+C`），在 CMD 輸入一次 `tailscale funnel --bg 8787`，確認顯示 `https://desktop-da434is.tail667184.ts.net/` 並轉送 `127.0.0.1:8787`。**此步會對公網開放 HTTPS 入口**；務必確認仍需要從 iPhone 遠端連線。這是原有 Tailscale Funnel 的背景持續模式。
7. iPhone 主畫面開啟原 APP，按「發送遠端測試推播」驗證。**不要再按取消訂閱，也不要重產金鑰**。
8. 登出再登入 Windows 後：預期排程自動啟動 8787，Tailscale Funnel 背景持續運作；再次用手機測試，才算 Windows 實機驗證通過。

## 限制與回復
- 本版沒有真實自動多空訊號推播，Fugle 授權信未回覆前**不應啟用**。背景程序強制 `WEBPUSH_DERIVED_SIGNAL_ALLOWED=NO`。
- Windows 電腦要保持開機、已登入、連網、避免休眠；不是雲端常駐服務。
- 配對碼、VAPID 私鑰及既有 iPhone 訂閱儲存在既有私人資料夾，安裝器只新增同一資料夾的 `push-background.json`（聯絡 Email）及 `push-background.log`（一般狀態，不記金鑰）。
- 排程可在工作排程器停用；不要刪除既有密鑰或 SQLite 資料庫。
- 如果背景服務沒有啟動，查看 `%USERPROFILE%\.ai-daytrade-private\push-background.log`，不包含配對碼或原始行情。檢查 8787 是否已被舊 CMD 服務占用。
- 不要同時開前景與背景的 8787 服務，否則其中之一無法繫結連接埠。
- 要完全停止公開遠端入口：`tailscale funnel off`。如果只是需要原本的前景方式，停用排程後仍可使用 `py -m v1071.start_windows`；Funnel 可再 `tailscale funnel 8787`。

## 驗證
- GitHub Windows 離線測試：`python -m unittest v1071.test_push_background -v`
- Windows 實機測試：排程登入、8787 health、iPhone 受保護的遠端測試通知、電腦重新登入後再次驗證
