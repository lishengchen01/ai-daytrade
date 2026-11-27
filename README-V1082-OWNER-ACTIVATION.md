# V1.08.2｜本人 iPhone 正式多空提醒：安全啟用、核對、停用

**目的：** 在已成功驗證 Fugle 本人私人真實行情掃描（V1.08.2）與 Windows → Apple Web Push → iPhone **真機連線測試**（2026-11-27 17:44）後，僅允許使用者本人 iPhone 收到真正符合全部策略條件的偏多／偏空觀察通知。**不自動下單、不是保證獲利或成交的交易指令。**

## 重要的安全補強
- `v108/local_dispatch.py`：原來要求本機訂閱數至少 1；現在必須剛好 **1 台**，並與本機啟用時紀錄的 **Apple 訂閱 endpoint SHA-256 指紋** 一致；任何第二台、取消/重配/更換 endpoint，則退回 `SHADOW_DISABLED`。指紋僅存本人 Windows 私人資料夾，不向網頁或推播傳送。
- `v1071/push_service.py`：最後從 SQLite 讀訂閱清單時仍須**再次**確認只剩原本那台；所有未綁定指紋的正式訊號都拒絕（即使舊服務設定 `WEBPUSH_DERIVED_SIGNAL_ALLOWED=YES`），避免 race condition。現有訂閱與測試通知 API 不變。
- `v108/manage_private_alerts.py`：僅 Windows 原帳戶，先檢查 `AI-Daytrade-V108-Shadow` 實際工作位置、最近 11 分鐘的 V1.08.2 狀態、原本私人 Fugle/券商資格、同帳戶 DPAPI 可以成功解密、P-256 VAPID 私鑰合法、Apple 訂閱恰好 1 台且格式合法。**無任何 Fugle API 呼叫、Apple Push 呼叫或券商下單。**
- 啟用時僅在本機輸入大寫 `ENABLE` 與原本 VAPID 聯絡 Email（不回顯），私下原子寫入 `%USERPROFILE%\.ai-daytrade-private\v1082-private-notify.json`。不讀/儲存 Fugle API Key 明文、不修改配對碼/Tailscale/原 Windows 排程、不把 endpoint 儲存到設定。
- `disable` 立即移除 opt-in 檔案；後續的掃描會立即停止新推播資格。**已經在傳送中的通知可能無法撤銷**，若有緊急中止需求，還須於工作排程器停止原工作。取消 opt-in **不取消手機訂閱、不關閉影子掃描、不下單**。

## 使用者自己在 Windows 操作
**請等此 PR 的 Windows 自動測試通過，再用正式的安全安裝器將安全修正與管理工具部署到 `C:\智慧當沖3\ai-daytrade-main`。光合併 GitHub 不會更新 Windows 本機。**

安裝完成後，使用**原來的 Windows 使用者**在 CMD，一次只輸入一行：
```cmd
cd /d "C:\智慧當沖3\ai-daytrade-main"
py -m v108.manage_private_alerts check
py -m v108.manage_private_alerts enable
```
第三行會在安全預檢通過後詢問 `ENABLE`，再詢問**VAPID 聯絡 Email（不是 Fugle Key／配對碼）**。完成後可重新輸入：
```cmd
py -m v108.manage_private_alerts check
py -m v108.preflight_private_push
py -m v108.status
```
前兩個檢查應顯示本人唯一 iPhone 與私有授權。注意 `py -m v108.status` 是最近**已完成**的五分鐘掃描摘要：啟用後要等下一次背景輪詢才能顯示 `LOCAL_PRIVATE_ENABLED`；**若是非盤中時段會顯示 outside_session、SHADOW_DISABLED，此為正常**，不代表啟用失敗。使用 `manage_private_alerts check` 會直接讀當下 opt-in 及配對指紋。

**一行即可停用：**
```cmd
py -m v108.manage_private_alerts disable
```
即使背景工作因故未運行，也可以停用；這會移除私人授權檔。確認停用請再次輸入 `check`。若出現第三方改動、多台訂閱或不同 Windows 帳戶，啟用器會拒絕，不可直接手動把 JSON 的 enabled 改為 true 繞過。

## 正式實機驗收（不造假訊號）
1. **現在已成功：** V1.08.2 本機直接 Apple Web Push 真機連線測試：Apple 接受 1、iPhone 實際收到 1（2026-11-27 17:44）；不需要重複貼 Fugle Key。
2. 安全補強與啟用器 Windows CI 綠燈，更新本機後先核對 `check`、`preflight`、`status`。本人在 Windows 明確 `ENABLE`；不會立即發一筆假股票通知。
3. 下一個合法台股交易日開盤 09:07–13:20：Windows 保持登入、開機、連網與不休眠。每 5 分鐘背景掃描；資料來源需全部驗證，真實合格候選為 0 時**就不發送**。不能放寬多空策略、補假行情或把測試當真實訊號。
4. 背景 `py -m v108.status` 只看狀態數量：版本、最近時間、是否 completed、符合策略數、符合推播條件數、attempted_alerts、供應商接受數、`LOCAL_PRIVATE_ENABLED`。若仍為 `SHADOW_DISABLED`，請優先核對 `manage_private_alerts check` 是否已啟用，且訂閱是否未變。
5. 僅在市場真的出現全九條件合格、本人已允許時，iPhone 可能收到 `智慧當沖｜做多條件候選` 或 `智慧當沖｜做空條件候選`，內含股票代碼；驗證消息方向、日期及時間。Apple provider 接受不代表 iPhone 已顯示，須本人確認。請回報不含密鑰的畫面。
6. 防重複與漏訊號：每日期/股票/方向會在本機 SQLite 保留一次發送嘗試（at-most-once），避免因每五分鐘輪詢或重啟而重複提醒；**若網路臨時失敗，可能不重試該筆**。推播只是額外研究提醒，不能當成穩定交易執行系統。

## 回復與風險
- 如果 iPhone 通知出錯，**先停用**，不必重裝程式。
- 如果背景掃描異常／時間停更，預設不發正式訊號。不要把通知當成一定會送達。
- 原本 `AI-Daytrade-Private-Push`、配對碼、Tailscale、Fugle DPAPI 加密金鑰不能被新安裝器覆蓋；若有例外應阻止更新並備份回滾。
- 正式交易訊號必須經現有全部真實來源及策略門檻，不適用合成／模擬行情；不進行任何券商下單。
