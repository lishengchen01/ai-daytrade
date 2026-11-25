// Offline tests for opt-in remember-pairing behavior. No API or device secrets.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "..", "push-v1071.js"), "utf8");
const STORAGE_KEY = "private-push-pairing-v1073";
const base = "https://owner-private.example";
const token = "test-only-48-character-pairing-value-0000000000000000";

function load(storage, sent = 1) {
  const els = {};
  const node = id => {
    if (!els[id]) {
      const listeners = {};
      els[id] = {value:"", checked:false, disabled:false, textContent:"",
        listeners, addEventListener:(event,fn)=>{listeners[event]=fn;}};
    }
    return els[id];
  };
  const localStorage = {
    getItem: key => storage.has(key) ? storage.get(key) : null,
    setItem: (key,value) => storage.set(key,String(value)),
    removeItem: key => storage.delete(key)
  };
  const requests = [];
  const notification = {permission:"granted", requestPermission:async()=>"granted"};
  const ctx = {
    document: {getElementById:node},
    window: {matchMedia:()=>({matches:true}),Notification:notification,PushManager:function(){}},
    Notification: notification,
    navigator: {standalone:true,userAgent:"iPhone", serviceWorker:{
      register:async()=>({}), ready:Promise.resolve({pushManager:{
        getSubscription:async()=>({toJSON:()=>({endpoint:"https://web.push.apple.com/a",keys:{p256dh:"x".repeat(50),auth:"y".repeat(22)}})})
      }})
    }},
    PushManager:function(){},
    localStorage,
    location:{protocol:"https:",hostname:"lishengchen01.github.io"},
    URL, Uint8Array, AbortController,
    atob: b64 => Buffer.from(b64, "base64").toString("binary"),
    setTimeout:()=>1, clearTimeout:()=>{},
    fetch:async (url, opts)=>{
      requests.push({url,opts});
      return {ok:true,status:200,json:async()=>({sent,publicKey:"e".repeat(87),registered:true})};
    }
  };
  vm.runInNewContext(script, ctx, {filename:"push-v1071.js"});
  return {els, requests};
}

async function run() {
  const storage = new Map([["private-push-service-v1071", base]]);
  let a = load(storage);
  assert.equal(a.els.push1071pair.value, "", "default is never remembered");
  a.els.push1071url.value = base;
  a.els.push1071pair.value = token;
  a.els.push1073remember.checked = true;
  await a.els.push1071test.onclick();
  assert.equal(JSON.parse(storage.get(STORAGE_KEY)).token, token);
  assert.equal(a.requests[0].opts.headers.Authorization, "Bearer " + token);

  a = load(storage);
  assert.equal(a.els.push1071pair.value, token, "reopen restores saved token");
  assert.equal(a.els.push1073remember.checked, true);
  a.els.push1073remember.checked = false;
  a.els.push1073remember.listeners.change();
  assert.equal(storage.has(STORAGE_KEY), false, "opt-out immediately forgets token");
  assert.equal(a.els.push1071pair.value, token, "current session may still use token");

  a.els.push1073remember.checked = true;
  await a.els.push1071test.onclick();
  a.els.push1073forget.onclick();
  assert.equal(storage.has(STORAGE_KEY), false, "forget button deletes stored token");
  assert.equal(a.els.push1071pair.value, "", "forget removes visible field only");
  assert.match(a.els.push1071status.textContent, /訂閱不受影響/);

  const failed = new Map([["private-push-service-v1071", base]]);
  const bad = load(failed, 0);
  bad.els.push1071pair.value = token;
  bad.els.push1073remember.checked = true;
  await bad.els.push1071test.onclick();
  assert.equal(failed.has(STORAGE_KEY), false, "server that sent zero pushes never stores token");

  const noOptIn = new Map([["private-push-service-v1071", base]]);
  const b = load(noOptIn);
  b.els.push1071pair.value = token;
  await b.els.push1071test.onclick();
  assert.equal(noOptIn.has(STORAGE_KEY), false, "not checked means no storage");

  const otherUrl = new Map([
    ["private-push-service-v1071", base],
    [STORAGE_KEY, JSON.stringify({base,token})]
  ]);
  const c = load(otherUrl);
  c.els.push1071url.value = "https://changed-private.example";
  c.els.push1071url.listeners.change();
  assert.equal(c.els.push1071pair.value, "", "saved pairing token not reused with another server");
  assert.equal(otherUrl.has(STORAGE_KEY), false);
  console.log("PASS: opt-in, reopen, opt-out, forget, remote test failure, URL mismatch");
}

run().catch(e=>{console.error(e);process.exitCode=1;});
