# AI 台股智慧當沖 Pro V1.07.1：私人 Web Push ＋ Fugle 真實行情自動訊號

**狀態：已完成可測試的全鏈路程式；目前尚未部署私人伺服器、尚未與用戶的 Fugle Key 實際連線，也尚未從關閉的 iPhone 收到真實策略訊號。** 本 PR 將程式放在開發分支，不能把程式完成誤認為服務已啟用。

## 保留內容與範圍

保留 `main` 原本的 V1.06/V1.06.1 盤後免費選股、V1.05 監控、五分鐘策略、風控、本機歷史紀錄、iPhone 手動通知測試。新增 `v1071/` 私人 Python 服務（**不**放進 GitHub Pages 發布檔案）、手機訂閱 UI 和 Web Push Service Worker。

### 真正會查詢的市場資料

在正常交易日 09:07～13:20，以最多 5 檔「前一個有效交易日價格變動 2–4% 且日量 >=500張」的候選為基礎，私人掃描器會從 Fugle 官方 REST 對每檔取得：

- `intraday/ticker/{symbol}`：上市櫃、證券狀態、產業別、現股當沖及先買後賣資格。
- `intraday/quote/{symbol}`：當日最新成交時間、前收、最新價、成交均價（VWAP 方向）。
- `intraday/candles/{symbol}?timeframe=1&sort=asc`：實際 09:00–09:04 五根完整 1 分鐘 K，首根量/前日量、影線、突破回踩。
- `intraday/tickers?type=EQUITY&exchange=TWSE&industry=...`：實際同產業股票名單；與前日公開量排序取得兩個同產業參考標的，檢驗當日實際成交價方向。
- `intraday/tickers?type=INDEX&exchange=TWSE`：查找已驗證加權指數代碼，或者從私人 config 指定已核實的指數代碼；查詢實際指數方向。不能確定則 WAIT。

每次掃描間隔 >=60 秒（避免免費方案 60 REST 呼叫／分鐘限制）。**所有 K 線與行情均是真實 API 取得，不以合成資料補缺；缺少行情、券商權限、市場／產業、過期資料、交易資格、符號或數據異常時一律不發交易訊號。**

標的證券的 `canDayTrade` 和 `canBuyDayTrade` **不能代替使用者券商帳號的現沖權限、可用額度與先賣後買授權**；本版要求私人 config 明確確認。**策略發出的只是研究候選，無交易委託 API。**

## Web Push：真正「APP 關閉後」也能收到

1. iPhone 主畫面 PWA（iOS 16.4 或以上）在 `V1.07.1 私人自動訊號推播` 區域輸入 **自己的私人 HTTPS 伺服器網址**及單獨生成的 **配對碼（不是 Fugle Key）**。
2. 由使用者點擊「訂閱私人遠端通知」呼叫 PushManager.subscribe；僅將 iPhone 的訂閱端點及推送公鑰上傳到私人伺服器；訂閱資訊保存在用戶本機私人 SQLite，並非 GitHub。
3. 由使用者點擊「發送遠端測試推播」→ 私人 Python 伺服器呼叫 Apple Web Push，確認真正背景伺服器發送通知；這是明確標記的「測試通知」，非行情。
4. 實際買賣候選訊號只由 `scan_loop` 的 **Fugle 真實行情** 通過全部判斷，且 `WEBPUSH_DERIVED_SIGNAL_ALLOWED=YES`（**必須已獲資料供應商確認這種私人衍生訊號使用符合授權**）時推送。
5. 推播只帶股票代碼、方向、時間與訊號 ID。**不帶 Fugle API Key、原始報價、K線、VWAP 具體數字，也不代客下單**。同股同向同日去重，防止重複通知。

## 部署前提：請先看這段

- **GitHub Pages 不會執行 Python，也不能接受手機推播訂閱**，需一個持續運作且具合法 HTTPS 憑證的私人服務（可選私人 Windows 電腦 + 受信任的 HTTPS 反向代理/通道，或私人 VPS；免費與費用取決於主機與域名）。
- Windows 電腦如果睡眠、關機或網路斷線，背景掃描停止；iPhone 收不到自動通知。
- 需向 Fugle 確認個人 API 用於私人常駐程式、私人衍生訊號推送到個人 iPhone 是否在授權範圍內。在確認前不可啟用正式訊號 `WEBPUSH_DERIVED_SIGNAL_ALLOWED`。
- 公開 GitHub、GitHub Actions、公開 PWA **不得**放 `FUGLE_API_KEY`、`PUSH_PAIRING_TOKEN`、VAPID 私鑰、實際訂閱端點、原始行情資料及可交易訊號 JSON。
- 如果私人端點公開可達，務必透過 HTTPS、隨機高熵配對碼及限制 CORS，限制訂閱數量、針對異常啟用防火牆/流量限制。此版後端是**初始安全骨架**，不是完成資安稽核的商業服務。

## Windows 本機準備（在專案根目錄執行）

先將本分支取得到 Windows 私人工作資料夾，確認使用 Python 3.12+：

```cmd
py -m pip install -r v1071\requirements.txt
py -m v1071.create_vapid_keys
```

第二行會將 VAPID 私鑰安全產生於用戶的 `%USERPROFILE%\.ai-daytrade-private\vapid-private.pem`。**私鑰不能上傳或截圖**；列印的 `VAPID_PUBLIC_KEY` 是公開金鑰，可填入後端環境變數。

