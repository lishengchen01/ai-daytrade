/* iPhone private Web Push pairing. App's existing V1.06.1 manual notification remains.
   No Fugle key, price feed or trade execution logic on the public page.
   Remote push needs user's *own* live HTTPS private service, not GitHub Pages.
*/
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const urlField = el("push1071url"), pairField = el("push1071pair"),
    subButton = el("push1071subscribe"), testButton = el("push1071test"),
    unsubscribeButton = el("push1071unsubscribe"), status = el("push1071status");
  if (![urlField, pairField, subButton, testButton, unsubscribeButton, status].every(Boolean)) return;
  urlField.value = localStorage.getItem("private-push-service-v1071") || "";
  const say = msg => { status.textContent = msg; };
  const homeScreen = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const supported = () => location.protocol === "https:" && "Notification" in window &&
    "serviceWorker" in navigator && "PushManager" in window;
  const toBytes = base64url => {
    const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
    const s = atob(base64 + "=".repeat((4 - base64.length % 4) % 4));
    return Uint8Array.from(s, c => c.charCodeAt(0));
  };
  const config = () => {
    const url = new URL(urlField.value.trim());
    if (url.protocol !== "https:" || url.username || url.password ||
        url.search || url.hash || url.pathname !== "/" || url.hostname === location.hostname)
      throw new Error("請填寫你自己私人 HTTPS 伺服器的根網址（例如 https://notify.example.com/），不能填 GitHub Pages。");
    const token = pairField.value.trim();
    if (token.length < 32) throw new Error("請填寫私人伺服器配對碼（至少32字元），不是 Fugle API Key。");
    return {base: url.origin, token};
  };
  async function api(cfg, path, data, auth=true) {
    const options = {method: data ? "POST" : "GET", mode: "cors", cache: "no-store",
      headers: {"Accept":"application/json"}};
    if (data) {options.headers["Content-Type"] = "application/json";options.body = JSON.stringify(data);}
    if (auth) options.headers["Authorization"] = "Bearer " + cfg.token;
    const controller = new AbortController();
    options.signal = controller.signal;
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const resp = await fetch(cfg.base + path, options);
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.error || "HTTP " + resp.status);
      return json;
    } finally {clearTimeout(timeout);}
  }
  async function registration() {
    await navigator.serviceWorker.register("./sw.js", {scope:"./"});
    return navigator.serviceWorker.ready;
  }
  function check() {
    if (!supported()) {say("瀏覽器未支援 Web Push，請使用支援的 iPhone 主畫面 APP。");return false;}
    if (/iPhone|iPad|iPod/.test(navigator.userAgent) && !homeScreen()) {
      say("iPhone 請從主畫面「智慧當沖」圖示開啟，而不是從 Safari 開啟。");return false;
    }
    return true;
  }
  subButton.onclick = async () => {
    if (!check()) return;
    subButton.disabled = true;
    try {
      const cfg = config();
      // iOS permission request MUST come directly from user's tap (before other await).
      if (Notification.permission === "default") {
        if (await Notification.requestPermission() !== "granted")
          throw new Error("請先允許 iPhone 系統通知");
      }
      if (Notification.permission !== "granted") throw new Error("iPhone 通知權限被拒絕");
      say("正在連接你的私人推播服務…");
      const key = await api(cfg, "/api/v1/vapid-public-key", undefined, false);
      const reg = await registration();
      let sub = await reg.pushManager.getSubscription();
      if (!sub) sub = await reg.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: toBytes(key.publicKey)
      });
      await api(cfg, "/api/v1/subscribe", sub.toJSON());
      localStorage.setItem("private-push-service-v1071", cfg.base);
      say("遠端 Web Push 訂閱成功。現在可測試從伺服器推播；真實行情訊號仍須伺服器完成授權及全部策略驗證。");
    } catch (err) {
      say("訂閱失敗：" + String(err.message || err).slice(0, 240));
    } finally {subButton.disabled = false;}
  };
  testButton.onclick = async () => {
    if (!check()) return;
    testButton.disabled = true;
    try {
      const cfg = config();
      const res = await api(cfg, "/api/v1/test", {});
      say(res.sent > 0 ? "私人伺服器已送出遠端測試推播。請檢查 iPhone 通知中心。" :
        "沒有送出推播：請先完成遠端訂閱及檢查私人伺服器的 VAPID 金鑰。");
    } catch (err) {say("遠端測試失敗：" + String(err.message || err).slice(0, 240));}
    finally {testButton.disabled = false;}
  };
  unsubscribeButton.onclick = async () => {
    if (!check()) return;
    unsubscribeButton.disabled = true;
    try {
      const cfg = config(), reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (!sub) {say("此裝置尚未訂閱。");return;}
      await api(cfg, "/api/v1/unsubscribe", sub.toJSON());
      await sub.unsubscribe();
      say("已取消此手機的私人推播訂閱。");
    } catch(err) {say("取消訂閱失敗：" + String(err.message || err).slice(0, 200));}
    finally {unsubscribeButton.disabled = false;}
  };
  check();
})();
