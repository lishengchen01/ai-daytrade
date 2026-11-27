# V1.08 — Windows 自動影子掃描（第一階段，不發正式訊號）

**目標：用一次安裝取代每日手動跑 `py -m v1071.audit_live`，並保留現有 iPhone 測試推播。此版不等於自動多空通知已上線。**

## 現有實機證據
2026-11-27 上午 10:18 的 V1.07.4.5 現場：盤後初篩 5 檔，Fugle REST 29 次，完整通過 0 檔。4 檔在同業與族群方向關卡遇到問題，1 檔已進入多項五分鐘策略檢查但未全數通過。這不是連線故障，不應放寬門檻強行送訊號。

## 第一階段新增
- `v108/shadow_loop.py`：Windows 登入後在背景每 **5 分鐘**執行一次，僅於週一到週五台灣時間 09:07–13:20 嘗試，後續仍由原 `scan_real` 檢查交易日/資料時效、券商資格、全部策略條件；缺資料自動安全跳過。台股假日未獨立確認前不能發正式訊號。
- **不連接** `v1071.push_service.deliver`，不打開 `WEBPUSH_DERIVED_SIGNAL_ALLOWED`，不送 Apple Web Push、不寫公開 JSON、更不連券商委託。
- 只在本機 `%USERPROFILE%\.ai-daytrade-private\` 保存 `shadow-v108-status.json` 與 `shadow-v108-history.jsonl`（每次合格數、REST 呼叫數、各條件匿名過濾數；不記錄股票代號、K線、價格、API Key、Push Token）。本階段沒有根據資料自動調整策略。
- 使用 Windows **同一個登入帳戶的 DPAPI** 加密保護 Fugle API Key 到本機 `fugle-key-v108.dpapi`；不同 Windows 使用者無法直接用此憑證啟動。DPAPI **不是硬體安全鑰匙圈**；任何能以同一 Windows 帳戶執行的惡意程式理論上仍可能解密。本人私人電腦才啟用。
- 新排程：`AI-Daytrade-V108-Shadow`（登入 Windows 時啟動，執行於 **pythonw.exe**，不需要常駐 CMD）；不刪除也不修改原本的 `AI-Daytrade-Private-Push`、Tailscale Funnel、iPhone 配對碼、VAPID 私鑰。
- 單個 process 的 Fugle REST 保守限制保持 <=45 次/60秒。每五分鐘掃描一次且防止本機重複影子程序，但**非全帳號跨程式配額**；不要同時啟動舊手動掃描或其他使用同一個 Fugle Key 的程式，避免超過基本額度。

## 安裝（只做一次）
1. GitHub CI 通過、合併後下載 main ZIP，**解壓縮到新的固定資料夾，例如 `C:\智慧當沖2\ai-daytrade-v108\`**；別覆寫或刪除正在執行的 V1.07.2 Windows 推播資料夾。zip 內最上層會有 `v108`、`v1071` 等子目錄。
2. 用 Windows 檔案總管進入同時看到 `v108` 和 `v1071` 的資料夾，直接雙擊 **`setup-v108-shadow.cmd`**（也可在此層 CMD 執行 `py -m v108.install_shadow`）。
3. 畫面核實個人 Fugle 授權、券商雙向現股當沖資格，輸入兩次 `YES`，最後 **只在 Windows 本機** 輸入一次 Fugle API Key（不回顯、不發 GitHub、不存在 script 裡）；不應在 ChatGPT 分享金鑰。
4. 出現「影子掃描排程已建立」才算完成。可在「工作排程器」中選 `AI-Daytrade-V108-Shadow`→「執行」，不須等下次登入；不會送任何手機交易推播。
5. 待第一次完整背景檢查後，CMD 在專案根目錄輸入 `py -m v108.status` 即可看到狀態時間、匿名拒絕原因數；**若目前已收盤**，看到 `outside_session` 是正常，不代表真實盤中測試通過。
6. 如果安裝器顯示失敗，不要重裝原本私人推播，也不要改用測試資料偽裝正式行情。提供不含金鑰的錯誤提示即可。

## 檢查／停止
- 查看工作是否存在：`schtasks /query /tn "AI-Daytrade-V108-Shadow"`
- 立即啟動：`schtasks /run /tn "AI-Daytrade-V108-Shadow"`
- 停止當前程序：`schtasks /end /tn "AI-Daytrade-V108-Shadow"`
- 取消未來啟動：`schtasks /change /tn "AI-Daytrade-V108-Shadow" /disable`
- 查詢本機狀態：`py -m v108.status`

Windows 關機、睡眠、沒有登入該使用者、無網路時，不會完成背景掃描。若程式更新或資料夾位置移動，排程仍指向原有安裝位置，必須重新安裝影子工作，**不要重設 iPhone 測試推播**。

## 下一階段（未啟用）
需真機觀察一段時間各時段資料有效率、滿足合法真人授權、每筆訊號時效與去重、影子紀錄正確、推播在手機關閉時實際送達，才能在另外經驗證且本人明確同意的版本加入真正的多空自動提醒。正式推播必須和目前的連線測試通知清楚區分，永遠不得推播合成／不完整資料或未驗證策略。