你需要在**私人執行環境**設定（數值僅為名稱示範；不要直接使用假字串）：

```text
PUSH_PAIRING_TOKEN           = 用密碼管理工具生成的至少 32 字元隨機配對碼
VAPID_PRIVATE_KEY_PATH       = 本機 VAPID 私鑰完整路徑
VAPID_PUBLIC_KEY             = 上述程式輸出的公開金鑰
VAPID_SUBJECT                = mailto:你自己的有效聯絡信箱
DAYTRADE_DB_PATH             = 使用者私人資料夾內 SQLite 路徑（未設定時自動存於家目錄）
FUGLE_API_KEY                = 你現有的 Fugle 私人金鑰（只供掃描器）
PRIVATE_CONFIG_FILE          = 你在私人目錄另建的 JSON 設定檔路徑
FUGLE_PRIVATE_USE_CONFIRMED  = YES（僅在確認個人使用授權後）
WEBPUSH_DERIVED_SIGNAL_ALLOWED = YES（僅在確認衍生推播授權後）
```

根據 `v1071/private-config.example.json` 建立**私人** `private-config.json`，位於 GitHub 專案外。只有本人確實確認券商現股當沖權限後，才可把 `broker_permission_verified` 設定為 true；`broker_sell_first_verified` 要另外確認先賣後買權限。大盤指數代碼可留空讓程式查找，不唯一時全部 WAIT，不能亂猜。

私人伺服器由反向代理提供 **公開可由 iPhone 存取的 HTTPS**，並轉送到本機 `127.0.0.1:8787`；不要把本機 HTTP 直接暴露到網際網路：

```cmd
py -m v1071.start_windows
```

**給 Windows 使用者的簡易啟動程式**：會自動產生不外傳的 VAPID 私鑰及高強度私人手機配對碼，存在 `%USERPROFILE%\.ai-daytrade-private\`，提示輸入自己的聯絡 Email，再於本機 `127.0.0.1:8787` 啟動服務。**不會要求 Fugle 金鑰，也不會自動打開正式行情推播**。請先用這個功能驗證真正遠端推播。

進階手動啟動可用：

```cmd
py -m v1071.serve
```

手動啟動時，需要自行在私人環境變數配置前述 VAPID 和配對資料。

**在另一個已設定 Fugle 個人金鑰與私人 config 的命令視窗**：

```cmd
py -m v1071.scan_loop
```

後端站的 `/api/v1/vapid-public-key` 和 `/api/v1/subscribe` 用於手機訂閱；只有來自 `https://lishengchen01.github.io` 的網頁請求被允許。勿把配對碼貼入聊天、公開 repo、URL 查詢字串或網站 JS。後端測試 API 只會發出「私人遠端推播測試」；與實際交易訊號完全分離。

## 明確尚待真人實測

- 用戶本人的 Windows 或私人雲端主機 **尚未安裝／部署** 本後端，**尚未進行手機遠端 Web Push 真機測試**。
- 真正當日行情的加權指數清單、產業同儕資料、瞬時資料量及延遲，需開盤時 Fugle 真實 Key 實測。
- 策略績效、當沖成本、個人券商額度及行情授權需要逐項確認；不要將條件通過當成保證成交或獲利。

## 文件

- Fugle https://developer.fugle.tw/docs/data/http-api/intraday/quote/
- Fugle https://developer.fugle.tw/docs/data/http-api/intraday/candles/
- Fugle https://developer.fugle.tw/docs/data/http-api/intraday/ticker/
- Fugle https://developer.fugle.tw/docs/data/http-api/intraday/tickers/
- Fugle https://developer.fugle.tw/docs/pricing/
- Apple/WebKit https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/

## 免費優先的 Windows → iPhone HTTPS 測試路線（可選）

Tailscale Personal 提供免費方案，而 **Funnel** 可以在符合帳號/裝置條件時提供 `*.ts.net` HTTPS 網址，不必先購買自己的網域。**Funnel 是公開網路入口，不等於私人驗證**；所以本程式仍要求至少 32 字元的私人配對碼、同源限制，且只接受 Apple Web Push 訂閱端點。

1. 先安裝 Tailscale（https://tailscale.com/download），登入個人帳號；Windows 使用系統管理員權限執行 Funnel。
2. 保持 `py -m v1071.start_windows` 的 CMD 視窗執行中。
3. 在另一個系統管理員 CMD 輸入：

```cmd
tailscale funnel 8787
```

4. 依畫面核准開啟 HTTPS 與 Funnel，取得 `https://你的裝置.你的網路.ts.net/`。不要把本機 `http://127.0.0.1:8787` 當成手機可用網址。
5. iPhone 主畫面打開 **V1.07.1**，輸入上面的 HTTPS URL，再從本機私人檔案 `pairing-token.txt` 查看**私人配對碼（非 Fugle Key）**，點「訂閱私人遠端通知」→「發送遠端測試推播」。
6. 遠端測試成功後，才規劃真正行情掃描的授權確認、券商資格核實及 `scan_loop` 常駐。

**注意**：iPhone 訂閱是屬於**正式 GitHub Pages 來源**的 Service Worker，尚未合併部署本 PR 時，手機上看不到新按鈕；不要因為本機伺服器已啟動就宣稱手機推播已上線。Funnel 的開放會把後端入口暴露在公開網路，請保護本機資料與配對碼，也請按服務商條款評估是否適合長期運行。

官方說明：https://tailscale.com/docs/features/tailscale-funnel 、https://tailscale.com/pricing
