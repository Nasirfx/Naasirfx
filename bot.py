import os,asyncio,numpy as np,pandas as pd,requests
from datetime import datetime,timezone
from threading import Thread
from http.server import BaseHTTPRequestHandler,HTTPServer
from telegram import Update,ReplyKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,ContextTypes,filters
from pocketoptionapi_async import AsyncPocketOptionClient

TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")
PO_SSID=os.getenv("PO_SSID") or os.getenv("POCKET_OPTION_SSID")
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")
AI_MODEL="gemini-2.5-flash-lite"
IS_DEMO=True
CONNECT_TIMEOUT=40
CANDLE_TIMEOUT=30
CANDLE_COUNT=100
PORT=int(os.getenv("PORT","10000"))

TIMEFRAMES={
"1️⃣ 1 Minute":60,"3️⃣ 3 Minutes":180,"5️⃣ 5 Minutes":300,
"15️⃣ 15 Minutes":900,"30️⃣ 30 Minutes":1800,"60️⃣ 1 Hour":3600,
"4️⃣ 4 Hours":14400}
HIGHER_TF={60:180,180:300,300:900,900:1800,1800:3600,3600:14400,14400:14400}

FOREX_NAMES={
"🇪🇺 EUR/USD":"EURUSD","🇬🇧 GBP/USD":"GBPUSD","🇯🇵 USD/JPY":"USDJPY",
"🇨🇭 USD/CHF":"USDCHF","🇨🇦 USD/CAD":"USDCAD","🇦🇺 AUD/USD":"AUDUSD",
"🇳🇿 NZD/USD":"NZDUSD","🇪🇺 EUR/GBP":"EURGBP","🇪🇺 EUR/JPY":"EURJPY",
"🇪🇺 EUR/CHF":"EURCHF","🇬🇧 GBP/JPY":"GBPJPY","🇬🇧 GBP/CHF":"GBPCHF",
"🇦🇺 AUD/JPY":"AUDJPY","🇳🇿 NZD/JPY":"NZDJPY","🇨🇦 CAD/JPY":"CADJPY"}

FOREX_OTC_NAMES={
"🇪🇺 EUR/USD OTC":"EURUSD_otc","🇬🇧 GBP/USD OTC":"GBPUSD_otc",
"🇯🇵 USD/JPY OTC":"USDJPY_otc","🇨🇭 USD/CHF OTC":"USDCHF_otc",
"🇨🇦 USD/CAD OTC":"USDCAD_otc","🇦🇺 AUD/USD OTC":"AUDUSD_otc",
"🇳🇿 NZD/USD OTC":"NZDUSD_otc","🇪🇺 EUR/GBP OTC":"EURGBP_otc",
"🇪🇺 EUR/JPY OTC":"EURJPY_otc","🇪🇺 EUR/CHF OTC":"EURCHF_otc",
"🇬🇧 GBP/JPY OTC":"GBPJPY_otc","🇬🇧 GBP/CHF OTC":"GBPCHF_otc",
"🇦🇺 AUD/JPY OTC":"AUDJPY_otc","🇳🇿 NZD/JPY OTC":"NZDJPY_otc",
"🇨🇦 CAD/JPY OTC":"CADJPY_otc","🇷🇺 USD/RUB OTC":"USDRUB_otc"}

CNY_OTC_ASSETS={
"AEDCNY_otc":538,"BHDCNY_otc":536,"JODCNY_otc":546,
"OMRCNY_otc":544,"QARCNY_otc":542,"SARCNY_otc":540}

CNY_OTC_NAMES={
"🇦🇪 AED/CNY OTC":"AEDCNY_otc","🇧🇭 BHD/CNY OTC":"BHDCNY_otc",
"🇯🇴 JOD/CNY OTC":"JODCNY_otc","🇴🇲 OMR/CNY OTC":"OMRCNY_otc",
"🇶🇦 QAR/CNY OTC":"QARCNY_otc","🇸🇦 SAR/CNY OTC":"SARCNY_otc"}

