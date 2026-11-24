/* V1.06.1 iPhone Home Screen notification permission and LOCAL test only.
   Push delivery while APP is closed requires a separate authenticated backend.
   No price, trading signal or API key is accessed here. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const status = $('notify1061status');
  const allow = $('notify1061allow');
  const test = $('notify1061test');
  const refresh = $('notify1061check');
  if (!status || !allow || !test || !refresh) return;

  const isIOS = () => /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const standalone = () => window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;
  const supported = () => window.isSecureContext && 'serviceWorker' in navigator &&
    'Notification' in window && typeof Notification.requestPermission === 'function';
  const message = value => { status.textContent = value; };

  function update() {
    if (!supported()) {
      message('這個瀏覽環境不支援網頁系統通知。請使用 iPhone 主畫面中的智慧當沖 APP。');
      allow.disabled = true; test.disabled = true;
      return;
    }
    if (isIOS() && !standalone()) {
      message('iPhone 必須從主畫面點擊「智慧當沖」圖示開啟，而不是從 Safari／LINE／ChatGPT 內的網頁開啟。');
      allow.disabled = true; test.disabled = true;
      return;
    }
    const perm = Notification.permission;
    allow.disabled = perm !== 'default';
    test.disabled = perm !== 'granted';
    if (perm === 'granted') {
      message('已授權通知；可按「發送本機測試通知」。背景自動推播仍未啟用，必須接入私人伺服器。');
    } else if (perm === 'denied') {
      message('通知權限已拒絕。請到 iPhone「設定 → 通知 → 智慧當沖」檢查設定（名稱依系統顯示）。');
    } else {
      message('尚未授權。請點「允許通知」，然後再按「發送本機測試通知」。');
    }
  }

  allow.addEventListener('click', async () => {
    if (!supported() || (isIOS() && !standalone())) return update();
    // Request directly within tap handler, before awaiting any other promise.
    try {
      const permission = await Notification.requestPermission();
      update();
      if (permission === 'granted') message('通知已授權，請按下「發送本機測試通知」驗證。未連接背景伺服器。');
    } catch (error) {
      message('通知授權失敗：' + String(error.message || error).slice(0, 150));
    }
  });

  test.addEventListener('click', async () => {
    if (!supported() || Notification.permission !== 'granted') return update();
    test.disabled = true;
    message('正在嘗試顯示本機測試通知…');
    try {
      const registration = await navigator.serviceWorker.register('./sw.js', {scope:'./'});
      await registration.showNotification('智慧當沖｜手機通知測試', {
        body: '這是你手動觸發的通知測試，不是即時報價、做多或做空訊號。',
        icon: './icon-192.png',
        badge: './icon-192.png',
        tag: 'daytrade-local-test-v1061',
        data: {url: new URL('./', location.href).href, test: true}
      });
      message('測試通知已提交給系統。若未看到通知，請檢查「設定 → 通知」及專注模式。APP 關閉後的自動推播尚未啟用。');
    } catch (error) {
      message('測試通知未能顯示：' + String(error.message || error).slice(0, 200));
    } finally {
      test.disabled = false;
    }
  });

  refresh.addEventListener('click', update);
  update();
})();
