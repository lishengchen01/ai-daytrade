import json, urllib.request, datetime
sources=[('上市','https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'),('上櫃','https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes')]
def num(x): return float(str(x).replace(',',''))
def parse_date(x):
 s=str(x).replace('/','').replace('-',''); y=int(s[:-4]); return datetime.date(y+1911 if y<1911 else y,int(s[-4:-2]),int(s[-2:])).isoformat()
def pick(r,*ks):
 for k in ks:
  if k in r:return r[k]
 raise KeyError(ks)
def parse(r,m):
 code=str(pick(r,'Code','SecuritiesCompanyCode')); name=pick(r,'Name','CompanyName','SecuritiesCompanyName'); close=num(pick(r,'ClosingPrice','Close')); change=num(pick(r,'Change','ChangePrice')); volume=num(pick(r,'TradeVolume','TradingShares','TradingVolume')); date=parse_date(pick(r,'Date','TradeDate'))
 if len(code)!=4 or not code.isdigit() or close<=0 or close-change<=0 or volume<0:return None
 return dict(symbol=code,name=name,market=m,date=date,close=close,change=change/(close-change)*100,volume=volume/1000)
def main():
 rows=[]; status=[]
 for m,url in sources:
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Daytrade research dashboard'}),timeout=30) as f: data=json.load(f)
   valid=[]
   for r in data:
    try:
     x=parse(r,m)
     if x:valid.append(x)
    except (ValueError,KeyError,TypeError):pass
   if not valid:raise ValueError('無可解析資料，需檢查來源欄位')
   rows+=valid;status.append(dict(market=m,ok=True,count=len(valid),url=url))
  except Exception as e:status.append(dict(market=m,ok=False,error=str(e),url=url))
 with open('quotes.json','w') as f:json.dump(dict(fetched=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=status,rows=rows),f,ensure_ascii=False)
if __name__=='__main__':main()