STOCK_NAMES={
"🍎 Apple":"#AAPL","💳 American Express":"#AXP","🍔 McDonald's":"#MCD",
"🟢 Microsoft":"#MSFT","🔵 Meta":"#META","🟠 Amazon":"#AMZN",
"🚗 Tesla":"#TSLA","🟢 NVIDIA":"#NVDA","🔴 Coca-Cola":"#KO",
"💳 Mastercard":"#MA","💳 Visa":"#V","🔵 Google":"#GOOGL",
"🔵 Google (GOOG)":"#GOOG","🎬 Netflix":"#NFLX","🔴 AMD":"#AMD",
"🔵 Intel":"#INTC","🔵 IBM":"#IBM","🔴 Oracle":"#ORCL",
"☁️ Salesforce":"#CRM","🏰 Disney":"#DIS","👟 Nike":"#NKE",
"🥤 PepsiCo":"#PEP","🛒 Walmart":"#WMT","🏦 JPMorgan Chase":"#JPM",
"🏦 Bank of America":"#BAC","🏦 Citigroup":"#C","🏦 Goldman Sachs":"#GS",
"⛽ Exxon Mobil":"#XOM","⛽ Chevron":"#CVX","✈️ Boeing":"#BA",
"💊 Pfizer":"#PFE","💊 Johnson & Johnson":"#JNJ","🌐 Cisco":"#CSCO",
"🎨 Adobe":"#ADBE","📱 Qualcomm":"#QCOM","🚕 Uber":"#UBER",
"💳 PayPal":"#PYPL","🛍 Shopify":"#SHOP","🛒 Alibaba":"#BABA",
"📡 AT&T":"#T","📡 Verizon":"#VZ"}

STOCK_OTC_NAMES={
"🍎 Apple OTC":"#AAPL_otc","💳 American Express OTC":"#AXP_otc",
"🍔 McDonald's OTC":"#MCD_otc","🟢 Microsoft OTC":"#MSFT_otc",
"🔵 Meta OTC":"#META_otc","🟠 Amazon OTC":"#AMZN_otc",
"🚗 Tesla OTC":"#TSLA_otc","🟢 NVIDIA OTC":"#NVDA_otc",
"🔴 Coca-Cola OTC":"#KO_otc","💳 Mastercard OTC":"#MA_otc",
"💳 Visa OTC":"#V_otc","🔵 Google OTC":"#GOOGL_otc",
"🔵 Google (GOOG) OTC":"#GOOG_otc","🎬 Netflix OTC":"#NFLX_otc",
"🔴 AMD OTC":"#AMD_otc","🔵 Intel OTC":"#INTC_otc","🔵 IBM OTC":"#IBM_otc",
"🔴 Oracle OTC":"#ORCL_otc","☁️ Salesforce OTC":"#CRM_otc",
"🏰 Disney OTC":"#DIS_otc","👟 Nike OTC":"#NKE_otc","🥤 PepsiCo OTC":"#PEP_otc",
"🛒 Walmart OTC":"#WMT_otc","🏦 JPMorgan Chase OTC":"#JPM_otc",
"🏦 Bank of America OTC":"#BAC_otc","🏦 Citigroup OTC":"#C_otc",
"🏦 Goldman Sachs OTC":"#GS_otc","⛽ Exxon Mobil OTC":"#XOM_otc",
"⛽ Chevron OTC":"#CVX_otc","✈️ Boeing OTC":"#BA_otc","💊 Pfizer OTC":"#PFE_otc",
"💊 Johnson & Johnson OTC":"#JNJ_otc","🌐 Cisco OTC":"#CSCO_otc",
"🎨 Adobe OTC":"#ADBE_otc","📱 Qualcomm OTC":"#QCOM_otc","🚕 Uber OTC":"#UBER_otc",
"💳 PayPal OTC":"#PYPL_otc","🛍 Shopify OTC":"#SHOP_otc","🛒 Alibaba OTC":"#BABA_otc",
"📡 AT&T OTC":"#T_otc","📡 Verizon OTC":"#VZ_otc"}

ALL_PAIRS={}
for x in (FOREX_NAMES,FOREX_OTC_NAMES,CNY_OTC_NAMES,STOCK_NAMES,STOCK_OTC_NAMES): ALL_PAIRS.update(x)

client=None
selected_timeframe=60
selected_expiry=180

