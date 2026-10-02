import os
import time
import asyncio
import json
import pandas as pd
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

from pocketoptionapi_async import AsyncPocketOptionClient
from pocketoptionapi_async.constants import ASSETS as PO_ASSETS

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PO_SSID = os.getenv("PO_SSID")

CONNECT_TIMEOUT = 45
CONNECT_RETRIES = 3


def detect_demo_mode(ssid):
    try:
        if isinstance(ssid, str) and ssid.startswith("42["):
            payload = json.loads(ssid[2:])
            if isinstance(payload, list) and len(payload) >= 2:
                auth = payload[1]
                if isinstance(auth, dict) and "isDemo" in auth:
                    return bool(auth.get("isDemo"))
    except Exception:
        pass
    return True


async def connect_client():
    if not PO_SSID:
        raise RuntimeError("PO_SSID lama helin.")

    demo_mode = detect_demo_mode(PO_SSID)
    print(f"🔵 PO CONNECT: SSID waa jiraa (length={len(PO_SSID)})", flush=True)
    print(f"🔵 PO AUTH: SSID isDemo={demo_mode}", flush=True)
    print("🔵 PO CONNECT: persistent_connection=False", flush=True)

    last_error = None
    last_result = None

    for attempt in range(1, CONNECT_RETRIES + 1):
        client = None
        try:
            client = AsyncPocketOptionClient(
                PO_SSID,
                is_demo=demo_mode,
                persistent_connection=False,
                auto_reconnect=False,
                enable_logging=True,
            )
            print(f"🔵 PO CONNECT: attempt {attempt}/{CONNECT_RETRIES}...", flush=True)
            result = await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
            last_result = result
            print(f"🟢 PO CONNECT: connect() returned: {result!r}", flush=True)

            if result is True:
                print("🟢 PO CONNECT: connection READY.", flush=True)
                return client

            stats_method = getattr(client, "get_connection_stats", None)
            if callable(stats_method):
                try:
                    stats = await stats_method()
                    print(f"🔵 PO CONNECT STATS: {stats}", flush=True)
                    if stats.get("websocket_connected") or stats.get("connected"):
                        return client
                except Exception as stats_error:
                    print(f"🟡 PO CONNECT STATS ERROR: {stats_error}", flush=True)

            raise RuntimeError(f"connect() returned {result!r}")

        except asyncio.TimeoutError:
            last_error = f"connection timeout after {CONNECT_TIMEOUT}s"
            print(f"🔴 PO CONNECT TIMEOUT: {last_error}", flush=True)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"🔴 PO CONNECT ERROR: {last_error}", flush=True)
        finally:
            if client is not None and last_result is not True:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        if attempt < CONNECT_RETRIES:
            await asyncio.sleep(3)

    raise RuntimeError(
        f"Pocket Option connection failed after {CONNECT_RETRIES} attempts. "
        f"Last result={last_result!r}; last error={last_error}"
    )


# =========================================================
# TIMEFRAMES
# =========================================================

TIMEFRAMES = {
    "1️⃣ 1 Minute": 60,
    "3️⃣ 3 Minutes": 180,
    "5️⃣ 5 Minutes": 300,
    "15️⃣ 15 Minutes": 900,
    "30️⃣ 30 Minutes": 1800,
    "1️⃣ 1 Hour": 3600,
    "4️⃣ 4 Hours": 14400,
}


EXPIRIES = {
    "⌛ 1 Minute": 60,
    "⌛ 2 Minutes": 120,
    "⌛ 3 Minutes": 180,
    "⌛ 5 Minutes": 300,
    "⌛ 10 Minutes": 600,
    "⌛ 15 Minutes": 900,
    "⌛ 30 Minutes": 1800,
    "⌛ 1 Hour": 3600,
}


# =========================================================
# STATIC ASSETS
# =========================================================

