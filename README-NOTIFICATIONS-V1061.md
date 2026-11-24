# AI 台股智慧當沖 Pro V1.06.1｜iPhone 手機通知測試版

這個分支僅加入 **iPhone 主畫面 PWA 的系統通知權限、手動本機通知測試**與日後可接收**已驗證私人 Web Push 訊息**的 service worker 骨架。原本 V1.06 的盤後選股、五分鐘策略、盤中觀察、風控及本機紀錄功能保持不變。

## 實際已完成
- `notifier-v1061.js`：檢查 HTTPS / 主畫面 PWA / 通知支援，從使用者點擊要求通知權限，並以 `ServiceWorkerRegistration.showNotification()` 發送**自己手動觸發**的測試通知
- `sw.js`：版本換成 `daytrade-v1061`，加入 `notificationclick` 導回原 APP；為未來的**已驗證**私人推播預備接收事件，不信任未驗證及模擬訊息
- `index.html`：加入「iPhone 手機通知」區塊；不影響現有欄位、策略邏輯
- `quotes.yml`：確保新 JS 隨 GitHub Pages 一起部署
- `manifest.webmanifest`：加入穩定的 PWA id
- CI 以 Node 語法檢查 JavaScript 並確認頁面、快取與部署檔案存在

## iPhone 測試方法
1. 合併並成功部署後，從 iPhone **主畫面**點選現有「智慧當沖」APP（不是直接在 Safari、LINE 或 ChatGPT 內開）。
2. 確認頁首是 `V1.06.1`。若舊版仍在，關閉 APP 再開並重新整理。
3. 點選「允許通知」，系統詢問時選「允許」。
4. 點「發送本機測試通知」，確認系統通知中心是否收到測試通知。
5. 若沒有看到通知，檢查「設定 → 通知 → 智慧當沖」與專注模式，並使用「重新檢查通知狀態」確認權限。
6. 通知寫的是「不是即時報價或做多做空訊號」。此測試不需要 Fugle API Key。

## 尚未具備（重要）
- **沒有伺服器，沒有 Web Push 訂閱儲存、推送排程或從 V1.07 傳送真正訊號**。GitHub Pages 是靜態網站，APP 關閉時不會由 `setInterval` 或此頁面自動送出通知。
- 要實現 APP 關閉後通知，須建立**私人身分驗證**、PushManager 訂閱、VAPID、公私鑰安全保存、撤銷、推送後端與可核對的行情訊號來源，並符合資料使用授權。
- 不應在任何公開網址、PWA JS、GitHub 內放 Fugle API Key 或含受限制行情的 JSON。
- 手機通知不是下單服務，亦不保證獲利或成交。

官方說明：
- https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/
- https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers
- https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site

目前分支只供通知功能驗證，請先看 CI 再合併。
