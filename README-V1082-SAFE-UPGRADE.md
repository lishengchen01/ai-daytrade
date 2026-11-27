# V1.08.2｜一次安全更新 Windows 私人背景掃描（仍預設不發正式訊號）

2026-11-27 現有 `C:\智慧當沖3\ai-daytrade-main` 已實測 V1.08.1-shadow 背景每五分鐘掃描、已訂閱 Apple Web Push 連線測試成功。V1.08.2 在 GitHub 完成**離線**本機傳送通道與 SQLite 跨重新啟動去重；其正式發送需要另外明確的本機 `v1082-private-notify.json` opt-in，**本更新工具不建立此設定，也不開啟正式交易提醒**。

## 安全更新
使用者以最初安裝的 Windows 帳戶開啟管理員 CMD，不得換另外一個 Windows 帳戶，因 Fugle Key 受 Windows 同帳戶 DPAPI 保護：

```cmd
cd /d "C:\智慧當沖3\ai-daytrade-main"
curl.exe -fL "https://raw.githubusercontent.com/lishengchen01/ai-daytrade/main/upgrade-v1082-shadow.py" -o "upgrade-v1082-shadow.py"
py upgrade-v1082-shadow.py
```

**第二行確定顯示 100% 後才執行第三行。** 工具不會要求再次提供 Fugle Key。

工具先檢查：目前所在資料夾真的是 `AI-Daytrade-V108-Shadow` 排程實際使用的路徑，而且登入使用者仍有原加密 Fugle Key；從固定 SHA `798816cda847b1a5e6f231199dd411f8f8e2c704`（PR #21 合併後不可變程式）下載並語法驗證 5 個檔案。驗證成功才停止工作、備份舊版、更新檔案、執行離線回歸測試，再重新啟動原背景工作。失敗會嘗試還原。

本次只有這些檔案會更換：
- `v108/shadow_loop.py`
- `v108/status.py`
- `v108/local_dispatch.py`（新）
- `v108/test_local_dispatch.py`（新）
- `v108/preflight_private_push.py`（新）

不會修改 `v1071/push_service.py`、既有配對碼、`vapid-private.pem`、`fugle-key-v108.dpapi`、Tailscale，也不會清空現有 `push.sqlite3` 訂閱資料庫。

## 檢查更新後狀態
程式更新成功後，新背景工作要完成一次掃描才會更新狀態：
```cmd
py -m v108.status
py -m v108.preflight_private_push
```
正常的安全狀態應顯示：
- **V1.08.2-shadow**、`status=completed`、新的掃描時間；
- `push_mode=SHADOW_DISABLED`、`notifications_sent=0`（正式通知尚未啟用）；
- 預檢可讀到既有 iPhone 訂閱數、VAPID 私鑰與本機 DPAPI 金鑰*是否存在*（不顯示金鑰內容）。
- 如果本次無完整策略合格股票，`push_ready_count=0` 是合理研究結果。

## 還沒完成
需要先以獨立**真正 Apple 連線測試**驗證由本機新傳送路徑抵達 iPhone，顯示「測試通知」而非交易提示，再由本人明確同意啟用，並針對自然產生的盤中合格訊號進行實機驗收。**CI 通過、更新工具完成，都不等於正式 iPhone 多空通知已可使用**。本版本不下單、不放寬任何選股／券商資格／90 秒時效條件。