async def connect_client():
    if not PO_SSID: raise RuntimeError("POCKET_OPTION_SSID / PO_SSID lama helin.")
    print("🔵 PO CONNECT: bilaabatay...",flush=True)
    print(f"🔵 PO CONNECT: SSID length={len(PO_SSID)}",flush=True)
    c=AsyncPocketOptionClient(PO_SSID,is_demo=True,enable_logging=True)
    try:
        await asyncio.wait_for(c.connect(),timeout=CONNECT_TIMEOUT)
        print("🟢 PO CONNECT: SUCCESS",flush=True)
        return c
    except asyncio.TimeoutError:
        try: await c.disconnect()
        except: pass
        raise RuntimeError(f"Pocket Option connection timeout ({CONNECT_TIMEOUT}s).")
    except Exception:
        try: await c.disconnect()
        except: pass
        raise

def get_asset_variants(asset_code):
    original=str(asset_code).strip()
    variants=[]
    def add(x):
        if x and x not in variants: variants.append(x)
    add(original);add(original.replace("/",""))
    if original.lower().endswith("_otc"):
        base=original[:-4]
        add(base+"_otc");add(base.upper()+"_otc");add(base.upper()+"-OTC")
        add(base.upper()+" OTC");add(base.upper()+"_OTC")
        if base.startswith("#"):
            clean=base[1:]
            add("#"+clean+"_otc");add(clean+"_otc")
            add("#"+clean.upper()+"_otc");add(clean.upper()+"_otc")
    else:
        add(original+"_otc");add(original.replace("/","")+"_otc")
    return variants

async def discover_asset_variants_by_id(client,asset_code):
    asset_id=CNY_OTC_ASSETS.get(asset_code)
    if asset_id is None:return []
    method=getattr(client,"get_assets",None)
    if not callable(method):return []
    try: assets=await asyncio.wait_for(method(),timeout=10)
    except Exception as e:
        print(f"🟡 ASSET DISCOVERY ERROR {asset_code}: {e}",flush=True);return []
    found=[]
    def add(v):
        if v is not None:
            v=str(v).strip()
            if v and v not in found:found.append(v)
    def same_id(v):
        if v is None:return False
        try:return int(v)==int(asset_id)
        except:return str(v).strip()==str(asset_id)
    id_keys=("id","asset_id","active_id","activeId","symbol_id")
    name_keys=("symbol","asset","name","ticker","code","pair")
    if isinstance(assets,dict):
        for key,value in assets.items():
            if same_id(key):
                if isinstance(value,dict):
                    for k in name_keys:add(value.get(k))
                else:add(value)
            if same_id(value):add(key)
            if isinstance(value,dict) and any(same_id(value.get(k)) for k in id_keys):
                for k in name_keys:add(value.get(k))
        candidates=list(assets.values())
    elif isinstance(assets,(list,tuple,set)):candidates=list(assets)
    else:candidates=[assets]
    for item in candidates:
        if isinstance(item,dict):
            if any(same_id(item.get(k)) for k in id_keys):
                for k in name_keys:add(item.get(k))
        else:
            ids=[]
            for k in id_keys:
                try:ids.append(getattr(item,k,None))
                except:pass
            if any(same_id(v) for v in ids):
                for k in name_keys:
                    try:add(getattr(item,k,None))
                    except:pass
    if found:print(f"🟢 ASSET DISCOVERY {asset_code}: {found}",flush=True)
    return found

def normalize_dataframe(df):
    if df is None:return None
    if not isinstance(df,pd.DataFrame):
        try:df=pd.DataFrame(df)
        except:return None
    if df.empty:return None
    df=df.copy();rename={}
    for col in df.columns:
        low=str(col).lower()
        if low in ("open","o"):rename[col]="open"
        elif low in ("high","h"):rename[col]="high"
        elif low in ("low","l"):rename[col]="low"
        elif low in ("close","c","price"):rename[col]="close"
        elif low in ("volume","vol","v"):rename[col]="volume"
        elif low in ("time","timestamp","timestamp_ms","at"):rename[col]="time"
    df=df.rename(columns=rename)
    for col in ("open","high","low","close"):
        if col not in df.columns:return None
        df[col]=pd.to_numeric(df[col],errors="coerce")
    df=df.dropna(subset=["open","high","low","close"])
    if "time" in df.columns:
        try:df["time"]=pd.to_datetime(df["time"],errors="coerce",utc=True)
        except:pass
    return df.sort_index()

