# V1.08.1｜Fugle 真實多空訊號 → iPhone 私人通知安全閘（影子驗證）

## 目前真實狀態
2026-11-27 11:04 和 11:14，V1.08 Windows 工作排程器完成兩次私人 Fugle 真實行情掃描。後者讀取 29 REST、5 檔初篩，0 檔符合所有策略條件。背景五分鐘掃描在 Windows 實機正常；iPhone Apple Web Push 連線測試已成功，但**沒有完成真人盤中合格訊號的送達測試**。

## 這次 V1.08.1 做的事
1. `v1071.audit_live.audit_once` 原有 `signals` 清單及 CMD 輸出維持不變，另外在單次程序記憶體回傳已通過的 `verified_signals`，供下一層安全審核使用（不寫磁碟／GitHub／公開頁面）。
2. 新 `v108/signal_bridge.py` 對每筆訊號要求：
   - `sample is False`、`LONG_CONDITIONS` / `SHORT_CONDITIONS` 合法方向、4–6 位數字股票代號。
   - **九項原有安全條件都明確等於 True**（跳空、首根K方向與影線、量比、VWAP、大盤及族群、突破回踩、個股當沖資格、私人使用授權）；任何缺漏/額外假值都拒絕。
   - 原始 `at` 有時區、台股正常時間，與真實檢查當下同一天且不早於 90 秒、不晚於檢查時鐘。禁止以「目前時間」把過期訊號重新包裝成新通知。
   - 同一掃描內的相同日期＋股票＋方向只準備一次，`signalId=日期:股票:方向` 為後續跨掃描/重啟去重提供一致 ID。
   - 僅輸出 `schema/type/verified/sample/symbol/direction/signalId/issuedAt`，不含 Fugle 原始價格、K線、 API Key、VAPID 配對碼或券商資訊。
3. 既有 V1.08 Windows 影子掃描會呼叫此安全閘，**只在私人狀態 JSON 保存「符合手機通知安全格式數量」與「實際發送 0」**，不保存股票代碼、訊號 payload，也不對手機呼叫發送。
4. `py -m v108.status` 可檢視 `push_mode=SHADOW_DISABLED`、`push_ready_count`、`notifications_sent=0`。如果 0 候選就不會有任何準備通知。
5. 延續 Windows 登入後背景執行、5 分鐘間隔、Fugle 保守 45 REST/分鐘/進程上限；既有券商資格、策略與風控完全不變。

## 安全 / 邊界
- **這個 PR 不會讓 iPhone 真正收到正式多空訊號**，也不下單；只是用實機影子掃描測試正式發送前的訊號格式、安全閘、時效與去重鍵。原本 `push_service.deliver` 的 `WEBPUSH_DERIVED_SIGNAL_ALLOWED=NO` 仍維持關閉。
- 這版只在同次掃描內去重；跨掃描跨重啟的真正防重送，要使用 `push_service` 的 `sent(signal_id)` 去重表，並完成傳送成功/失敗測試。不得把 `push_ready_count` 誤認為 `notifications_sent`。
- 正式發送還需將現有私人 push service、VAPID 設定與推播來源驗證合併，確認經由 Apple Push 真機收到的文案與訊號時間，確保不會將測試訊號/舊訊號當成盤中建議。需再次確認手機通知不違反 Fugle 個人用途授權範圍。

## Windows 更新時機
此 GitHub 開發改版**不會自動更新電腦中的 `C:\智慧當沖3\ai-daytrade-main`**。正在運行的 V1.08 影子工作仍按舊版執行；請先讓原本運作維持不動。待 CI 通過及新版交付驗證後，先停 `AI-Daytrade-V108-Shadow`，備份專案，再更新 `v1071/audit_live.py`、`v108/shadow_loop.py`、`v108/status.py` 並新增 `v108/signal_bridge.py`；再啟動同一工作確認兩次輪詢。此階段不需要重新輸入 Fugle Key 或改動 iPhone 配對碼，若變更不同 Windows 帳戶須另查 DPAPI。
