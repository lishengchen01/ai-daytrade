免費獨立 PWA V1.02
將此資料夾所有檔案上傳至同一 HTTPS 靜態網站目錄（例如 GitHub Pages 免費方案，須自行建立帳號及部署）。iPhone Safari 開啟網址，分享 > 加入主畫面。首次連線後可離線使用已快取介面。未部署、未串接即時行情、無背景推播。sample.json 為模擬資料，匯入後按分析。行情欄位：prev昨收,o/h/l/c首根五分K,pv昨日總量,v首根量,p現價,w VWAP,trend及confirm為1多/-1空/0未知；價格元、成交量同單位、time資料時間。未來由授權行情後端輸出同格式，API金鑰只留後端。不要將真實交易資料上傳公開網站。做空與影線門檻待回測。

V1.04：原有功能保留。上傳根目錄檔案，另在 GitHub 建立 .github/workflows/quotes.yml（內容照套件）。Settings > Pages > Source 選 GitHub Actions；Actions > Public daily quotes > Run workflow。成功後網站發布。排程平日台灣16:30，可能延遲；休市可能回傳舊交易日。官方 API 欄位與網路尚未實測，失敗時顯示無資料或部分市場失敗。盤後初篩不是當沖訊號。未部署盤中推播。公開儲存庫不可放金鑰。

V1.05：保留原始手動策略、批次、風控、紀錄及盤後初篩。新增全部候選顯示、盤中多空分榜、九項檢查、風控帶入（以首根低/高作停損、毛3R作試算，非最佳化建議）。盤中來源尚未接通；須提供允許跨來源 CORS 的合法 HTTPS JSON 陣列，沿用 sample.json 欄位，另需 date (YYYY-MM-DD 台灣交易日)、time (ISO8601 含時區)、eligible、shortEligible、tradingDay、firstBarComplete（布林值）。trend/confirm 由供應商或後端確認，非本版自動推導。時間超過90秒或缺資格不通過。僅前景每30秒更新，離開即停止；無背景推播。請勿將金鑰放在網址或公開儲存庫。
更新：上傳 index.html、dashboard.js、monitor.js、sw.js 四檔至根目錄；修改現有 .github/workflows/quotes.yml 的 cp 那行，在 dashboard.js 後加入 monitor.js。不要覆蓋現有 quotes.json；完整套件內的 quotes.json 是初始空檔。手動執行 Public daily quotes 後重新開啟手機 APP。
