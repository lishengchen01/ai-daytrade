# V1.08.1｜在既有 Windows V1.08 上一次更新（仍為影子，不發正式多空通知）

### 先說明資料狀況
- 2026-11-27 11:59 Windows 實測 GitHub Pages `quotes.json`：抓取台灣時間 11:54、最近交易日 2026-11-26、公開股票 1,978 檔（上市 1,099、上櫃 879）。盤中使用上一個完整交易日是正常的。
- V1.08 已於 2026-11-27 11:04、11:14 完成多次背景真實行情影子掃描。
- GitHub PR #17 V1.08.1 完成真實多空訊號安全閘，但**使用者本機尚未更新**。
- V1.08.1 只增加 `push_ready_count`、`push_mode=SHADOW_DISABLED`、`notifications_sent=0` 的本機影子診斷，不真正發 Apple Push 或下單。

### 安全更新流程
使用者現有程式位置為 `C:\智慧當沖3\ai-daytrade-main`，排程已經以同一 Windows 帳戶建立 `AI-Daytrade-V108-Shadow`，且 Fugle Key 已保存在該帳戶的 Windows DPAPI。
1. 使用者在 **相同 Windows 帳戶** 點開始搜尋 CMD，選「以系統管理員身分執行」；若 UAC 要求換另一帳戶，**不要繼續**，因 DPAPI 跨帳戶可能無法解密。
2. 在 CMD 執行 `cd /d "C:\智慧當沖3\ai-daytrade-main"`。
3. 下載一次性工具（使用者自己的 GitHub）：
   `curl.exe -fL "https://raw.githubusercontent.com/lishengchen01/ai-daytrade/main/upgrade-v1081-shadow.py" -o "upgrade-v1081-shadow.py"`
4. 明確檢查下載成功，執行 `py upgrade-v1081-shadow.py`；不可使用沒有下載成功的部分檔案。
5. 工具先驗證是否為實際排程所在的資料夾、Windows 目前登入帳戶有 DPAPI 檔案，從**固定且不可變的 GitHub Commit**下載 5 個相關程式並逐檔做長度/UTF-8/語法與版本標記檢查。此時不會停背景工作。保留舊檔到 `.shadow-updates/backup_v108_時間/`。
6. 只停止 `AI-Daytrade-V108-Shadow`，替換 `v1071/audit_live.py`、`v108/shadow_loop.py`、`v108/status.py`、`v108/signal_bridge.py`、`v108/test_signal_bridge.py`，執行不連 Fugle API 的現有 Python 離線測試；中途發現錯誤會還原舊檔，並嘗試重新啟動同一工作。
7. 工具**不接觸** `AI-Daytrade-Private-Push`、Tailscale Funnel、iPhone 配對碼、Apple VAPID 伺服器、Fugle Key 或券商資料，不啟用正式多空通知。更新完成後，`py -m v108.status` 應顯示 **V1.08.1-shadow**、`push_mode=SHADOW_DISABLED`、`notifications_sent=0`。首次狀態需在下一次實際五分鐘掃描後才能看到新版本時間戳。
8. 仍沒有正式多空訊號推播。之後另行完成 V1.08.2 Windows 私有發送端、驗證來源、跨掃描去重、授權、真機端到端驗收，才可能啟用。

### 故障處理
- 如果顯示「存取被拒」、無法停止工作或錯誤 Windows 帳戶，**不要**刪除重裝 Fugle Key 或 iPhone Push，先依文字顯示檢查權限／使用者登入帳戶。
- 如果 GitHub 下載或離線測試不過，應停止更新／回復備份，且**沒有開啟正式通知**。
- 如果工作不能重新啟動，需在原本 Windows 工作排程器中檢查 `AI-Daytrade-V108-Shadow`，並提供無金鑰的錯誤資訊；此時不可聲稱已正常背景執行。
- 更新程式不會自動修改推播配對碼、Web Push 私鑰或策略條件。