async def get_candles(client,asset_code,timeframe,count=CANDLE_COUNT):
    variants=get_asset_variants(asset_code)
    if asset_code in CNY_OTC_ASSETS:
        discovered=await discover_asset_variants_by_id(client,asset_code)
        for x in discovered:
            if x not in variants:variants.append(x)
    print(f"🔵 CANDLE SEARCH {asset_code}: {variants}",flush=True)
    now_utc=datetime.now(timezone.utc)

    method=getattr(client,"get_candles",None)
    if callable(method):
        for variant in variants:
            try:
                try:raw=await asyncio.wait_for(method(variant,timeframe,count,now_utc),timeout=CANDLE_TIMEOUT)
                except TypeError:raw=await asyncio.wait_for(method(variant,timeframe,count),timeout=CANDLE_TIMEOUT)
                if raw is None:continue
                if isinstance(raw,pd.DataFrame):df=raw.copy()
                elif isinstance(raw,(list,tuple)):df=pd.DataFrame(raw)
                elif isinstance(raw,dict):
                    if "data" in raw:df=pd.DataFrame(raw["data"])
                    elif "candles" in raw:df=pd.DataFrame(raw["candles"])
                    else:df=pd.DataFrame(raw)
                else:continue
                df=normalize_dataframe(df)
                if df is not None and len(df)>=55:
                    print(f"🟢 CANDLES OK {asset_code} via raw: {variant} count={len(df)}",flush=True)
                    return df
            except Exception as e:
                print(f"🟡 RAW CANDLE FAIL {asset_code} / {variant}: {e}",flush=True)

    method_df=getattr(client,"get_candles_dataframe",None)
    if callable(method_df):
        for variant in variants:
            try:
                try:df=await asyncio.wait_for(method_df(variant,timeframe,count,now_utc),timeout=CANDLE_TIMEOUT)
                except TypeError:df=await asyncio.wait_for(method_df(variant,timeframe,count),timeout=CANDLE_TIMEOUT)
                df=normalize_dataframe(df)
                if df is not None and len(df)>=55:
                    print(f"🟢 CANDLES OK {asset_code} via dataframe: {variant} count={len(df)}",flush=True)
                    return df
            except Exception as e:
                print(f"🟡 DF CANDLE FAIL {asset_code} / {variant}: {e}",flush=True)
    print(f"🔴 ALL CANDLE METHODS FAILED: {asset_code}",flush=True)
    return None

def calculate_rsi(series,period=14):
    delta=series.diff()
    gain=delta.clip(lower=0)
    loss=-delta.clip(upper=0)
    avg_gain=gain.rolling(period).mean()
    avg_loss=loss.rolling(period).mean()
    rs=avg_gain/avg_loss.replace(0,np.nan)
    return 100-(100/(1+rs))

def analyze_dataframe(df,higher_df=None):
    if df is None or len(df)<55:return None
    df=df.copy()
    df["ma10"]=df["close"].rolling(10).mean()
    df["ma50"]=df["close"].rolling(50).mean()
    df["rsi"]=calculate_rsi(df["close"])
    current=df.iloc[-1];previous=df.iloc[-2]
    price=float(current["close"]);ma10=float(current["ma10"]);ma50=float(current["ma50"]);rsi=float(current["rsi"])

    trend="CALL" if price>ma10>ma50 else "PUT" if price<ma10<ma50 else "NEUTRAL"
    rsi_direction="CALL" if 50<=rsi<=70 else "PUT" if 30<=rsi<50 else "NEUTRAL"
    current_direction="CALL" if current["close"]>current["open"] else "PUT" if current["close"]<current["open"] else "NEUTRAL"
    previous_direction="CALL" if previous["close"]>previous["open"] else "PUT" if previous["close"]<previous["open"] else "NEUTRAL"
    higher_direction="NEUTRAL"

    if higher_df is not None and len(higher_df)>=55:
        h=higher_df.copy()
        h["ma10"]=h["close"].rolling(10).mean()
        h["ma50"]=h["close"].rolling(50).mean()
        hc=h.iloc[-1]
        if hc["close"]>hc["ma10"]>hc["ma50"]:higher_direction="CALL"
        elif hc["close"]<hc["ma10"]<hc["ma50"]:higher_direction="PUT"

    directions=[trend,rsi_direction,current_direction,previous_direction,higher_direction]
    call_count=directions.count("CALL");put_count=directions.count("PUT")
    technical_direction="CALL" if call_count>put_count else "PUT" if put_count>call_count else "WAIT"
    return {"price":price,"ma10":ma10,"ma50":ma50,"rsi":rsi,"trend":trend,
            "rsi_direction":rsi_direction,"current_direction":current_direction,
            "previous_direction":previous_direction,"higher_direction":higher_direction,
            "call_count":call_count,"put_count":put_count,
            "technical_direction":technical_direction,
            "technical_count":max(call_count,put_count)}

