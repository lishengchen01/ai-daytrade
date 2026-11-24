# V1.07｜真實盤中行情接收 + 審慎多空條件判斷

**狀態：原始碼已建置，尚未連接私人 Fugle API 金鑰，也沒有私人雲端後端。這不是已上線的即時選股服務。** 此分支不改 GitHub Pages/手機 V1.06 的正式畫面及每日盤後排程。

## 官方來源與費用（2026-11-24 核對）

- Fugle 基本行情方案：免費，REST 日內查詢 60 次/分鐘、WebSocket 5 個「標的×頻道」訂閱、1 連線。
- 開發者：NT$1,499/月，REST 600 次/分鐘、WebSocket 300 訂閱。
- https://developer.fugle.tw/docs/pricing/
- https://developer.fugle.tw/docs/data/http-api/getting-started/
- https://developer.fugle.tw/docs/data/intro/

## 版權、隱私與授權

Fugle 與臺灣證券交易所/櫃買中心的即時資料有使用及再傳輸限制。**禁止**把 Fugle API Key 或未獲再轉播授權的盤中行情寫入 GitHub、GitHub Actions log、GitHub Pages、公開 JSON、公開推播服務或直接塞入 iPhone PWA 的 JS。
這個後端只供個人私有運行，僅輸出判斷結果（沒有原始授權行情）；**是否允許在雲端給個人手機查看衍生訊號，需再向供應商核實**。
任何真正 iPhone 獨立盤中顯示都需專用、經驗證的私人服務。

## 實際程式功能

- fugle.py：以 FUGLE_API_KEY 環境變數私下呼叫 REST /intraday/quote/{symbol} 及 /intraday/candles/{symbol}?timeframe=1。
- runner.py：從目前 GitHub Pages 的免費盤後 JSON 自動擷取前一日候選（2–4% / 500 張 / 最多五檔），以 Fugle 真實資料計算，不使用假的實時資料。
- strategy.py：把 09:00–09:04 **五根完整 1 分 K** 合成首根五分鐘K；檢查跳空、紅黑K、端影線 ≤20%、首根量達前日 10%、當日成交均價/VWAP、突破與回踩或跌破與反彈、當日行情時效、獨立驗證大盤與族群方向、當沖與先賣後買資格；不通過一律 WAIT。
- test_strategy.py：只使用本地合成資料做單元回歸測試，不呼叫 Fugle、不需要金鑰。
- 不連接任何下單 API；trade_action_enabled=false、place_order=false。

### 必須事先自動取得／驗證的外部條件

真實策略完整訊號還缺**由獨立授權來源**驗證的當日交易日、大盤、各股族群強弱、當沖與先賣後買資格。context 缺任何欄位或超過90秒自動判定 WAIT。這不是把欄位設定成 true 就算核實，不能用測試/手動猜測值代替實際查核。

## 私人環境運行（僅示範程式操作，不需提供金鑰給 ChatGPT）

1. 至 https://developer.fugle.tw/docs/key/ 註冊會員並申請 API Key。
2. 在**個人受保護**的系統環境變數設定 FUGLE_API_KEY。切勿貼到聊天、GitHub 或公開網站。
3. 預設 python v107/runner.py 只執行一次並輸出私人判斷；要在專屬後端長期運作才使用 --loop（至少間隔30秒）。
4. --context 可傳入由**自動且已查證**的其他資料源建立的私人 JSON，並須包含時間/資格/授權等確認欄位；目前尚無自動 context provider，所以即使 Fugle 連線成功，正式交易狀態仍會是 WAIT。
5. python -m unittest discover -s v107 -p 'test_*.py' -v 做離線回歸測試。

## 為何不能直接在 GitHub Actions 每30秒執行

GitHub Actions 的定時工作不是分鐘級即時服務；而且公開儲存庫不得因測試方便就將即時行情或金鑰發布成公開 JSON。正式上線需具身分驗證、保密及授權的私有持續運行服務，並經供應商確認允許個人雲端接收與展示。

## 下一步待驗證

1. 使用者完成 Fugle 個人 API Key 申請（不需交出 Key）。
2. 向供應商確認個人私有雲端實例運行、衍生訊號輸出、個人 iPhone 查看是否合規。
3. 實測 09:05 前後 K 棒、最新交易時間以及流量限制。
4. 引入交易所的當沖資格與各標的族群、指數合法實時資料；在未完成前不發多空進場訊號。
5. 統計歷史回測、各策略單筆最大虧損與成交成本；保留舊版全部功能。