ASSETS = {

    # -----------------------------------------------------
    # FOREX
    # -----------------------------------------------------

    "💱 Forex": {
        "EUR/USD": "EURUSD",
        "GBP/USD": "GBPUSD",
        "USD/JPY": "USDJPY",
        "USD/CHF": "USDCHF",
        "USD/CAD": "USDCAD",
        "AUD/USD": "AUDUSD",
        "NZD/USD": "NZDUSD",
        "EUR/GBP": "EURGBP",
        "EUR/JPY": "EURJPY",
        "EUR/CHF": "EURCHF",
        "EUR/AUD": "EURAUD",
        "EUR/CAD": "EURCAD",
        "EUR/NZD": "EURNZD",
        "GBP/JPY": "GBPJPY",
        "GBP/CHF": "GBPCHF",
        "GBP/CAD": "GBPCAD",
        "GBP/AUD": "GBPAUD",
        "AUD/JPY": "AUDJPY",
        "AUD/CAD": "AUDCAD",
        "AUD/CHF": "AUDCHF",
        "AUD/NZD": "AUDNZD",
        "CAD/JPY": "CADJPY",
        "CAD/CHF": "CADCHF",
        "CHF/JPY": "CHFJPY",
    },
    # -----------------------------------------------------
    # FOREX OTC
    # -----------------------------------------------------

    "💱 Forex OTC": {
        "EUR/USD OTC": "EURUSD_otc",
        "GBP/USD OTC": "GBPUSD_otc",
        "USD/JPY OTC": "USDJPY_otc",
        "USD/CHF OTC": "USDCHF_otc",
        "USD/CAD OTC": "USDCAD_otc",
        "AUD/USD OTC": "AUDUSD_otc",
        "NZD/USD OTC": "NZDUSD_otc",
        "EUR/GBP OTC": "EURGBP_otc",
        "EUR/JPY OTC": "EURJPY_otc",
        "EUR/CHF OTC": "EURCHF_otc",
        "EUR/NZD OTC": "EURNZD_otc",
        "EUR/TRY OTC": "EURTRY_otc",
        "EUR/HUF OTC": "EURHUF_otc",
        "EUR/RUB OTC": "EURRUB_otc",
        "GBP/JPY OTC": "GBPJPY_otc",
        "GBP/AUD OTC": "GBPAUD_otc",
        "AUD/JPY OTC": "AUDJPY_otc",
        "AUD/CAD OTC": "AUDCAD_otc",
        "AUD/CHF OTC": "AUDCHF_otc",
        "AUD/NZD OTC": "AUDNZD_otc",
        "CAD/JPY OTC": "CADJPY_otc",
        "CAD/CHF OTC": "CADCHF_otc",
        "CHF/JPY OTC": "CHFJPY_otc",
        "CHF/NOK OTC": "CHFNOK_otc",
        "USD/INR OTC": "USDINR_otc",
        "USD/PHP OTC": "USDPHP_otc",
        "USD/DZD OTC": "USDDZD_otc",
        "USD/BDT OTC": "USDBDT_otc",
        "USD/EGP OTC": "USDEGP_otc",
        "USD/CNH OTC": "USDCNH_otc",
        "USD/RUB OTC": "USDRUB_otc",
        "USD/MXN OTC": "USDMXN_otc",
        "USD/BRL OTC": "USDBRL_otc",
        "USD/ARS OTC": "USDARS_otc",
        "USD/COP OTC": "USDCOP_otc",
        "USD/CLP OTC": "USDCLP_otc",
        "USD/PKR OTC": "USDPKR_otc",
        "USD/THB OTC": "USDTHB_otc",
        "USD/VND OTC": "USDVND_otc",
        "USD/IDR OTC": "USDIDR_otc",
        "USD/MYR OTC": "USDMYR_otc",
        "USD/SGD OTC": "USDSGD_otc",
        "NGN/USD OTC": "NGNUSD_otc",
        "AUH/USD OTC": "AUHUSD_otc",
        "ZAR/USD OTC": "ZARUSD_otc",
        "KES/USD OTC": "KESUSD_otc",
        "YER/USD OTC": "YERUSD_otc",
        "TND/USD OTC": "TNDUSD_otc",
        "MAD/USD OTC": "MADUSD_otc",
        "UAH/USD OTC": "UAHUSD_otc",
        "AED/CNY OTC": "AEDCNY_otc",
        "BHD/CNY OTC": "BHDCNY_otc",
        "JOD/CNY OTC": "JODCNY_otc",
        "OMR/CNY OTC": "OMRCNY_otc",
        "QAR/CNY OTC": "QARCNY_otc",
        "SAR/CNY OTC": "SARCNY_otc",
    },

    # -----------------------------------------------------
    # COMMODITIES
    # -----------------------------------------------------

    "🥇 Commodities": {
        "Gold OTC": "gold_otc",
        "Silver OTC": "silver_otc",
        "Brent Oil OTC": "brent_oil_otc",
        "WTI Crude Oil OTC": "wti_crude_oil_otc",
        "Natural Gas OTC": "natural_gas_otc",
        "Platinum spot OTC": "platinum_otc",
        "Palladium spot OTC": "palladium_otc",
    },
     # -----------------------------------------------------
    # STOCKS
    #
    # IMPORTANT:
    # Stocks are NOT hardcoded here.
    # They are loaded dynamically from Pocket Option.
    # -----------------------------------------------------

    "📈 Stocks": {},

    # -----------------------------------------------------
    # CRYPTO
    # -----------------------------------------------------

    "🪙 Crypto": {
        "Bitcoin": "BTCUSD",
        "Ethereum": "ETHUSD",
        "Dash": "DASHUSD",
        "Chainlink": "LINKUSD",
        "Bitcoin / GBP": "BTCGBP",
        "Bitcoin / JPY": "BTCJPY",
        "BCH / EUR": "BCHEUR",
        "BCH / GBP": "BCHGBP",
        "BCH / JPY": "BCHJPY",
        "Bitcoin OTC": "BTCUSD_otc",
        "Ethereum OTC": "ETHUSD_otc",
        "Solana OTC": "SOLUSD_otc",
        "Dogecoin OTC": "DOGEUSD_otc",
        "Cardano OTC": "ADAUSD_otc",
        "BNB OTC": "BNBUSD_otc",
        "TRON OTC": "TRXUSD_otc",
        "Avalanche OTC": "AVAXUSD_otc",
        "Litecoin OTC": "LTCUSD_otc",
        "Polygon OTC": "MATICUSD_otc",
        "Polkadot OTC": "DOTUSD_otc",
        "Chainlink OTC": "LINKUSD_otc",
        "Toncoin OTC": "TONUSD_otc",
        "Bitcoin ETF OTC": "BTCETF_otc",
    },

    # -----------------------------------------------------
    # INDICES
    # -----------------------------------------------------

    "📊 Indices": {
        "US100": "US100",
        "US100 OTC": "US100_otc",
        "SP500": "SP500",
        "SP500 OTC": "SP500_otc",
        "DJI30": "DJI30",
        "DJI30 OTC": "DJI30_otc",
        "JPN225": "JPN225",
        "JPN225 OTC": "JPN225_otc",
        "D30/EUR": "D30EUR",
        "D30EUR OTC": "D30EUR_otc",
        "E50/EUR": "E50EUR",
        "E50EUR OTC": "E50EUR_otc",
        "F40EUR OTC": "F40EUR_otc",
        "E35EUR OTC": "E35EUR_otc",
        "AUS 200": "AUS200",
        "AUS 200 OTC": "AUS200_otc",
        "100GBP": "100GBP",
        "100GBP OTC": "100GBP_otc",
        "CAC 40": "CAC40",
        "HONG KONG 33": "HK33",
    },
}
# =========================================================
# STOCK ASSETS
# =========================================================