def sr_filter(df):
    if df is None or len(df)<20:return False
    p=float(df.iloc[-1]["close"])
    hi=float(df["high"].iloc[-20:].max());lo=float(df["low"].iloc[-20:].min())
    total=hi-lo
    if total<=0:return True
    dh=hi-p;dl=p-lo
    if dh/total<0.03 and dl/total>0.50:return False
    if dl/total<0.03 and dh/total>0.50:return False
    return True

def calculate_accuracy(call_count,put_count):
    return {5:90,4:80,3:60,2:40,1:20,0:0}.get(max(call_count,put_count),0)

def ask_gemini(technical_direction,call_count,put_count,price,ma10,ma50,rsi):
    if not GEMINI_API_KEY:return "WAIT"
    prompt=f"""Technical direction: {technical_direction}
CALL confirmations: {call_count}/5
PUT confirmations: {put_count}/5
Price: {price}
MA10: {ma10}
MA50: {ma50}
RSI: {rsi}
Return ONLY one word: BUY, SELL, or WAIT."""
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{AI_MODEL}:generateContent"
    try:
        response=requests.post(url,params={"key":GEMINI_API_KEY},
            json={"contents":[{"parts":[{"text":prompt}]}]},timeout=15)
        if response.status_code!=200:return "WAIT"
        text=response.json()["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
        if "BUY" in text:return "BUY"
        if "SELL" in text:return "SELL"
        return "WAIT"
    except Exception as e:
        print("🟡 GEMINI ERROR:",repr(e),flush=True);return "WAIT"

def direction_text(v):
    return "CALL 🟢" if v=="CALL" else "PUT 🔴" if v=="PUT" else "WAIT ⚪"

def timeframe_label(seconds):
    for label,value in TIMEFRAMES.items():
        if value==seconds:return label
    return "1️⃣ 1 Minute"

def expiry_label(seconds):
    return {60:"⌛ 1 Minute",180:"⌛ 3 Minutes",300:"⌛ 5 Minutes",
            900:"⌛ 15 Minutes",1800:"⌛ 30 Minutes",3600:"⌛ 1 Hour",
            14400:"⌛ 4 Hours"}.get(seconds,"⌛ 3 Minutes")

async def generate_signal(display_name,asset_code,timeframe,expiry):
    global client
    if client is None:client=await connect_client()
    df=await get_candles(client,asset_code,timeframe,CANDLE_COUNT)

    if df is None:
        return ("━━━━━━━━━━━━━━━━━━━━\n🤖 NAASIRFX AI SIGNAL\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {display_name}\n\n⚪ FINAL: WAIT\n\n❌ DATA LAMA HELIN\n\n"
                "Candles ku filan lama helin.\n\n"
                f"⏱ Timeframe: {timeframe_label(timeframe)}\n"
                f"⌛ Expiry: {expiry_label(expiry)}\n\n⚠️ SIGNAL ONLY\n━━━━━━━━━━━━━━━━━━━━")

    higher_seconds=HIGHER_TF.get(timeframe,timeframe)
    higher_df=df if higher_seconds==timeframe else await get_candles(client,asset_code,higher_seconds,CANDLE_COUNT)
    a=analyze_dataframe(df,higher_df)

    if a is None:
        return ("━━━━━━━━━━━━━━━━━━━━\n🤖 NAASIRFX AI SIGNAL\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {display_name}\n\n⚪ FINAL: WAIT\n\n❌ DATA LAMA HELIN\n\n"
                "Candles ku filan lama helin.\n\n"
                f"⏱ Timeframe: {timeframe_label(timeframe)}\n"
                f"⌛ Expiry: {expiry_label(expiry)}\n\n⚠️ SIGNAL ONLY\n━━━━━━━━━━━━━━━━━━━━")

    cc=a["call_count"];pc=a["put_count"];td=a["technical_direction"]
    sr=sr_filter(df);accuracy=calculate_accuracy(cc,pc)

    ai=await asyncio.to_thread(ask_gemini,td,cc,pc,a["price"],a["ma10"],a["ma50"],a["rsi"])

    final_signal="BUY" if td=="CALL" and cc>=4 and sr else "SELL" if td=="PUT" and pc>=4 and sr else "WAIT"
    emoji="🟢" if final_signal=="BUY" else "🔴" if final_signal=="SELL" else "⚪"
    tech=f"CALL {max(cc,pc)}/5" if td=="CALL" else f"PUT {max(cc,pc)}/5" if td=="PUT" else f"WAIT {max(cc,pc)}/5"
    sr_text="PASS ✅" if sr else "BLOCK ❌"
    ai_emoji="🟢" if ai=="BUY" else "🔴" if ai=="SELL" else "⚪"

    return (f"━━━━━━━━━━━━━━━━━━━━\n🤖 NAASIRFX AI SIGNAL\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💱 {display_name}\n\n{emoji} FINAL: {final_signal}\n"
            f"📊 Technical: {tech}\n🎯 Accuracy: {accuracy}%\n\n"
            f"⏱ Timeframe: {timeframe_label(timeframe)}\n⌛ Expiry: {expiry_label(expiry)}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n📊 TECHNICAL ANALYSIS\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 Trend:       {direction_text(a['trend'])}\n"
            f"📊 RSI:         {direction_text(a['rsi_direction'])}\n"
            f"🕯 Current:     {direction_text(a['current_direction'])}\n"
            f"🕯 Previous:    {direction_text(a['previous_direction'])}\n"
            f"⏫ Higher TF:   {direction_text(a['higher_direction'])}\n\n"
            f"🟢 CALL: {cc}/5\n🔴 PUT: {pc}/5\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n📐 MARKET DATA\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Price: {a['price']:.5f}\n📈 MA10:  {a['ma10']:.5f}\n"
            f"📉 MA50:  {a['ma50']:.5f}\n📊 RSI:   {a['rsi']:.2f}\n\n"
            f"🛡 S/R: {sr_text}\n\n━━━━━━━━━━━━━━━━━━━━\n🤖 GEMINI AI\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"AI: {ai} {ai_emoji}\n\n━━━━━━━━━━━━━━━━━━━━\n🎯 FINAL SIGNAL\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} {final_signal}\n\n⚠️ SIGNAL ONLY\n━━━━━━━━━━━━━━━━━━━━")

def main_keyboard():
    return ReplyKeyboardMarkup([["📋 PAIRS"],["⏱ TIMEFRAME","⌛ EXPIRY"],["ℹ️ STATUS"]],resize_keyboard=True)

def pairs_keyboard():
    return ReplyKeyboardMarkup([["💱 Forex","💱 Forex OTC"],["📈 Stocks","📈 Stocks OTC"],["💱 CNY OTC"],["🔙 Back"]],resize_keyboard=True)

def list_keyboard(mapping):
    b=list(mapping.keys());rows=[b[i:i+2] for i in range(0,len(b),2)];rows.append(["🔙 Back"])
    return ReplyKeyboardMarkup(rows,resize_keyboard=True)

def timeframe_keyboard():
    return ReplyKeyboardMarkup([["1️⃣ 1 Minute","3️⃣ 3 Minutes"],["5️⃣ 5 Minutes","15️⃣ 15 Minutes"],
    ["30️⃣ 30 Minutes","60️⃣ 1 Hour"],["4️⃣ 4 Hours"],["🔙 Back"]],resize_keyboard=True)

def expiry_keyboard():
    return ReplyKeyboardMarkup([["⌛ 1 Minute","⌛ 3 Minutes"],["⌛ 5 Minutes","⌛ 15 Minutes"],
    ["⌛ 30 Minutes","⌛ 1 Hour"],["⌛ 4 Hours"],["🔙 Back"]],resize_keyboard=True)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 NAASIRFX AI SIGNAL\n\nBot-ka wuu shaqeynayaa!",reply_markup=main_keyboard())

async def handle_message(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global selected_timeframe,selected_expiry,client
    text=update.message.text if update.message else ""

    if text=="📋 PAIRS":
        await update.message.reply_text("📋 PAIRS",reply_markup=pairs_keyboard());return
    if text=="⏱ TIMEFRAME":
        await update.message.reply_text("⏱ TIMEFRAME",reply_markup=timeframe_keyboard());return
    if text=="⌛ EXPIRY":
        await update.message.reply_text("⌛ EXPIRY",reply_markup=expiry_keyboard());return
    if text=="ℹ️ STATUS":
        await update.message.reply_text(f"ℹ️ STATUS\n\n{'🟢 CONNECTED' if client is not None else '🟡 NOT CONNECTED'}",reply_markup=main_keyboard());return
    if text=="🔙 Back":
        await update.message.reply_text("🏠 MENU",reply_markup=main_keyboard());return
    if text in TIMEFRAMES:
        selected_timeframe=TIMEFRAMES[text]
        await update.message.reply_text(f"⏱ Timeframe: {text}\n\nTimeframe waa la doortay.",reply_markup=timeframe_keyboard());return

    expiry_map={"⌛ 1 Minute":60,"⌛ 3 Minutes":180,"⌛ 5 Minutes":300,"⌛ 15 Minutes":900,
                "⌛ 30 Minutes":1800,"⌛ 1 Hour":3600,"⌛ 4 Hours":14400}
    if text in expiry_map:
        selected_expiry=expiry_map[text]
        await update.message.reply_text(f"⌛ Expiry: {text}\n\nExpiry waa la doortay.",reply_markup=expiry_keyboard());return

    categories={
        "💱 Forex":FOREX_NAMES,"💱 Forex OTC":FOREX_OTC_NAMES,
        "💱 CNY OTC":CNY_OTC_NAMES,"📈 Stocks":STOCK_NAMES,"📈 Stocks OTC":STOCK_OTC_NAMES}
    if text in categories:
        await update.message.reply_text(text,reply_markup=list_keyboard(categories[text]));return

    if text in ALL_PAIRS:
        await update.message.reply_text("⏳ Signal-ka waa la baarayaa...")
        try:
            signal=await generate_signal(text,ALL_PAIRS[text],selected_timeframe,selected_expiry)
            await update.message.reply_text(signal,reply_markup=main_keyboard())
        except Exception as e:
            print("🔴 SIGNAL ERROR:",repr(e),flush=True)
            await update.message.reply_text(
                "━━━━━━━━━━━━━━━━━━━━\n🤖 NAASIRFX AI SIGNAL\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {text}\n\n⚪ FINAL: WAIT\n\n❌ DATA LAMA HELIN\n\nCandles ku filan lama helin.\n\n"
                f"⏱ Timeframe: {timeframe_label(selected_timeframe)}\n"
                f"⌛ Expiry: {expiry_label(selected_expiry)}\n\n⚠️ SIGNAL ONLY\n━━━━━━━━━━━━━━━━━━━━",
                reply_markup=main_keyboard())

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header("Content-Type","text/plain");self.end_headers();self.wfile.write(b"NAASIRFX AI SIGNAL OK")
    def log_message(self,format,*args):return

def run_health_server():
    server=HTTPServer(("0.0.0.0",PORT),HealthHandler)
    print(f"🟢 HTTP SERVER: 0.0.0.0:{PORT}",flush=True)
    server.serve_forever()

async def main():
    global client
    if not TELEGRAM_BOT_TOKEN:raise RuntimeError("TELEGRAM_BOT_TOKEN lama helin.")
    print("🟢 NAASIRFX: starting...",flush=True)
    Thread(target=run_health_server,daemon=True).start()
    try:client=await connect_client()
    except Exception as e:
        print("🟡 PO INITIAL CONNECT FAILED:",repr(e),flush=True);client=None

    app=Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    print("🟢 TELEGRAM POLLING: STARTED",flush=True)
    await app.initialize();await app.start();await app.updater.start_polling(drop_pending_updates=True)
    try:
        while True:await asyncio.sleep(3600)
    finally:
        await app.updater.stop();await app.stop();await app.shutdown()
        if client:
            try:await client.disconnect()
            except:pass

if __name__=="__main__":
    asyncio.run(main())                        
