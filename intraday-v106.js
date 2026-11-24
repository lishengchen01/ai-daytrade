/* V1.06 public-data adapter. Not a real-time provider. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
let active=false,rows=[],meta=null,lastError='';
const tw=d=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(d);
const keys=['prev','o','h','l','c','pv','v','p','w'];
function evaluate(a){
 const checks=[];if(keys.some(k=>typeof a[k]!=='number'||!Number.isFinite(a[k])))return {checks,reason:'五分鐘欄位不足',dir:0};
 const {prev,o,h,l,c,pv,v,p,w}=a;
 if(Math.min(prev,o,h,l,c,pv,p,w)<=0||v<0||h<=l||h<Math.max(o,c)||l>Math.min(o,c))return {checks,reason:'K棒或成交量不合法',dir:0};
 const gap=(o/prev-1)*100,dir=Math.sign(gap),wick=(dir>0?h-c:c-l)/(h-l)*100,volume=v/pv*100;
 const now=Date.now(),today=tw(new Date()).slice(0,10),clock=tw(new Date()).slice(11,16),dow=new Date(today+'T12:00:00Z').getUTCDay(),at=Date.parse(a.time);
 const fresh=Number.isFinite(at)&&at<=now&&now-at<=90000&&tw(new Date(at)).slice(0,10)===today;
 checks.push(['跳空 2～4%',Math.abs(gap)>=2&&Math.abs(gap)<=4],['五分鐘K方向',dir*(c-o)>0],['收盤端影線 ≤20%',wick<=20],['首根成交量 ≥10%',volume>=10],['VWAP',dir*(p-w)>0],['大盤與族群',a.trend===dir&&dir!==0],['突破／跌破',a.confirm===dir&&dir!==0],['現股當沖資格',a.eligible===true&&(dir>0||a.shortEligible===true)],['當日行情時效',fresh&&dow>=1&&dow<=5&&clock>='09:05'&&clock<='13:20'&&a.tradingDay===true&&a.firstBarComplete===true&&a.date===today]);
 return {checks,dir,reason:checks.every(x=>x[1])?'條件符合輸入資料；來源尚未獨立核實，非交易訊號':'等待／不進場',gap,volume};
}
function display(){
 const status=$('live106status'),out=$('live106results');if(!status||!out)return;
 status.textContent='行情來源：'+(meta?.source||'未接入')+'\n更新時間：'+(meta?.generatedAt||'未提供')+'\n股票筆數：'+rows.length+(lastError?'\n狀態：'+lastError:'');
 out.replaceChildren();
 for(const dir of [1,-1]){
  const h=document.createElement('h3');h.textContent=dir===1?'🔴 做多觀察':'🟢 做空觀察';out.append(h);
  const candidates=rows.map(a=>({a,r:evaluate(a)})).filter(x=>x.r.dir===dir).sort((x,y)=>y.r.checks.filter(v=>v[1]).length-x.r.checks.filter(v=>v[1]).length).slice(0,5);
  if(!candidates.length){out.append(document.createTextNode('沒有可驗證候選'));continue;}
  for(const {a,r} of candidates){
   const section=document.createElement('section');section.style.background='#101827';
   const title=document.createElement('strong');title.textContent=String(a.symbol||'無代號')+'｜'+r.reason;
   const details=document.createElement('pre');details.textContent=r.checks.map(([k,v])=>(v?'✓ ':'✗ ')+k).join('\n');
   section.append(title,details);out.append(section);
  }
 }
}
async function refresh(){if(active||document.hidden)return;active=true;
 try{const r=await fetch('./intraday.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
 const j=await r.json();if(!Array.isArray(j.rows)||j.rows.length>5000||j.mode==='sample')throw Error('資料格式無效');
 rows=j.rows;meta=j;lastError=rows.length?'':'未串接合法盤中來源，沒有即時訊號';
 }catch(e){rows=[];meta=null;lastError=e.message}finally{active=false;display()}}
$('live106refresh')?.addEventListener('click',refresh);
$('live106sample')?.addEventListener('click',()=>{rows=[{symbol:'TEST01',prev:100,o:103,h:104.2,l:102.8,c:104,pv:10000,v:1500,p:104.5,w:103.5,trend:1,confirm:1,eligible:true,tradingDay:true,firstBarComplete:true,date:tw(new Date()).slice(0,10),time:new Date().toISOString()}];meta={source:'合成示範（不可交易）',generatedAt:new Date().toISOString()};lastError='模擬資料，不構成交易依據';display()});
$('live106clear')?.addEventListener('click',()=>{rows=[];meta=null;lastError='已清除';display()});
refresh();setInterval(refresh,30000);
})();