import os
import asyncio
import json
import re
import numpy as np
import pandas as pd

from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    ReplyKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from pocketoptionapi_async import AsyncPocketOptionClient


# =========================================================
# GEMINI
# =========================================================




# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

PO_SSID = (
    os.getenv("POCKET_OPTION_SSID")
    or os.getenv("PO_SSID")
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

AI_MODEL = "gemini-2.5-flash-lite"

IS_DEMO = True

PORT = int(
    os.getenv(
        "PORT",
        "10000"
    )
)

CONNECT_TIMEOUT = 40
CANDLE_TIMEOUT = 30

CANDLE_COUNT = 100


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_TIMEFRAME = 180
DEFAULT_EXPIRY = 180


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


# =========================================================
# EXPIRIES
# =========================================================

EXPIRIES = {
    "1️⃣ 1 Minute": 60,
    "3️⃣ 3 Minutes": 180,
    "5️⃣ 5 Minutes": 300,
    "10️⃣ 10 Minutes": 600,
    "15️⃣ 15 Minutes": 900,
}


# =========================================================
# HIGHER TIMEFRAME
# =========================================================

HIGHER_TIMEFRAME = {
    60: 180,
    180: 300,
    300: 900,
    900: 1800,
    1800: 3600,
    3600: 14400,
    14400: 14400,
}


# =========================================================
# FOREX
# =========================================================

FOREX_PAIRS = {

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
}


# =========================================================
# FOREX OTC
# =========================================================

FOREX_OTC_PAIRS = {

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

    "SAR/USD OTC": "SARUSD_otc",
}


# =========================================================
# CNY OTC ASSET IDS
# =========================================================

CNY_OTC_ASSETS = {
    "AEDCNY_otc": 538,
    "BHDCNY_otc": 536,
    "JODCNY_otc": 546,
    "OMRCNY_otc": 544,
    "QARCNY_otc": 542,
    "SARCNY_otc": 540,
}


# =========================================================
# STOCKS
# =========================================================

STOCK_NAMES = {

    "#AAPL": "🍎 Apple",
    "#AXP": "💳 American Express",
    "#MCD": "🍔 McDonald's",
    "#MSFT": "🟢 Microsoft",
    "#META": "🔵 Meta",
    "#AMZN": "🟠 Amazon",
    "#TSLA": "🚗 Tesla",
    "#NVDA": "🟢 NVIDIA",
    "#KO": "🔴 Coca-Cola",
    "#MA": "💳 Mastercard",
    "#V": "💳 Visa",

    "#GOOGL": "🔵 Google",
    "#GOOG": "🔵 Google",

    "#NFLX": "🎬 Netflix",
    "#AMD": "🔴 AMD",
    "#INTC": "🔵 Intel",
    "#IBM": "🔵 IBM",
    "#ORCL": "🔴 Oracle",
    "#CRM": "☁️ Salesforce",
    "#DIS": "🏰 Disney",
    "#NKE": "👟 Nike",
    "#PEP": "🥤 PepsiCo",
    "#WMT": "🛒 Walmart",

    "#JPM": "🏦 JPMorgan Chase",
    "#BAC": "🏦 Bank of America",
    "#C": "🏦 Citigroup",
    "#GS": "🏦 Goldman Sachs",

    "#XOM": "⛽ Exxon Mobil",
    "#CVX": "⛽ Chevron",

    "#BA": "✈️ Boeing",
    "#PFE": "💊 Pfizer",
    "#JNJ": "💊 Johnson & Johnson",

    "#CSCO": "🌐 Cisco",
    "#ADBE": "🎨 Adobe",
    "#QCOM": "📱 Qualcomm",
    "#UBER": "🚕 Uber",
    "#PYPL": "💳 PayPal",
    "#SHOP": "🛍 Shopify",
    "#BABA": "🛒 Alibaba",

    "#T": "📡 AT&T",
    "#VZ": "📡 Verizon",
}


# =========================================================
# STOCK OTC
# =========================================================

STOCK_OTC_NAMES = {

    "#AAPL_otc": "🍎 Apple OTC",
    "#AXP_otc": "💳 American Express OTC",
    "#MCD_otc": "🍔 McDonald's OTC",
    "#MSFT_otc": "🟢 Microsoft OTC",
    "#META_otc": "🔵 Meta OTC",
    "#AMZN_otc": "🟠 Amazon OTC",
    "#TSLA_otc": "🚗 Tesla OTC",
    "#NVDA_otc": "🟢 NVIDIA OTC",
    "#KO_otc": "🔴 Coca-Cola OTC",
    "#MA_otc": "💳 Mastercard OTC",
    "#V_otc": "💳 Visa OTC",

    "#GOOGL_otc": "🔵 Google OTC",
    "#GOOG_otc": "🔵 Google OTC",

    "#NFLX_otc": "🎬 Netflix OTC",
    "#AMD_otc": "🔴 AMD OTC",
    "#INTC_otc": "🔵 Intel OTC",
    "#IBM_otc": "🔵 IBM OTC",
    "#ORCL_otc": "🔴 Oracle OTC",
    "#CRM_otc": "☁️ Salesforce OTC",
    "#DIS_otc": "🏰 Disney OTC",
    "#NKE_otc": "👟 Nike OTC",
    "#PEP_otc": "🥤 PepsiCo OTC",
    "#WMT_otc": "🛒 Walmart OTC",

    "#JPM_otc": "🏦 JPMorgan Chase OTC",
    "#BAC_otc": "🏦 Bank of America OTC",
    "#C_otc": "🏦 Citigroup OTC",
    "#GS_otc": "🏦 Goldman Sachs OTC",

    "#XOM_otc": "⛽ Exxon Mobil OTC",
    "#CVX_otc": "⛽ Chevron OTC",

    "#BA_otc": "✈️ Boeing OTC",
    "#PFE_otc": "💊 Pfizer OTC",
    "#JNJ_otc": "💊 Johnson & Johnson OTC",

    "#CSCO_otc": "🌐 Cisco OTC",
    "#ADBE_otc": "🎨 Adobe OTC",
    "#QCOM_otc": "📱 Qualcomm OTC",
    "#UBER_otc": "🚕 Uber OTC",
    "#PYPL_otc": "💳 PayPal OTC",
    "#SHOP_otc": "🛍 Shopify OTC",
    "#BABA_otc": "🛒 Alibaba OTC",

    "#T_otc": "📡 AT&T OTC",
    "#VZ_otc": "📡 Verizon OTC",
}


# =========================================================
# CATEGORIES
# =========================================================

CATEGORIES = {
    "💱 FOREX": FOREX_PAIRS,
    "💱 FOREX OTC": FOREX_OTC_PAIRS,
    "📈 STOCKS": STOCK_NAMES,
    "📈 STOCKS OTC": STOCK_OTC_NAMES,
}


# =========================================================
# USER SETTINGS
# =========================================================

USER_SETTINGS = {}


def get_settings(user_id):

    if user_id not in USER_SETTINGS:

        USER_SETTINGS[user_id] = {
            "category": None,
            "asset": DEFAULT_ASSET if False else None,
            "timeframe": DEFAULT_TIMEFRAME,
            "expiry": DEFAULT_EXPIRY,
        }

    return USER_SETTINGS[user_id]


# =========================================================
# NAME HELPERS
# =========================================================

def timeframe_name(seconds):

    names = {
        60: "1 Minute",
        180: "3 Minutes",
        300: "5 Minutes",
        900: "15 Minutes",
        1800: "30 Minutes",
        3600: "1 Hour",
        14400: "4 Hours",
    }

    return names.get(
        seconds,
        f"{seconds} Seconds"
    )


def expiry_name(seconds):

    names = {
        60: "1 Minute",
        180: "3 Minutes",
        300: "5 Minutes",
        600: "10 Minutes",
        900: "15 Minutes",
    }

    return names.get(
        seconds,
        f"{seconds} Seconds"
    )


def format_price(value):

    try:

        value = float(value)

        if value >= 100:
            return f"{value:.2f}"

        if value >= 1:
            return f"{value:.5f}"

        return f"{value:.6f}"

    except Exception:

        return str(value)


# =========================================================
# BUTTON CHUNKS
# =========================================================

def make_rows(items, per_row=2):

    rows = []

    row = []

    for item in items:

        row.append(item)

        if len(row) >= per_row:

            rows.append(row)

            row = []

    if row:
        rows.append(row)

    return rows


# =========================================================
# RSI
# =========================================================

def calculate_rsi(
    series,
    period=14
):

    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.rolling(
        period
    ).mean()

    avg_loss = loss.rolling(
        period
    ).mean()

    avg_loss = avg_loss.replace(
        0,
        np.nan
    )

    rs = avg_gain / avg_loss

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# =========================================================
# ASSET VARIANTS
# =========================================================

def get_asset_variants(
    asset_code
):

    variants = []

    if not asset_code:
        return variants

    original = str(
        asset_code
    ).strip()

    candidates = [
        original,
        original.replace(
            "/",
            ""
        ),
    ]

    if original.lower().endswith(
        "_otc"
    ):

        base = original[:-4]

        candidates.extend([
            base + "_otc",
            base.upper() + "_otc",
            base.upper() + "-OTC",
            base.upper() + " OTC",
            base.upper() + "_OTC",
        ])

    else:

        no_slash = original.replace(
            "/",
            ""
        )

        candidates.extend([
            original + "_otc",
            no_slash + "_otc",
            no_slash.upper() + "_otc",
        ])

    for item in candidates:

        if item and item not in variants:

            variants.append(item)

    return variants


# =========================================================
# CONNECT POCKET OPTION
# =========================================================

async def connect_client():

    if not PO_SSID:
        raise RuntimeError(
            "POCKET_OPTION_SSID / PO_SSID lama helin."
        )

    print(
        "🔵 PO CONNECT: bilaabatay...",
        flush=True
    )

    print(
        f"🔵 PO CONNECT: SSID length={len(PO_SSID)}",
        flush=True
    )

    client = AsyncPocketOptionClient(
        PO_SSID,
        is_demo=True,
        enable_logging=True
    )

    try:

        await asyncio.wait_for(
            client.connect(),
            timeout=CONNECT_TIMEOUT
        )

        print(
            "🟢 PO CONNECT: SUCCESS",
            flush=True
        )

        return client

    except asyncio.TimeoutError:

        print(
            "🔴 PO CONNECT: TIMEOUT",
            flush=True
        )

        try:
            await client.disconnect()
        except Exception:
            pass

        raise RuntimeError(
            f"Pocket Option connection timeout "
            f"({CONNECT_TIMEOUT}s)."
        )

    except Exception as e:

        print(
            "🔴 PO CONNECT ERROR:",
            repr(e),
            flush=True
        )

        try:
            await client.disconnect()
        except Exception:
            pass

        raise


# =========================================================
# GET CANDLES
# =========================================================

async def get_candles(
    client,
    asset_code,
    timeframe
):

    variants = get_asset_variants(
        asset_code
    )

    last_error = None

    for variant in variants:

        # -------------------------------------------------
        # METHOD 1: get_candles_dataframe
        # -------------------------------------------------

        try:

            method = getattr(
                client,
                "get_candles_dataframe",
                None
            )

            if callable(method):

                print(
                    f"🔵 CANDLES DATAFRAME: {variant}",
                    flush=True
                )

                df = await asyncio.wait_for(
                    method(
                        asset=variant,
                        timeframe=timeframe
                    ),
                    timeout=CANDLE_TIMEOUT
                )

                if (
                    df is not None
                    and not df.empty
                ):

                    df = df.copy()

                    df.columns = [
                        str(c).lower()
                        for c in df.columns
                    ]

                    for column in [
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume"
                    ]:

                        if column in df.columns:

                            df[column] = pd.to_numeric(
                                df[column],
                                errors="coerce"
                            )

                    if (
                        "open" in df.columns
                        and "close" in df.columns
                    ):

                        df = df.dropna(
                            subset=[
                                "open",
                                "close"
                            ]
                        ).reset_index(
                            drop=True
                        )

                        if len(df) >= 20:

                            print(
                                f"🟢 CANDLES OK: "
                                f"{variant} rows={len(df)}",
                                flush=True
                            )

                            return df

        except Exception as e:

            last_error = e

            print(
                f"🟡 DATAFRAME ERROR "
                f"{variant}: {e}",
                flush=True
            )

        # -------------------------------------------------
        # METHOD 2: get_candles
        # -------------------------------------------------

        try:

            method = getattr(
                client,
                "get_candles",
                None
            )

            if callable(method):

                print(
                    f"🔵 CANDLES RAW: {variant}",
                    flush=True
                )

                raw = await asyncio.wait_for(
                    method(
                        variant,
                        timeframe,
                        CANDLE_COUNT
                    ),
                    timeout=CANDLE_TIMEOUT
                )

                if raw is None:
                    continue

                if isinstance(
                    raw,
                    pd.DataFrame
                ):

                    df = raw.copy()

                elif isinstance(
                    raw,
                    dict
                ):

                    data = (
                        raw.get("candles")
                        or raw.get("data")
                        or raw.get("result")
                        or raw.get("rows")
                        or []
                    )

                    df = pd.DataFrame(
                        data
                    )

                else:

                    df = pd.DataFrame(
                        raw
                    )

                if df.empty:
                    continue

                rename_map = {}

                for column in df.columns:

                    key = str(
                        column
                    ).lower()

                    if key in [
                        "o",
                        "open_price"
                    ]:
                        rename_map[column] = "open"

                    elif key in [
                        "h",
                        "high_price"
                    ]:
                        rename_map[column] = "high"

                    elif key in [
                        "l",
                        "low_price"
                    ]:
                        rename_map[column] = "low"

                    elif key in [
                        "c",
                        "close_price"
                    ]:
                        rename_map[column] = "close"

                df = df.rename(
                    columns=rename_map
                )

                required = [
                    "open",
                    "high",
                    "low",
                    "close"
                ]

                if not all(
                    column in df.columns
                    for column in required
                ):

                    continue

                for column in required:

                    df[column] = pd.to_numeric(
                        df[column],
                        errors="coerce"
                    )

                df = df.dropna(
                    subset=required
                ).reset_index(
                    drop=True
                )

                if len(df) >= 20:

                    print(
                        f"🟢 CANDLES RAW OK: "
                        f"{variant} rows={len(df)}",
                        flush=True
                    )

                    return df

        except Exception as e:

            last_error = e

            print(
                f"🟡 RAW CANDLE ERROR "
                f"{variant}: {e}",
                flush=True
            )

    print(
        f"🔴 DATA LAMA HELIN: "
        f"{asset_code}; error={last_error}",
        flush=True
    )

    return None


# =========================================================
# HIGHER TIMEFRAME
# =========================================================

def get_higher_timeframe(
    timeframe
):

    return HIGHER_TIMEFRAME.get(
        timeframe,
        300
    )


# =========================================================
# TECHNICAL SIGNAL
# =========================================================

def technical_signal_from_counts(
    call_count,
    put_count
):

    if (
        call_count == 5
        and call_count > put_count
    ):

        return "CALL", "5/5"

    if (
        put_count == 5
        and put_count > call_count
    ):

        return "PUT", "5/5"

    if (
        call_count == 4
        and call_count > put_count
    ):

        return "CALL", "4/5"

    if (
        put_count == 4
        and put_count > call_count
    ):

        return "PUT", "4/5"

    if call_count > put_count:

        return "CALL", f"{call_count}/5"

    if put_count > call_count:

        return "PUT", f"{put_count}/5"

    return "WAIT", "0-3/5"


# =========================================================
# SUPPORT / RESISTANCE
# =========================================================

def support_resistance(
    df
):

    recent = df.tail(
        20
    )

    support = float(
        recent["low"].min()
    )

    resistance = float(
        recent["high"].max()
    )

    price = float(
        recent["close"].iloc[-1]
    )

    total_range = (
        resistance - support
    )

    if total_range <= 0:

        return (
            support,
            resistance,
            0.0,
            0.0,
            False,
            False
        )

    distance_support = (
        price - support
    )

    distance_resistance = (
        resistance - price
    )

    # CALL needs enough room before resistance.
    call_pass = (
        distance_resistance
        >= total_range * 0.20
    )

    # PUT needs enough room before support.
    put_pass = (
        distance_support
        >= total_range * 0.20
    )

    return (
        support,
        resistance,
        distance_support,
        distance_resistance,
        call_pass,
        put_pass
    )


# =========================================================
# GEMINI AI
# =========================================================

async def ask_gemini(
    asset,
    timeframe,
    expiry,
    df,
    higher_signal,
    trend_signal,
    rsi_signal,
    current_signal,
    previous_signal,
    call_count,
    put_count,
    support,
    resistance,
    price
):

    if not GEMINI_API_KEY:

        print(
            "AI ERROR: GEMINI_API_KEY missing",
            flush=True
        )

        return "ERROR"



        print(
            "AI ERROR: google-genai missing",
            flush=True
        )

        return "ERROR"

    try:

        recent = df.tail(
            20
        )[
            [
                "open",
                "high",
                "low",
                "close"
            ]
        ].copy()

        recent_rows = []

        for _, row in recent.iterrows():

            recent_rows.append({

                "open": round(
                    float(row["open"]),
                    8
                ),

                "high": round(
                    float(row["high"]),
                    8
                ),

                "low": round(
                    float(row["low"]),
                    8
                ),

                "close": round(
                    float(row["close"]),
                    8
                ),

            })

        technical_direction = (

            "CALL"
            if call_count > put_count

            else "PUT"
            if put_count > call_count

            else "WAIT"
        )

        prompt = f"""
You are a conservative market-analysis confirmation engine.

You are NOT placing trades.

Analyze ONLY the supplied technical information.

Asset: {asset}
Timeframe: {timeframe_name(timeframe)}
Expiry: {expiry_name(expiry)}

Technical direction:
{technical_direction}

CALL confirmations:
{call_count}/5

PUT confirmations:
{put_count}/5

Trend:
{trend_signal}

RSI:
{rsi_signal}

Current candle:
{current_signal}

Previous candle:
{previous_signal}

Higher timeframe:
{higher_signal}

Price:
{price}

Support:
{support}

Resistance:
{resistance}

Recent candles:
{json.dumps(recent_rows)}

Rules:

1. Return BUY only when supplied evidence supports upward direction.
2. Return SELL only when supplied evidence supports downward direction.
3. Return WAIT when evidence is mixed, weak, conflicting, near important levels, or insufficient.
4. Never invent market information.
5. Do not explain.
6. Return exactly one word:
BUY
SELL
or
WAIT
"""

        def call_ai():

            import requests

            url = (
                "https://generativelanguage.googleapis.com/"
                "v1beta/models/"
                f"{AI_MODEL}:generateContent"
            )

            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY
            }

            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:

                print(
                    "GEMINI HTTP ERROR:",
                    response.status_code,
                    response.text[:500],
                    flush=True
                )

                return ""

            data = response.json()

            try:

                text = (
                    data["candidates"][0]
                    ["content"]["parts"][0]
                    ["text"]
                )

            except Exception:

                return ""

            return text or ""

        text = await asyncio.to_thread(
            call_ai
        )

        if not text:

            return "ERROR"

        answer = text.strip().upper()

        if re.search(
            r"\bBUY\b",
            answer
        ):

            return "BUY"

        if re.search(
            r"\bSELL\b",
            answer
        ):

            return "SELL"

        if re.search(
            r"\bWAIT\b",
            answer
        ):

            return "WAIT"

        return "ERROR"

        answer = text.strip().upper()

        if re.search(
            r"\bBUY\b",
            answer
        ):

            return "BUY"

        if re.search(
            r"\bSELL\b",
            answer
        ):

            return "SELL"

        if re.search(
            r"\bWAIT\b",
            answer
        ):

            return "WAIT"

        return "ERROR"