STOCK_ASSETS = {}
STOCK_META = {}

def load_stock_assets():
    stocks = {}
    for symbol in PO_ASSETS:
        symbol = str(symbol)
        if not symbol.startswith("#"):
            continue
        label = symbol[1:]
        if label.lower().endswith("_otc"):
            label = label[:-4] + " OTC"
        stocks[label] = symbol
    return stocks

STOCK_ASSETS = load_stock_assets()

# =========================================================
# CNY OTC ASSET IDS
# These are internal fallbacks only. The Telegram names/buttons
# and the rest of the bot are unchanged.
# =========================================================
CNY_OTC_ASSET_IDS = {
    "AEDCNY_otc": 538,
    "BHDCNY_otc": 536,
    "JODCNY_otc": 546,
    "OMRCNY_otc": 544,
    "QARCNY_otc": 542,
    "SARCNY_otc": 540,
}



# =========================================================
# GET SIGNAL
# =========================================================

async def _get_candles_with_fallback(client, asset_code, timeframe):
    """Fetch enough candles for the selected asset without changing its
    visible Telegram name.  The requested symbol is tried first, then the
    live Pocket Option asset catalog is used to find the exact server symbol.
    """
    requested = str(asset_code).strip()
    candidates = []

    def add(value):
        if value is None:
            return
        value = str(value).strip()
        if value and value not in candidates:
            candidates.append(value)

    def norm(value):
        return ''.join(ch for ch in str(value).upper() if ch.isalnum())

    base = requested[:-4] if requested.lower().endswith('_otc') else requested
    base = base.replace('/', '').replace(' ', '').replace('-', '')
    target = norm(base)

    # Always try the exact code first.
    add(requested)
    add(base + '_otc')
    add(base.upper() + '_otc')
    add(base + '_OTC')

    # CNY OTC: keep every CNY pair and try all common server spellings.
    # Numeric asset IDs are handled separately below; they are never shown
    # to the user and do not replace the normal symbol.
    if target.endswith('CNY'):
        add(target + '_otc')
        add(target + '_OTC')
        add(target)

    # The user-facing AUH/USD name stays unchanged.  Some PO catalogs use
    # UAHUSD for the same currency pair; use it only as an internal fallback.
    if target == 'AUHUSD':
        add('UAHUSD_otc')
        add('UAHUSD_OTC')

    # -----------------------------------------------------
    # LIVE ASSET CATALOG
    # -----------------------------------------------------
    get_assets = getattr(client, 'get_assets', None)
    if callable(get_assets):
        try:
            live = await get_assets()
            items = live.items() if isinstance(live, dict) else []

            for key, value in items:
                records = [key]
                if isinstance(value, dict):
                    for field in (
                        'symbol', 'asset', 'name', 'ticker', 'id',
                        'active', 'active_id', 'code'
                    ):
                        if value.get(field) is not None:
                            records.append(value.get(field))
                elif value is not None:
                    records.append(value)

                for record in records:
                    text_value = str(record).strip()
                    clean = norm(text_value)
                    # Accept the exact pair and common OTC suffix variants.
                    if clean in {target, target + 'OTC'}:
                        add(text_value)
                        if not text_value.lower().endswith('_otc') and 'OTC' in text_value.upper():
                            add(text_value)

            print(
                f"🔵 ASSET LOOKUP: {requested} -> candidates={candidates}",
                flush=True,
            )
        except Exception as e:
            print(
                f"🟡 ASSET CATALOG WARNING [{requested}]: "
                f"{type(e).__name__}: {e}",
                flush=True,
            )

    last_error = None

    # -----------------------------------------------------
    # CANDLE FETCHERS
    # -----------------------------------------------------
    for candidate in candidates:

        # 1) Raw get_candles is the most direct API method.
        get_candles = getattr(client, 'get_candles', None)
        if callable(get_candles):
            for args in (
                (candidate, timeframe, 120),
                (candidate, timeframe, 100),
                (candidate, timeframe),
            ):
                try:
                    raw = await get_candles(*args)
                    if raw is None:
                        continue

                    if isinstance(raw, pd.DataFrame):
                        df = raw.copy()
                    elif isinstance(raw, dict):
                        # Some releases return {timestamp: candle}.
                        values = list(raw.values())
                        df = pd.DataFrame(values)
                    else:
                        rows = []
                        for candle in list(raw):
                            if isinstance(candle, dict):
                                rows.append(dict(candle))
                            else:
                                row = {}
                                for field in (
                                    'timestamp', 'time', 'open', 'high',
                                    'low', 'close', 'volume'
                                ):
                                    if hasattr(candle, field):
                                        row[field] = getattr(candle, field)
                                if row:
                                    rows.append(row)
                        df = pd.DataFrame(rows)

                    if df is not None and len(df) > 0:
                        if 'time' in df.columns and 'timestamp' not in df.columns:
                            df = df.rename(columns={'time': 'timestamp'})

                        if {'open', 'close'}.issubset(df.columns):
                            print(
                                f"🟢 CANDLES OK: {requested} -> "
                                f"{candidate} ({len(df)})",
                                flush=True,
                            )
                            return df, candidate

                except TypeError as e:
                    last_error = e
                except Exception as e:
                    last_error = e
                    print(
                        f"🟡 GET_CANDLES FAIL: {requested} -> {candidate}: "
                        f"{type(e).__name__}: {e}",
                        flush=True,
                    )

        # 2) DataFrame helper.
        get_df = getattr(client, 'get_candles_dataframe', None)
        if callable(get_df):
            for call in (
                lambda: get_df(candidate, timeframe),
                lambda: get_df(asset=candidate, timeframe=timeframe),
            ):
                try:
                    df = await call()
                    if df is not None and len(df) > 0:
                        df = df.copy()
                        if 'time' in df.columns and 'timestamp' not in df.columns:
                            df = df.rename(columns={'time': 'timestamp'})
                        if {'open', 'close'}.issubset(df.columns):
                            print(
                                f"🟢 DATAFRAME OK: {requested} -> "
                                f"{candidate} ({len(df)})",
                                flush=True,
                            )
                            return df, candidate
                except TypeError as e:
                    last_error = e
                except Exception as e:
                    last_error = e
                    print(
                        f"🟡 DATAFRAME FAIL: {requested} -> {candidate}: "
                        f"{type(e).__name__}: {e}",
                        flush=True,
                    )

        # 3) A few package versions expose historical candles separately.
        historical = getattr(client, 'get_historical_candles', None)
        if callable(historical):
            calls = (
                lambda: historical(candidate, timeframe, count_request=2),
                lambda: historical(candidate, timeframe, count_request=1),
            )
            for call in calls:
                try:
                    raw = await call()
                    if raw is None:
                        continue
                    if isinstance(raw, pd.DataFrame):
                        df = raw.copy()
                    else:
                        df = pd.DataFrame(raw)
                    if df is not None and len(df) > 0 and {'open', 'close'}.issubset(df.columns):
                        print(
                            f"🟢 HISTORICAL OK: {requested} -> "
                            f"{candidate} ({len(df)})",
                            flush=True,
                        )
                        return df, candidate
                except TypeError as e:
                    last_error = e
                except Exception as e:
                    last_error = e
                    print(
                        f"🟡 HISTORICAL FAIL: {requested} -> {candidate}: "
                        f"{type(e).__name__}: {e}",
                        flush=True,
                    )
    # -----------------------------------------------------
    # CNY NUMERIC-ASSET FALLBACK
    # -----------------------------------------------------
    # Some Pocket Option API builds expose these OTC CNY pairs through
    # numeric asset IDs even when the symbolic candle endpoint returns
    # empty data. Try the ID only after all symbolic methods above fail.
    cny_asset_id = CNY_OTC_ASSET_IDS.get(requested)
    if cny_asset_id is None:
        cny_asset_id = CNY_OTC_ASSET_IDS.get(requested.upper())
    if cny_asset_id is not None:
        print(
            f"🟡 CNY ID FALLBACK: {requested} -> asset_id={cny_asset_id}",
            flush=True,
        )
        for candidate in (cny_asset_id, str(cny_asset_id)):
            get_candles = getattr(client, 'get_candles', None)
            if callable(get_candles):
                for args in (
                    (candidate, timeframe, 120),
                    (candidate, timeframe, 100),
                    (candidate, timeframe),
                ):
                    try:
                        raw = await get_candles(*args)
                        if raw is None:
                            continue
                        if isinstance(raw, pd.DataFrame):
                            df = raw.copy()
                        elif isinstance(raw, dict):
                            df = pd.DataFrame(list(raw.values()))
                        else:
                            df = pd.DataFrame(raw)
                        if len(df) > 0:
                            if 'time' in df.columns and 'timestamp' not in df.columns:
                                df = df.rename(columns={'time': 'timestamp'})
                            if {'open', 'close'}.issubset(df.columns):
                                print(
                                    f"🟢 CNY ID CANDLES OK: {requested} -> "
                                    f"{candidate} ({len(df)})",
                                    flush=True,
                                )
                                return df, requested
                    except Exception as e:
                        last_error = e
                        print(
                            f"🟡 CNY ID GET_CANDLES FAIL: {requested} -> "
                            f"{candidate}: {type(e).__name__}: {e}",
                            flush=True,
                        )

            get_df = getattr(client, 'get_candles_dataframe', None)
            if callable(get_df):
                for call in (
                    lambda: get_df(candidate, timeframe),
                    lambda: get_df(asset=candidate, timeframe=timeframe),
                ):
                    try:
                        df = await call()
                        if df is not None and len(df) > 0:
                            df = df.copy()
                            if 'time' in df.columns and 'timestamp' not in df.columns:
                                df = df.rename(columns={'time': 'timestamp'})
                            if {'open', 'close'}.issubset(df.columns):
                                print(
                                    f"🟢 CNY ID DATAFRAME OK: {requested} -> "
                                    f"{candidate} ({len(df)})",
                                    flush=True,
                                )
                                return df, requested
                    except Exception as e:
                        last_error = e
                        print(
                            f"🟡 CNY ID DATAFRAME FAIL: {requested} -> "
                            f"{candidate}: {type(e).__name__}: {e}",
                            flush=True,
                        )

    if last_error:
        print(
            f"🔴 ALL CANDLE METHODS FAILED: {requested}: "
            f"{type(last_error).__name__}: {last_error}",
            flush=True,
        )
    else:
        print(f"🔴 NO CANDLE DATA: {requested}", flush=True)

    return None, last_error


