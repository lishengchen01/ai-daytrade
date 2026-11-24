const C='daytrade-v1061';self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['./','./index.html','./extra.js','./dashboard.js','./monitor.js','./intraday-v106.js','./notifier-v1061.js','./manifest.webmanifest','./icon-192.png','./icon-512.png'])).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('daytrade-')&&k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));self.addEventListener('fetch',e=>{let u=new URL(e.request.url);if(e.request.method==='GET'&&u.origin===location.origin&&!u.pathname.endsWith('/quotes.json'))e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});
// Prepared for VERIFIED private Web Push transport only. No subscription/backend exists yet.
self.addEventListener('push', event => {
  let payload;
  try { payload = event.data && event.data.json(); } catch (_) { return; }
  if (!payload || payload.schema !== 'daytrade-push-v1' || payload.verified !== true ||
      payload.sample === true || !['research-watchlist', 'risk-notice'].includes(payload.type)) return;
  const at = Date.parse(payload.issuedAt);
  if (!Number.isFinite(at) || at > Date.now() || Date.now() - at > 120000) return;
  const title = payload.type === 'risk-notice' ? '智慧當沖｜風控提醒' : '智慧當沖｜觀察清單更新';
  const body = payload.type === 'risk-notice'
    ? '請開啟 APP 檢查已核實的風控資訊。'
    : '觀察清單有新的已驗證狀態；請開啟 APP 自行確認，非下單指令。';
  event.waitUntil(self.registration.showNotification(title, {
    body, icon: './icon-192.png', badge: './icon-192.png',
    tag: 'daytrade-verified-' + payload.type, data: {url: self.registration.scope}
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(self.clients.matchAll({type:'window', includeUncontrolled:true}).then(windows => {
    const scope = self.registration.scope;
    for (const w of windows) {
      if (w.url.startsWith(scope) && 'focus' in w) return w.focus();
    }
    return self.clients.openWindow ? self.clients.openWindow(scope) : undefined;
  }));
});
