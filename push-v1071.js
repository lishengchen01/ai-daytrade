/* iPhone private Web Push pairing. App's existing V1.06.1 manual notification remains.
   No Fugle key, price feed or trade execution logic on the public page.
   Remote push needs user's *own* live HTTPS private service, not GitHub Pages.
*/
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const urlField = el("push1071url"), pairField = el("push1071pair"),
    subButton = el("push1071subscribe"), testButton = el("push1071test"),
    unsubscribeButton = el("push1071unsubscribe"), status = el("push1071status"),
    rememberField = el("push1073remember"), forgetButton = el("push1073forget");
  if (![urlField, pairField, subButton, testButton, unsubscribeButton, status,
        rememberField, forgetButton].every(Boolean)) return;
  const PAIR_STORAGE_KEY = "private-push-pairing-v1073";
  const URL_STORAGE_KEY = "private-push-service-v1071";
  const persistStatus = el("push1073persistStatus");
  const say = msg => { status.textContent = msg; };
  const showSaveStatus = msg => {
    if (persistStatus) persistStatus.textContent = "本機保存狀態：" + msg;
  };
  const getRemembered = () => {
    try {
      const obj = JSON.parse(localStorage.getItem(PAIR_STORAGE_KEY) || "null");
      if (obj && typeof obj.base === "string" &&
          /^https:\/\/[^/]+$/.test(obj.base) && typeof obj.token === "string" &&
          obj.token.length >= 32 && obj.token.length <= 512) return obj;
    } catch (_) { /* no secret or error details are shown to user */ }
    return null;
  };
  const clearRemembered = (clearInput = false) => {
    try { localStorage.removeItem(PAIR_STORAGE_KEY); } catch (_) {}
    rememberField.checked = false;
    if (clearInput) pairField.value = "";
    showSaveStatus("未保存（已清除本機配對碼）");
  };
  let priorUrl = "";
  let urlReadBlocked = false;
  try { priorUrl = localStorage.getItem(URL_STORAGE_KEY) || ""; }
  catch (_) { urlReadBlocked = true; }
  const remembered = getRemembered();
  // V1.07.3 bug: previously only the Subscribe path saved URL. A successful
  // Test request could save the token while priorUrl was empty, preventing
  // restoration on reopen. Recover from the server origin bound to the token.
  urlField.value = priorUrl || (remembered ? remembered.base : "");
  const sameOrigin = () => {
    try { return !!remembered && new URL(urlField.value).origin === remembered.base; }
    catch (_) { return false; }
  };
  if (remembered && sameOrigin()) {
    pairField.value = remembered.token;
    rememberField.checked = true;
    showSaveStatus("已從此裝置恢復，無需重新輸入配對碼");
  } else if (remembered) {
    showSaveStatus("有保存資料，但伺服器網址不同；請確認網址後重新驗證");
  } else if (urlReadBlocked) {
    showSaveStatus("無法存取網站儲存空間，請確認目前不是私人瀏覽");
  } else {
    showSaveStatus("尚未保存配對碼，勾選後需成功完成遠端測試");
  }
  const rememberAfterSuccess = cfg => {
    if (!rememberField.checked) { clearRemembered(false); return true; }
    // Store the URL and its authenticated token together and verify both
    // read back correctly. Never log or show any part of the bearer token.
    try {
      localStorage.setItem(URL_STORAGE_KEY, cfg.base);
      localStorage.setItem(PAIR_STORAGE_KEY, JSON.stringify({base:cfg.base, token:cfg.token}));
      const confirmed = getRemembered();
      const confirmedUrl = localStorage.getItem(URL_STORAGE_KEY);
      const ok = !!confirmed && confirmed.base === cfg.base &&
        confirmed.token === cfg.token && confirmedUrl === cfg.base;
      if (!ok) throw new Error("storage_readback_failed");
      showSaveStatus("已保存並成功讀回（可關閉 APP 再開測試）");
      return true;
    } catch (_) {
      try { localStorage.removeItem(PAIR_STORAGE_KEY); } catch (_) {}
      showSaveStatus("儲存或讀回失敗，請檢查此 iPhone 的網站儲存權限");
      return false;
    }
  };
  rememberField.addEventListener("change", () => {
    if (!rememberField.checked) {
      clearRemembered(false);
      say("已關閉記住配對碼；本次開啟期間仍可使用，重開 APP 後須重新輸入。");
    } else {
      showSaveStatus("已勾選，請按「發送遠端測試推播」完成驗證後保存");
    }
  });
  forgetButton.onclick = () => {
    clearRemembered(true);
    say("已忘記這台裝置的配對碼。現有 iPhone 推播訂閱不受影響。");
  };
  urlField.addEventListener("change", () => {
    const stored = getRemembered();
    if (!stored) return;
    try {
      if (new URL(urlField.value.trim()).origin === stored.base) return;
    } catch (_) { /* invalid URL also invalidates remembered credential */ }
    if (pairField.value.trim() === stored.token) pairField.value = "";
    clearRemembered(false);
    say("伺服器網址已變更，請重新輸入該伺服器的私人配對碼。");
  });
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
      try { localStorage.setItem("private-push-service-v1071", cfg.base); } catch (_) {}
      const saved = rememberAfterSuccess(cfg);
      say("遠端 Web Push 訂閱成功。" +
        (rememberField.checked ? (saved ? " 已記住此裝置配對碼。" : " 無法儲存配對碼，請檢查瀏覽器儲存權限。") : "") +
        " 現在可測試從伺服器推播；真實行情訊號仍須伺服器完成授權及全部策略驗證。");
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
      const saved = res.sent > 0 ? rememberAfterSuccess(cfg) : true;
      say(res.sent > 0 ?
        ("私人伺服器已送出遠端測試推播。請檢查 iPhone 通知中心。" +
         (rememberField.checked ? (saved ? " 已記住此裝置配對碼。" : " 無法儲存配對碼。") : "")) :
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
      clearRemembered(true);
      say("已取消此手機的私人推播訂閱，並清除本裝置儲存的配對碼。");
    } catch(err) {say("取消訂閱失敗：" + String(err.message || err).slice(0, 200));}
    finally {unsubscribeButton.disabled = false;}
  };
  check();
})();