async def get_signal(
    asset_code,
    timeframe,
    timeframe_name,
    expiry_name
):

    if not PO_SSID:
        return (
            "❌ PO_SSID lama helin.\n\n"
            "Render → Environment Variables ka hubi PO_SSID."
        )

    client = None

    try:
        client = await connect_client()

        df, working_asset = await _get_candles_with_fallback(
            client,
            asset_code,
            timeframe,
        )

        if df is None or len(df) == 0:
            return (
                "❌ DATA LAMA HELIN\n\n"
                f"Asset: {asset_code}\n"
                f"Timeframe: {timeframe_name}\n\n"
                "Pair-kan candles lagama helin."
            )

        # Make sure numeric market columns are usable even when the raw API
        # fallback returned strings.
        for column in ("open", "high", "low", "close", "volume"):
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.dropna(subset=["open", "close"])

        if len(df) < 55:
            return (
                "❌ CANDLES KU FILAN LAMA HELIN\n\n"
                f"Asset: {asset_code}\n"
                f"Timeframe: {timeframe_name}\n"
                f"Candles la helay: {len(df)}\n\n"
                "Ugu yaraan 55 candles ayaa loo baahan yahay."
            )

        df = df.copy()

        # -------------------------------------------------
        # MA10
        # -------------------------------------------------
        df["MA10"] = (
            df["close"]
            .rolling(10)
            .mean()
        )

        # -------------------------------------------------
        # MA50
        # -------------------------------------------------
        df["MA50"] = (
            df["close"]
            .rolling(50)
            .mean()
        )

        # -------------------------------------------------
        # RSI 14
        # -------------------------------------------------
        delta = df["close"].diff()

        gain = (
            delta
            .clip(lower=0)
            .rolling(14)
            .mean()
        )

        loss = (
            -delta
            .clip(upper=0)
            .rolling(14)
            .mean()
        )

        rs = gain / loss.replace(
            0,
            float("nan")
        )

        df["RSI"] = (
            100
            - (
                100
                / (1 + rs)
            )
        )

        last = df.iloc[-1]

        if (
            pd.isna(last["MA10"])
            or pd.isna(last["MA50"])
            or pd.isna(last["RSI"])
        ):
            return (
                "❌ Indicators-ka lama xisaabin karin.\n\n"
                f"Asset: {asset_code}\n"
                f"Timeframe: {timeframe_name}"
            )

        close = float(last["close"])
        open_price = float(last["open"])

        ma10 = float(last["MA10"])
        ma50 = float(last["MA50"])
        rsi = float(last["RSI"])

        bullish_candle = close > open_price
        bearish_candle = close < open_price

        # -------------------------------------------------
        # SIGNAL RULES
        # -------------------------------------------------
        if (
            close > ma10
            and ma10 > ma50
            and 50 <= rsi <= 70
            and bullish_candle
        ):
            signal = "🟢 CALL"

        elif (
            close < ma10
            and ma10 < ma50
            and 30 <= rsi <= 50
            and bearish_candle
        ):
            signal = "🔴 PUT"

        else:
            signal = "🟡 WAIT"

        # -------------------------------------------------
        # CANDLE
        # -------------------------------------------------
        if bullish_candle:
            candle = "Bullish 🟢"
        elif bearish_candle:
            candle = "Bearish 🔴"
        else:
            candle = "Neutral 🟡"

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------
        return (
            "📊 LALAA24BOT SIGNAL\n\n"
            f"Asset: {asset_code}\n"
            f"Signal: {signal}\n\n"
            f"💰 Price: {close:.5f}\n"
            f"MA10: {ma10:.5f}\n"
            f"MA50: {ma50:.5f}\n"
            f"RSI: {rsi:.2f}\n\n"
            f"🕯 Candle: {candle}\n\n"
            f"⏱ Timeframe: {timeframe_name}\n"
            f"⌛ Expiry: {expiry_name}\n\n"
            "⚠️ Technical signal only.\n"
            "⚠️ Ma aha dammaanad faa'iido."
        )

    except Exception as e:
        return (
            "❌ MARKET DATA ERROR\n\n"
            f"Asset: {asset_code}\n"
            f"Timeframe: {timeframe_name}\n\n"
            f"Error: {type(e).__name__}: {e}"
        )

    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.end_headers()

        self.wfile.write(
            b"Lalaa24Bot is running!"
        )

    def log_message(
        self,
        format,
        *args
    ):
        pass


