const C='daytrade-v1073';self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['./','./index.html','./extra.js','./dashboard.js','./monitor.js','./intraday-v106.js','./notifier-v1061.js','./push-v1071.js','./manifest.webmanifest','./icon-192.png','./icon-512.png'])).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('daytrade-')&&k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));self.addEventListener('fetch',e=>{let u=new URL(e.request.url);if(e.request.method==='GET'&&u.origin===location.origin&&!u.pathname.endsWith('/quotes.json'))e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});
// Prepared for VERIFIED private Web Push transport only. No subscription/backend exists yet.
self.addEventListener('push', event => {
  let payload;
  try { payload = event.data && event.data.json(); } catch (_) { return; }
  if (!payload || payload.schema !== 'daytrade-push-v1') return;
  const test = payload.type === 'connection-test' && payload.test === true;
  const verified = payload.type === 'strategy-signal' && payload.verified === true &&
    payload.sample === false && /^[0-9]{4,6}$/.test(payload.symbol || '') &&
    ['LONG_CONDITIONS','SHORT_CONDITIONS'].includes(payload.direction);
  if (!test && !verified) return;
  const time = Date.parse(payload.issuedAt);
  if (!Number.isFinite(time) || time > Date.now() + 10000 ||
      Date.now() - time > 120000) return;
  const title = test ? '智慧當沖｜私人遠端推播測試' :
    payload.direction === 'LONG_CONDITIONS' ? '智慧當沖｜做多條件候選' : '智慧當沖｜做空條件候選';
  const body = test ? '這是私人伺服器發出的連線測試，並非交易訊號。' :
    payload.symbol + '：真實資料條件檢查通過。請開啟 APP 複核風控與當沖資格；非下單指令。';
  event.waitUntil(self.registration.showNotification(title, {
    body, icon: './icon-192.png', badge: './icon-192.png',
    tag: test ? 'daytrade-remote-test' : 'daytrade-real-' + payload.signalId,
    data: {url: self.registration.scope}
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