Muhiim: "" qaybtii hore ee aad sheegtay sidoo kale waa inay meesha ka baxdaa. "genai" hadda gabi ahaanba ma isticmaaleyno.

Kadib Commit → Deploy.

Ha beddelin wax kale.

answer = text.strip().upper()

if re.search(
    r"\bBUY\b",
    answer
):
    return "BUY"

if re.search(
    r"\bSELL\b",
    answer
):
    return "SELL"

if re.search(
    r"\bWAIT\b",
    answer
):
    return "WAIT"

return "ERROR"

Laakiin hal wax muhiim ah: qaybta kore ee function-kaaga waxaa weli ku jiri kara:

if genai is None:

Taasna waa in laga saaraa, sababtoo ah "genai" dambe ma isticmaaleyno.

Markaas "NameError: name 'genai' is not defined" wuu joogsanayaa.


# =========================================================
# SIGNAL PANEL
# =========================================================

def build_signal_panel(
    display_asset,
    final_signal,
    technical_direction,
    technical_count,
    trend,
    momentum,
    current_signal,
    previous_signal,
    higher_signal,
    call_count,
    put_count,
    price,
    ma10,
    ma50,
    rsi,
    sr_status,
    ai_signal,
    timeframe,
    expiry,
    reason=None
):

    if final_signal == "BUY":

        final_icon = "🟢"

    elif final_signal == "SELL":

        final_icon = "🔴"

    else:

        final_icon = "⚪"

    if technical_direction == "CALL":

        technical_text = (
            f"CALL {technical_count}"
        )

    elif technical_direction == "PUT":

        technical_text = (
            f"PUT {technical_count}"
        )

    else:

        technical_text = (
            f"WAIT {technical_count}"
        )

    if sr_status == "PASS":

        sr_text = "PASS ✅"

    else:

        sr_text = "FAIL ❌"

    if ai_signal == "BUY":

        ai_text = "BUY 🟢"

    elif ai_signal == "SELL":

        ai_text = "SELL 🔴"

    elif ai_signal == "WAIT":

        ai_text = "WAIT ⚪"

    else:

        ai_text = "UNAVAILABLE ⚠️"

    message = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 NAASIRFX AI SIGNAL\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"💱 {display_asset}\n"
        "\n"
        f"{final_icon} FINAL: {final_signal}\n"
        f"📊 Technical: {technical_text}\n"
        "\n"
        f"⏱ Timeframe: {timeframe_name(timeframe)}\n"
        f"⌛ Expiry: {expiry_name(expiry)}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 TECHNICAL ANALYSIS\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"📈 Trend:       {trend}\n"
        f"📊 RSI:         {momentum}\n"
        f"🕯 Current:     {current_signal}\n"
        f"🕯 Previous:    {previous_signal}\n"
        f"⏫ Higher TF:   {higher_signal}\n"
        "\n"
        f"🟢 CALL: {call_count}/5\n"
        f"🔴 PUT: {put_count}/5\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📐 MARKET DATA\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"💰 Price: {format_price(price)}\n"
        f"📈 MA10:  {format_price(ma10)}\n"
        f"📉 MA50:  {format_price(ma50)}\n"
        f"📊 RSI:   {rsi:.2f}\n"
        "\n"
        f"🛡 S/R: {sr_text}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 GEMINI AI\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"AI: {ai_text}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 FINAL SIGNAL\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"{final_icon} {final_signal}\n"
        "\n"
    )

    if final_signal == "WAIT" and reason:

        message += (
            f"ℹ️ Reason: {reason}\n"
            "\n"
        )

    message += (
        "⚠️ SIGNAL ONLY\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    return message


# =========================================================
# GET SIGNAL
# =========================================================

async def get_signal(
    asset_code,
    timeframe,
    display_asset,
    expiry
):

    client = None

    try:

        print(
            "🔵 SIGNAL REQUEST:",
            display_asset,
            asset_code,
            timeframe_name(timeframe),
            expiry_name(expiry),
            flush=True
        )

        if not PO_SSID:

            return (
                "❌ POCKET OPTION SSID LAMA HELIN\n\n"
                "Render Environment Variables ka hubi:\n"
                "POCKET_OPTION_SSID"
            )

        client = await connect_client()

        # =================================================
        # CURRENT TIMEFRAME
        # =================================================

        df = await get_candles(
            client,
            asset_code,
            timeframe
        )

        if (
            df is None
            or df.empty
        ):

            return (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 NAASIRFX AI SIGNAL\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {display_asset}\n\n"
                "⚪ FINAL: WAIT\n\n"
                "❌ DATA LAMA HELIN\n\n"
                "Candles ku filan lama helin.\n\n"
                f"⏱ Timeframe: "
                f"{timeframe_name(timeframe)}\n"
                f"⌛ Expiry: "
                f"{expiry_name(expiry)}\n\n"
                "⚠️ SIGNAL ONLY\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

        if len(df) < 60:

            return (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 NAASIRFX AI SIGNAL\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {display_asset}\n\n"
                "⚪ FINAL: WAIT\n\n"
                f"❌ Candles: {len(df)}\n"
                "Waxaa loo baahan yahay ugu "
                "yaraan 60 candles.\n\n"
                f"⏱ Timeframe: "
                f"{timeframe_name(timeframe)}\n"
                f"⌛ Expiry: "
                f"{expiry_name(expiry)}\n\n"
                "⚠️ SIGNAL ONLY\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

        # =================================================
        # INDICATORS
        # =================================================

        df["MA10"] = (
            df["close"]
            .rolling(10)
            .mean()
        )

        df["MA50"] = (
            df["close"]
            .rolling(50)
            .mean()
        )

        df["RSI"] = calculate_rsi(
            df["close"],
            14
        )

        latest = df.iloc[-1]

        previous = df.iloc[-2]

        if (
            pd.isna(latest["MA10"])
            or pd.isna(latest["MA50"])
            or pd.isna(latest["RSI"])
        ):

            return (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 NAASIRFX AI SIGNAL\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {display_asset}\n\n"
                "⚪ FINAL: WAIT\n\n"
                "❌ Indicator data aan "
                "dhammeystirnayn.\n\n"
                "⚠️ SIGNAL ONLY\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

        price = float(
            latest["close"]
        )

        ma10 = float(
            latest["MA10"]
        )

        ma50 = float(
            latest["MA50"]
        )

        rsi = float(
            latest["RSI"]
        )

        current_open = float(
            latest["open"]
        )

        current_close = float(
            latest["close"]
        )

        previous_open = float(
            previous["open"]
        )

        previous_close = float(
            previous["close"]
        )

        # =================================================
        # 1. TREND
        # =================================================

        if (
            price > ma10
            and ma10 > ma50
        ):

            trend = "CALL 🟢"

        elif (
            price < ma10
            and ma10 < ma50
        ):

            trend = "PUT 🔴"

        else:

            trend = "NEUTRAL ⚪"

        # =================================================
        # 2. RSI
        # =================================================

        if 50 <= rsi <= 70:

            momentum = "CALL 🟢"

        elif 30 <= rsi < 50:

            momentum = "PUT 🔴"

        else:

            momentum = "NEUTRAL ⚪"

        # =================================================
        # 3. CURRENT CANDLE
        # =================================================

        if current_close > current_open:

            current_signal = "CALL 🟢"

        elif current_close < current_open:

            current_signal = "PUT 🔴"

        else:

            current_signal = "NEUTRAL ⚪"

        # =================================================
        # 4. PREVIOUS CANDLE
        # =================================================

        if previous_close > previous_open:

            previous_signal = "CALL 🟢"

        elif previous_close < previous_open:

            previous_signal = "PUT 🔴"

        else:

            previous_signal = "NEUTRAL ⚪"

        # =================================================
        # 5. HIGHER TIMEFRAME
        # =================================================

        higher_tf = get_higher_timeframe(
            timeframe
        )

        if timeframe == 14400:

            higher_signal = "CALL 🟢" if (
                current_close > current_open
            ) else (
                "PUT 🔴"
                if current_close < current_open
                else "NEUTRAL ⚪"
            )

        else:

            higher_df = await get_candles(
                client,
                asset_code,
                higher_tf
            )

            if (
                higher_df is None
                or len(higher_df) < 2
            ):

                higher_signal = (
                    "NEUTRAL ⚪"
                )

            else:

                # Previous candle on higher timeframe
                # to reduce use of forming candle.

                higher_latest = (
                    higher_df.iloc[-2]
                )

                higher_open = float(
                    higher_latest["open"]
                )

                higher_close = float(
                    higher_latest["close"]
                )

                if higher_close > higher_open:

                    higher_signal = (
                        "CALL 🟢"
                    )

                elif higher_close < higher_open:

                    higher_signal = (
                        "PUT 🔴"
                    )

                else:

                    higher_signal = (
                        "NEUTRAL ⚪"
                    )

        # =================================================
        # CONFIRMATION COUNT
        # =================================================

        confirmations = [
            trend,
            momentum,
            current_signal,
            previous_signal,
            higher_signal,
        ]

        call_count = sum(
            1
            for item in confirmations
            if item.startswith("CALL")
        )

        put_count = sum(
            1
            for item in confirmations
            if item.startswith("PUT")
        )

        technical_direction, technical_count = (
            technical_signal_from_counts(
                call_count,
                put_count
            )
        )

        # =================================================
        # SUPPORT / RESISTANCE
        # =================================================

        (
            support,
            resistance,
            distance_support,
            distance_resistance,
            call_sr_pass,
            put_sr_pass
        ) = support_resistance(
            df
        )

        if technical_direction == "CALL":

            sr_pass = call_sr_pass

        elif technical_direction == "PUT":

            sr_pass = put_sr_pass

        else:

            sr_pass = False

        sr_status = (
            "PASS"
            if sr_pass
            else "FAIL"
        )
 # =================================================
        # GEMINI
        # =================================================

        ai_signal = await ask_gemini(
            asset=asset_code,
            timeframe=timeframe,
            expiry=expiry,
            df=df,
            higher_signal=higher_signal,
            trend_signal=trend,
            rsi_signal=momentum,
            current_signal=current_signal,
            previous_signal=previous_signal,
            call_count=call_count,
            put_count=put_count,
            support=support,
            resistance=resistance,
            price=price
        )

        # =================================================
        # FINAL SIGNAL
        # =================================================

        final_signal = "WAIT"

        reason = None

        # 5/5 or 4/5 + S/R + Gemini agreement

        if (
            technical_direction == "CALL"
            and technical_count in [
                "4/5",
                "5/5"
            ]
        ):

            if not sr_pass:

                reason = (
                    "S/R filter ayaa BLOCKED."
                )

            elif ai_signal == "BUY":

                final_signal = "BUY"

            elif ai_signal == "WAIT":

                reason = (
                    "Gemini AI wuxuu yiri WAIT."
                )

            elif ai_signal == "SELL":

                reason = (
                    "Technical-ku CALL ayuu yahay "
                    "laakiin Gemini SELL ayuu soo celiyey."
                )

            else:

                reason = (
                    "Gemini AI lama helin."
                )

        elif (
            technical_direction == "PUT"
            and technical_count in [
                "4/5",
                "5/5"
            ]
        ):

            if not sr_pass:

                reason = (
                    "S/R filter ayaa BLOCKED."
                )

            elif ai_signal == "SELL":

                final_signal = "SELL"

            elif ai_signal == "WAIT":

                reason = (
                    "Gemini AI wuxuu yiri WAIT."
                )

            elif ai_signal == "BUY":

                reason = (
                    "Technical-ku PUT ayuu yahay "
                    "laakiin Gemini BUY ayuu soo celiyey."
                )

            else:

                reason = (
                    "Gemini AI lama helin."
                )

        else:

            reason = (
                "Technical confirmation-ku "
                "4/5 ama 5/5 ma gaarin."
            )

        # =================================================
        # PANEL
        # =================================================

        return build_signal_panel(

            display_asset=display_asset,

            final_signal=final_signal,

            technical_direction=technical_direction,

            technical_count=technical_count,

            trend=trend,

            momentum=momentum,

            current_signal=current_signal,

            previous_signal=previous_signal,

            higher_signal=higher_signal,

            call_count=call_count,

            put_count=put_count,

            price=price,

            ma10=ma10,

            ma50=ma50,

            rsi=rsi,

            sr_status=sr_status,

            ai_signal=ai_signal,

            timeframe=timeframe,

            expiry=expiry,

            reason=reason
        )

    except Exception as e:

        print(
            "SIGNAL ERROR:",
            repr(e),
            flush=True
        )

        return (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 NAASIRFX AI SIGNAL\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💱 {display_asset}\n\n"
            "⚪ FINAL: WAIT\n\n"
            "❌ SIGNAL ERROR\n\n"
            f"{type(e).__name__}: {str(e)}\n\n"
            "⚠️ SIGNAL ONLY\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

    finally:

        if client is not None:

            try:

                await client.disconnect()

            except Exception:

                pass


# =========================================================
# MAIN KEYBOARD
# =========================================================

def main_keyboard():

    keyboard = [

        [
            "📋 PAIRS"
        ],

        [
            "⏱ TIMEFRAME",
            "⌛ EXPIRY"
        ],

        [
            "ℹ️ STATUS"
        ],

    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    settings = get_settings(
        update.effective_user.id
    )

    if not settings["timeframe"]:

        settings["timeframe"] = (
            DEFAULT_TIMEFRAME
        )

    if not settings["expiry"]:

        settings["expiry"] = (
            DEFAULT_EXPIRY
        )

    await update.message.reply_text(

        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 NAASIRFX AI SIGNAL\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👋 Soo dhawoow.\n\n"
        "📋 PAIRS ka dooro Pair.\n"
        "⏱ TIMEFRAME ka dooro Timeframe.\n"
        "⌛ EXPIRY ka dooro Expiry.\n\n"
        "📌 Marka Pair la taabto,\n"
        "signal-ka si toos ah ayuu u soo baxayaa.",

        reply_markup=main_keyboard()
    )


# =========================================================
# PAIRS CATEGORY MENU
# =========================================================

async def show_pair_categories(
    update: Update
):

    keyboard = [

        [
            "💱 FOREX",
            "💱 FOREX OTC"
        ],

        [
            "📈 STOCKS",
            "📈 STOCKS OTC"
        ],

        [
            "🔙 BACK"
        ],

    ]

    await update.message.reply_text(

        "📋 PAIRS\n\n"
        "Dooro market-ka:",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# =========================================================
# PAIR MENU
# =========================================================

async def show_pairs(
    update: Update,
    category_name
):

    settings = get_settings(
        update.effective_user.id
    )

    settings["category"] = (
        category_name
    )

    assets = CATEGORIES.get(
        category_name,
        {}
    )

    if not assets:

        await update.message.reply_text(
            "❌ Pairs lama helin.",
            reply_markup=main_keyboard()
        )

        return

    names = list(
        assets.keys()
    )

    keyboard = make_rows(
        names,
        2
    )

    keyboard.append([
        "🔙 BACK"
    ])

    await update.message.reply_text(

        f"{category_name}\n\n"
        f"📊 {len(names)} Pairs\n\n"
        "💱 Dooro Pair-ka:\n\n"
        "📌 Pair-ka markaad taabato "
        "signal-ka isla markiiba ayuu soo baxayaa.",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# =========================================================
# TIMEFRAME MENU
# =========================================================

async def show_timeframes(
    update: Update
):

    settings = get_settings(
        update.effective_user.id
    )

    current = timeframe_name(
        settings["timeframe"]
    )

    keyboard = make_rows(
        list(TIMEFRAMES.keys()),
        2
    )

    keyboard.append([
        "🔙 BACK"
    ])

    await update.message.reply_text(

        "⏱ TIMEFRAME\n\n"
        f"Current: {current}\n\n"
        "Dooro Timeframe-ka:",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# =========================================================
# EXPIRY MENU
# =========================================================

async def show_expiries(
    update: Update
):

    settings = get_settings(
        update.effective_user.id
    )

    current = expiry_name(
        settings["expiry"]
    )

    keyboard = make_rows(
        list(EXPIRIES.keys()),
        2
    )

    keyboard.append([
        "🔙 BACK"
    ])

    await update.message.reply_text(

        "⌛ EXPIRY\n\n"
        f"Current: {current}\n\n"
        "Dooro Expiry-ga:\n"
        "📌 Expiry-ga Timeframe-ka "
        "ma beddelayo.",

        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# =========================================================
# SEND SIGNAL WHEN PAIR IS TAPPED
# =========================================================

async def send_pair_signal(
    update: Update,
    asset_name
):

    user_id = (
        update.effective_user.id
    )

    settings = get_settings(
        user_id
    )

    category = settings.get(
        "category"
    )

    if not category:

        await update.message.reply_text(
            "❌ Marka hore 📋 PAIRS ka dooro category."
        )

        return

    assets = CATEGORIES.get(
        category,
        {}
    )

    asset_code = assets.get(
        asset_name
    )

    if not asset_code:

        await update.message.reply_text(
            "❌ Pair-kan lama aqoonsan."
        )

        return

    timeframe = settings.get(
        "timeframe"
    )

    expiry = settings.get(
        "expiry"
    )

    if not timeframe:

        await update.message.reply_text(
            "❌ Marka hore ⏱ TIMEFRAME dooro."
        )

        return

    if not expiry:

        await update.message.reply_text(
            "❌ Marka hore ⌛ EXPIRY dooro."
        )

        return

    # -----------------------------------------------------
    # LOADING MESSAGE
    # -----------------------------------------------------

    loading = await update.message.reply_text(

        "⏳ Signal-ka waa la baarayaa...\n\n"
        f"💱 {asset_name}\n"
        f"⏱ {timeframe_name(timeframe)}\n"
        f"⌛ {expiry_name(expiry)}"
    )

    try:

        signal = await get_signal(

            asset_code=asset_code,

            timeframe=timeframe,

            display_asset=asset_name,

            expiry=expiry
        )

        # Delete loading message
        try:

            await loading.delete()

        except Exception:

            pass

        # -------------------------------------------------
        # FULL SIGNAL PANEL
        # -------------------------------------------------

        await update.message.reply_text(
            signal
        )

    except Exception as e:

        try:

            await loading.delete()

        except Exception:

            pass

        await update.message.reply_text(

            "❌ SIGNAL ERROR\n\n"
            f"{type(e).__name__}: {str(e)}"

        )


# =========================================================
# STATUS
# =========================================================

async def show_status(
    update: Update
):

    settings = get_settings(
        update.effective_user.id
    )

    token_status = (
        "🟢 OK"
        if TOKEN
        else "🔴 MISSING"
    )

    ssid_status = (
        "🟢 OK"
        if PO_SSID
        else "🔴 MISSING"
    )

    gemini_status = (
        "🟢 OK"
        if GEMINI_API_KEY
        else "🔴 MISSING"
    )

    total_forex = len(
        FOREX_PAIRS
    )

    total_otc = len(
        FOREX_OTC_PAIRS
    )

    total_stocks = len(
        STOCK_NAMES
    )

    total_stocks_otc = len(
        STOCK_OTC_NAMES
    )

    await update.message.reply_text(

        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 NAASIRFX STATUS\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🤖 Telegram Token: {token_status}\n"
        f"🔐 Pocket Option: {ssid_status}\n"
        f"🧠 Gemini AI: {gemini_status}\n\n"

        f"💱 Forex: {total_forex}\n"
        f"💱 Forex OTC: {total_otc}\n"
        f"📈 Stocks: {total_stocks}\n"
        f"📈 Stocks OTC: {total_stocks_otc}\n\n"

        f"⏱ Timeframe: "
        f"{timeframe_name(settings['timeframe'])}\n"

        f"⌛ Expiry: "
        f"{expiry_name(settings['expiry'])}\n\n"

        "⚠️ SIGNAL ONLY\n"
        "━━━━━━━━━━━━━━━━━━━━",

        reply_markup=main_keyboard()
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:

        return

    text = (
        update.message.text
        or ""
    ).strip()

    user_id = (
        update.effective_user.id
    )

    settings = get_settings(
        user_id
    )

    # =====================================================
    # MAIN MENU
    # =====================================================

    if text == "📋 PAIRS":

        await show_pair_categories(
            update
        )

        return

    if text == "⏱ TIMEFRAME":

        await show_timeframes(
            update
        )

        return

    if text == "⌛ EXPIRY":

        await show_expiries(
            update
        )

        return

    if text == "ℹ️ STATUS":

        await show_status(
            update
        )

        return
    # =====================================================
    # BACK
    # =====================================================

    if text == "🔙 BACK":

        await update.message.reply_text(

            "🏠 Main Menu",

            reply_markup=main_keyboard()
        )

        return

    # =====================================================
    # CATEGORY
    # =====================================================

    if text in CATEGORIES:

        await show_pairs(
            update,
            text
        )

        return

    # =====================================================
    # TIMEFRAME
    # =====================================================

    if text in TIMEFRAMES:

        settings["timeframe"] = (
            TIMEFRAMES[text]
        )

        await update.message.reply_text(

            "✅ TIMEFRAME WAA LA DOORTAY\n\n"
            f"⏱ {timeframe_name(settings['timeframe'])}\n\n"
            "⌛ Expiry-ga isma beddelin.",

            reply_markup=main_keyboard()
        )

        return

    # =====================================================
    # EXPIRY
    # =====================================================

    if text in EXPIRIES:

        settings["expiry"] = (
            EXPIRIES[text]
        )

        await update.message.reply_text(

            "✅ EXPIRY WAA LA DOORTAY\n\n"
            f"⌛ {expiry_name(settings['expiry'])}\n\n"
            "⏱ Timeframe-ka isma beddelin.",

            reply_markup=main_keyboard()
        )

        return

    # =====================================================
    # PAIR
    # =====================================================

    category = settings.get(
        "category"
    )

    if category:

        assets = CATEGORIES.get(
            category,
            {}
        )

        if text in assets:

            # IMPORTANT:
            # Pair tap = immediate signal.
            await send_pair_signal(
                update,
                text
            )

            return

    # =====================================================
    # UNKNOWN
    # =====================================================

    await update.message.reply_text(

        "❌ Fadlan isticmaal buttons-ka hoose.",

        reply_markup=main_keyboard()
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"NaasirFx is running"
        )

    def log_message(
        self,
        format,
        *args
    ):

        return


def run_web_server():

    server = HTTPServer(
        (
            "0.0.0.0",
            PORT
        ),
        HealthHandler
    )

    print(
        f"🟢 HTTP SERVER RUNNING "
        f"0.0.0.0:{PORT}",
        flush=True
    )

    server.serve_forever()


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "━━━━━━━━━━━━━━━━━━━━",
        flush=True
    )

    print(
        "🤖 NAASIRFX BOT STARTING",
        flush=True
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━",
        flush=True
    )

    if TOKEN:

        print(
            "🟢 TELEGRAM_BOT_TOKEN: FOUND",
            flush=True
        )

    else:

        print(
            "🔴 TELEGRAM_BOT_TOKEN: MISSING",
            flush=True
        )

        return

    if PO_SSID:

        print(
            "🟢 POCKET OPTION SSID: FOUND",
            flush=True
        )

    else:

        print(
            "🔴 POCKET OPTION SSID: MISSING",
            flush=True
        )

    if GEMINI_API_KEY:

        print(
            "🟢 GEMINI_API_KEY: FOUND",
            flush=True
        )

    else:

        print(
            "🟡 GEMINI_API_KEY: MISSING",
            flush=True
        )

    # -----------------------------------------------------
    # RENDER HEALTH
    # -----------------------------------------------------

    health_thread = Thread(
        target=run_web_server,
        daemon=True
    )

    health_thread.start()

    # -----------------------------------------------------
    # TELEGRAM
    # -----------------------------------------------------

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler
        )
    )

    print(
        "🟢 NAASIRFX BOT IS RUNNING",
        flush=True
    )

    print(
        "📌 Pair tap = immediate signal",
        flush=True
    )

    print(
        "📌 Full signal panel enabled",
        flush=True
    )

    app.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()     