def run_server():

    server = HTTPServer(
        ("0.0.0.0", 10000),
        HealthHandler
    )

    print(
        "🟢 HTTP SERVER RUNNING ON 0.0.0.0:10000",
        flush=True
    )

    server.serve_forever()


# =========================================================
# USER STATE
# =========================================================

user_categories = {}
user_assets = {}
user_timeframes = {}
user_expiries = {}


def button_rows(items, size=2):
    rows, row = [], []
    for item in items:
        row.append(item)
        if len(row) == size:
            rows.append(row); row = []
    if row: rows.append(row)
    return rows


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📊 SIGNAL", "📋 PAIRS"], ["⏱ TIMEFRAME", "⌛ EXPIRY"]]
    await update.message.reply_text(
        "👋 Soo dhawoow LALAA24BOT.\n\n"
        "📊 Dooro Pair, Timeframe iyo Expiry.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# =========================================================
# PAIRS
# =========================================================

async def show_pair_categories(update: Update):
    keyboard = [["💱 FOREX"], ["💱 FOREX OTC"], ["📈 STOCKS"], ["🔙 BACK"]]
    await update.message.reply_text(
        "📋 PAIRS\n\nDooro qaybta Pair-ka:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def show_pairs(update: Update, key: str):
    user_id = update.effective_user.id
    if key == "FOREX":
        assets, category = ASSETS["💱 Forex"], "💱 Forex"
        title = "💱 FOREX"
    elif key == "OTC":
        assets, category = ASSETS["💱 Forex OTC"], "💱 Forex OTC"
        title = "💱 FOREX OTC"
    else:
        assets, category = STOCK_ASSETS, "📈 Stocks"
        title = "📈 STOCKS"
    if not assets:
        await update.message.reply_text("❌ Pairs lama helin qaybtaan.")
        return
    user_categories[user_id] = category
    user_assets[user_id] = dict(assets)
    rows = button_rows(list(assets.keys()), 2)
    rows.append(["🔙 BACK"])
    await update.message.reply_text(
        f"{title}\n\n📊 {len(assets)} pairs/assets\n\n"
        "Dooro Pair-ka aad rabto.\n📌 Pair-ku automatic uma beddelmayo.",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
    )


# =========================================================
# TIMEFRAME — INDEPENDENT
# =========================================================

async def show_timeframes(update: Update):
    current = user_timeframes.get(update.effective_user.id)
    rows = button_rows(list(TIMEFRAMES.keys()), 2)
    rows.append(["🔙 BACK"])
    await update.message.reply_text(
        "⏱ TIMEFRAME\n\n" + (f"Current: {current}\n\n" if current else "") +
        "Dooro Timeframe-ka:",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
    )


# =========================================================
# EXPIRY — INDEPENDENT
# =========================================================

async def show_expiries(update: Update):
    current = user_expiries.get(update.effective_user.id)
    rows = button_rows(list(EXPIRIES.keys()), 2)
    rows.append(["🔙 BACK"])
    await update.message.reply_text(
        "⌛ EXPIRY\n\n" + (f"Current: {current}\n\n" if current else "") +
        "Dooro Expiry-ga:\n📌 Expiry-ga Timeframe-ka ma beddelayo.",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
    )


# =========================================================
# SIGNAL
# =========================================================

async def send_signal(update: Update):
    user_id = update.effective_user.id
    assets = user_assets.get(user_id, {})
    if "__selected_code__" not in assets:
        await update.message.reply_text("❌ Marka hore 📋 PAIRS ka dooro Pair.")
        return
    timeframe_name = user_timeframes.get(user_id)
    expiry_name = user_expiries.get(user_id)
    if not timeframe_name:
        await update.message.reply_text("❌ Marka hore ⏱ TIMEFRAME dooro.")
        return
    if not expiry_name:
        await update.message.reply_text("❌ Marka hore ⌛ EXPIRY dooro.")
        return
    asset_code = assets["__selected_code__"]
    asset_name = assets["__selected_name__"]
    await update.message.reply_text(
        "⏳ Signal-ka waa la baarayaa...\n\n"
        f"💱 Pair: {asset_name}\n"
        f"🔑 API Code: {asset_code}\n"
        f"⏱ Timeframe: {timeframe_name}\n"
        f"⌛ Expiry: {expiry_name}"
    )
    signal = await get_signal(asset_code, TIMEFRAMES[timeframe_name], timeframe_name, expiry_name)
    await update.message.reply_text(signal)


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    text = update.message.text
    user_id = update.effective_user.id
    if text == "📋 PAIRS":
        await show_pair_categories(update); return
    if text == "⏱ TIMEFRAME":
        await show_timeframes(update); return
    if text == "⌛ EXPIRY":
        await show_expiries(update); return
    if text == "📊 SIGNAL":
        await send_signal(update); return
    if text == "🔙 BACK":
        keyboard = [["📊 SIGNAL", "📋 PAIRS"], ["⏱ TIMEFRAME", "⌛ EXPIRY"]]
        await update.message.reply_text("🏠 Main Menu", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)); return
    if text == "💱 FOREX":
        await show_pairs(update, "FOREX"); return
    if text == "💱 FOREX OTC":
        await show_pairs(update, "OTC"); return
    if text == "📈 STOCKS":
        await show_pairs(update, "STOCKS"); return
    if text in TIMEFRAMES:
        user_timeframes[user_id] = text
        await update.message.reply_text(
            f"✅ TIMEFRAME WAA LA DOORTAY\n\n⏱ {text}\n\n⌛ Expiry-ga isma beddelin.",
            reply_markup=ReplyKeyboardMarkup([["📊 SIGNAL", "📋 PAIRS"], ["⏱ TIMEFRAME", "⌛ EXPIRY"]], resize_keyboard=True)
        ); return
    if text in EXPIRIES:
        user_expiries[user_id] = text
        await update.message.reply_text(
            f"✅ EXPIRY WAA LA DOORTAY\n\n⌛ {text}\n\n⏱ Timeframe-ka isma beddelin.",
            reply_markup=ReplyKeyboardMarkup([["📊 SIGNAL", "📋 PAIRS"], ["⏱ TIMEFRAME", "⌛ EXPIRY"]], resize_keyboard=True)
        ); return
    assets = user_assets.get(user_id, {})
    if text in assets and not text.startswith("__"):
        user_assets[user_id]["__selected_code__"] = assets[text]
        user_assets[user_id]["__selected_name__"] = text
        await update.message.reply_text(
            "✅ PAIR WAA LA DOORTAY\n\n"
            f"💱 Pair: {text}\n"
            f"🔑 API Code: {assets[text]}\n\n"
            f"⏱ Timeframe: {user_timeframes.get(user_id, 'Lama dooran')}\n"
            f"⌛ Expiry: {user_expiries.get(user_id, 'Lama dooran')}\n\n"
            "📌 Pair-ku automatic uma beddelmayo.",
            reply_markup=ReplyKeyboardMarkup([["📊 SIGNAL", "📋 PAIRS"], ["⏱ TIMEFRAME", "⌛ EXPIRY"]], resize_keyboard=True)
        ); return
    await update.message.reply_text("❌ Fadlan ka dooro menu-ga hoose.")
    # =========================================================
# MAIN
# =========================================================

def main():
    Thread(target=run_server, daemon=True).start()
    print("🟡 Starting LALAA24BOT...", flush=True)
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN lama helin!", flush=True)
        return
    print("🟢 Telegram token waa la helay.", flush=True)
    if not PO_SSID:
        print("⚠️ PO_SSID lama helin!", flush=True)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🟢 LALAA24BOT IS RUNNING", flush=True)
    app.run_polling(drop_pending_updates=True)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
    
