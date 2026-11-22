import os
import asyncio
import json
import re
import inspect
import time
import logging

from datetime import datetime, timezone
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pandas as pd
import requests

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from pocketoptionapi_async import AsyncPocketOptionClient


# ==========================================
# NASIRFX AI SIGNAL
# ==========================================

BOT_NAME = "NASIRFX AI SIGNAL"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ==========================================
# ENVIRONMENT VARIABLES
# ==========================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

POCKET_OPTION_SSID = (
    os.getenv("POCKET_OPTION_SSID")
    or os.getenv("PO_SSID")
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# ==========================================
# SAFETY SETTINGS
# ==========================================

IS_DEMO = True

AUTO_TRADING = False
BACKTESTING = False

SIGNAL_ONLY = True

# Automatic and Manual signals are enabled.
MANUAL_MODE_ENABLED = True
AUTOMATIC_MODE_ENABLED = True


# ==========================================
# CONNECTION SETTINGS
# ==========================================

CONNECT_TIMEOUT = 40
CANDLE_TIMEOUT = 30

CANDLE_COUNT = 100

AI_MODEL = "gemini-2.5-flash-lite"


# ==========================================
# TIMEFRAMES
# ==========================================

TIMEFRAMES = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
}


# ==========================================
# EXPIRY TIMES
# ==========================================

EXPIRIES = {
    "1m": 60,
    "2m": 120,
    "3m": 180,
    "5m": 300,
    "10m": 600,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
}


# ==========================================
# HIGHER TIMEFRAME CONFIRMATION
# ==========================================

HIGHER_TIMEFRAME = {
    "1m": "3m",
    "3m": "5m",
    "5m": "15m",
    "15m": "30m",
    "30m": "1h",
    "1h": "4h",
    "4h": "4h",
}


# ==========================================
# CNY OTC ASSET IDs
# ==========================================

CNY_OTC_ASSETS = {
    "AEDCNY_otc": 538,
    "BHDCNY_otc": 536,
    "JODCNY_otc": 546,
    "OMRCNY_otc": 544,
    "QARCNY_otc": 542,
    "SARCNY_otc": 540,
}


# ==========================================
# LIVE SIGNAL SETTINGS
# ==========================================

MINIMUM_CANDLES = 55

MINIMUM_CONFIRMATIONS = 4

SIGNAL_COOLDOWN_SECONDS = 180

MAX_TICK_AGE_SECONDS = 5


# ==========================================
# AUTOMATIC MODE STATE
# ==========================================

AUTO_USERS = set()

AUTO_SCAN_RUNNING = False

AUTO_SCAN_INTERVAL = 15

LAST_SENT_SIGNALS = {}


# ==========================================
# USER SESSION STATE
# ==========================================

USER_SESSIONS = {}


# ==========================================
# SIGNAL SAFETY LABELS
# ==========================================

AUTO_TRADING_LABEL = "🚫 Auto-trading: OFF"

BACKTESTING_LABEL = "🚫 Backtesting: OFF"

SIGNAL_MODE_LABEL = "📡 Signal-only"


# ==========================================
# RENDER HEALTH SERVER
# ==========================================

PORT = int(os.getenv("PORT", "10000"))

# ==========================================
# PART 2 — MARKETS AND ASSET MANAGEMENT
# ==========================================

CATEGORIES = {
    "📈 FOREX": {
        "EUR/USD": "EURUSD",
        "GBP/USD": "GBPUSD",
        "USD/JPY": "USDJPY",
        "USD/CHF": "USDCHF",
        "AUD/USD": "AUDUSD",
        "NZD/USD": "NZDUSD",
        "USD/CAD": "USDCAD",
        "EUR/GBP": "EURGBP",
        "EUR/JPY": "EURJPY",
        "EUR/CHF": "EURCHF",
        "EUR/AUD": "EURAUD",
        "EUR/CAD": "EURCAD",
        "GBP/JPY": "GBPJPY",
        "GBP/CHF": "GBPCHF",
        "AUD/JPY": "AUDJPY",
        "AUD/CAD": "AUDCAD",
        "CAD/JPY": "CADJPY",
        "CHF/JPY": "CHFJPY",
    },

    "🌐 FOREX OTC": {
        "EUR/USD OTC": "EURUSD_otc",
        "GBP/USD OTC": "GBPUSD_otc",
        "USD/JPY OTC": "USDJPY_otc",
        "USD/CHF OTC": "USDCHF_otc",
        "AUD/USD OTC": "AUDUSD_otc",
        "NZD/USD OTC": "NZDUSD_otc",
        "USD/CAD OTC": "USDCAD_otc",
        "EUR/GBP OTC": "EURGBP_otc",
        "EUR/JPY OTC": "EURJPY_otc",
        "EUR/CHF OTC": "EURCHF_otc",
        "EUR/AUD OTC": "EURAUD_otc",
        "EUR/CAD OTC": "EURCAD_otc",
        "GBP/JPY OTC": "GBPJPY_otc",
        "GBP/CHF OTC": "GBPCHF_otc",
        "AUD/JPY OTC": "AUDJPY_otc",
        "AUD/CAD OTC": "AUDCAD_otc",
        "CAD/JPY OTC": "CADJPY_otc",
        "CHF/JPY OTC": "CHFJPY_otc",
        "AED/CNY OTC": "AEDCNY_otc",
        "BHD/CNY OTC": "BHDCNY_otc",
        "JOD/CNY OTC": "JODCNY_otc",
        "OMR/CNY OTC": "OMRCNY_otc",
        "QAR/CNY OTC": "QARCNY_otc",
        "SAR/CNY OTC": "SARCNY_otc",
    },

    "🍎 STOCKS": {
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "Amazon": "AMZN",
        "Google": "GOOGL",
        "Tesla": "TSLA",
        "NVIDIA": "NVDA",
        "Meta": "META",
        "Netflix": "NFLX",
    },

    "🍎 STOCKS OTC": {
        "Apple OTC": "AAPL_otc",
        "Microsoft OTC": "MSFT_otc",
        "Amazon OTC": "AMZN_otc",
        "Google OTC": "GOOGL_otc",
        "Tesla OTC": "TSLA_otc",
        "NVIDIA OTC": "NVDA_otc",
        "Meta OTC": "META_otc",
        "Netflix OTC": "NFLX_otc",
    },
}


# ==========================================
# BUTTON ROW BUILDER
# ==========================================

def button_rows(items, row_size=2):
    items = list(items)
    return [
        items[i:i + row_size]
        for i in range(0, len(items), row_size)
    ]


# ==========================================
# POCKET OPTION CONNECTION
# ==========================================

async def connect_client():
    if not POCKET_OPTION_SSID:
        raise RuntimeError(
            "POCKET_OPTION_SSID is missing in Render Environment."
        )

    client = AsyncPocketOptionClient(POCKET_OPTION_SSID)

    result = client.connect()

    if inspect.isawaitable(result):
        await asyncio.wait_for(
            result,
            timeout=CONNECT_TIMEOUT
        )

    logger.info("Pocket Option connection requested.")

    return client


# ==========================================
# DISCONNECT CLIENT
# ==========================================

async def disconnect_client(client):
    if client is None:
        return

    try:
        result = client.disconnect()

        if inspect.isawaitable(result):
            await result

    except Exception as exc:
        logger.warning("Disconnect warning: %s", exc)


# ==========================================
# ASSET VARIANTS
# ==========================================

def get_asset_variants(asset_code):
    variants = [
        asset_code,
        asset_code.upper(),
        asset_code.lower(),
    ]

    if asset_code.endswith("_otc"):
        base = asset_code[:-4]
        variants.extend([
            base + "_OTC",
            base.upper() + "_otc",
        ])

    return list(dict.fromkeys(variants))


# ==========================================
# ASSET DISCOVERY BY ID
# ==========================================

async def discover_asset_variants_by_id(client, asset_code):
    asset_id = CNY_OTC_ASSETS.get(asset_code)

    if asset_id is None:
        return get_asset_variants(asset_code)

    variants = get_asset_variants(asset_code)

    logger.info(
        "CNY OTC asset registered: %s ID=%s",
        asset_code,
        asset_id
    )

    return variants


# ==========================================
# CANDLE NORMALIZATION
# ==========================================

def normalize_candles(raw_data):
    if raw_data is None:
        return None

    if isinstance(raw_data, pd.DataFrame):
        df = raw_data.copy()

    else:
        try:
            df = pd.DataFrame(raw_data)
        except Exception:
            return None

    if df.empty:
        return None

    rename_map = {}

    for column in df.columns:
        key = str(column).lower()

        if key in ("open", "o"):
            rename_map[column] = "open"

        elif key in ("high", "h"):
            rename_map[column] = "high"

        elif key in ("low", "l"):
            rename_map[column] = "low"

        elif key in ("close", "c", "price"):
            rename_map[column] = "close"

        elif key in ("volume", "v"):
            rename_map[column] = "volume"

        elif key in ("time", "timestamp", "at", "from"):
            rename_map[column] = "time"

    df = df.rename(columns=rename_map)

    required = ["open", "high", "low", "close"]

    if not all(column in df.columns for column in required):
        return None

    for column in required:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(subset=required)

    if len(df) == 0:
        return None

    if "time" in df.columns:
        df = df.sort_values("time")

    return df.reset_index(drop=True)


# ==========================================
# CANDLE FRESHNESS CHECK
# ==========================================

def candle_is_current_or_recent(df, timeframe_seconds):
    if df is None or len(df) == 0:
        return False

    if "time" not in df.columns:
        return True

    try:
        latest = pd.to_datetime(
            df["time"].iloc[-1],
            unit="s",
            utc=True
        )

        now = pd.Timestamp.now(tz="UTC")

        age = (now - latest).total_seconds()

        return age <= timeframe_seconds * 3

    except Exception:
        return True


# ==========================================
# FLEXIBLE CANDLE API
# ==========================================

async def call_candle_method(
    client,
    asset_code,
    timeframe_seconds,
    count
):
    method_names = [
        "get_candles",
        "get_candles_async",
        "get_historical_candles",
    ]

    for method_name in method_names:
        method = getattr(client, method_name, None)

        if method is None:
            continue

        attempts = [
            (
                (asset_code, timeframe_seconds, count),
                {}
            )
# ==========================================
# CANDLE NORMALIZATION — FIXED
# ==========================================

def normalize_candles(raw_data):
    if raw_data is None:
        return None

    try:
        if isinstance(raw_data, pd.DataFrame):
            df = raw_data.copy()

            if df.index.name in ("timestamp", "time", "datetime"):
                df = df.reset_index()

        else:
            rows = []

            for candle in raw_data:
                if isinstance(candle, dict):
                    rows.append(candle)
                else:
                    rows.append({
                        "open": getattr(candle, "open", None),
                        "high": getattr(candle, "high", None),
                        "low": getattr(candle, "low", None),
                        "close": getattr(candle, "close", None),
                        "volume": getattr(candle, "volume", 0),
                        "time": getattr(
                            candle,
                            "timestamp",
                            getattr(candle, "time", None)
                        )
                    })

            df = pd.DataFrame(rows)

        if df.empty:
            return None

        df.columns = [str(c).lower() for c in df.columns]

        aliases = {
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "price": "close",
            "timestamp": "time",
            "datetime": "time",
            "at": "time",
            "from": "time",
            "v": "volume",
        }

        df = df.rename(columns=aliases)

        required = ["open", "high", "low", "close"]

        if not all(c in df.columns for c in required):
            return None

        for col in required:
            df[col] = pd.to_numeric(
                df[col], errors="coerce"
            )

        df = df.dropna(subset=required)

        if "time" in df.columns:
            df["time"] = pd.to_datetime(
                df["time"],
                utc=True,
                errors="coerce",
                unit="s"
                if pd.api.types.is_numeric_dtype(df["time"])
                else None
            )

            df = df.dropna(subset=["time"])
            df = df.sort_values("time")

        return df.reset_index(drop=True)

    except Exception as exc:
        logger.exception("Candle normalization error: %s", exc)
        return None


# ==========================================
# OFFICIAL POCKET OPTION CANDLE REQUEST
# ==========================================

async def call_candle_method(
    client,
    asset_code,
    timeframe_seconds,
    count
):
    try:
        candles = await asyncio.wait_for(
            client.get_candles(
                asset=asset_code,
                timeframe=timeframe_seconds,
                count=count
            ),
            timeout=CANDLE_TIMEOUT
        )

        df = normalize_candles(candles)

        if df is None:
            logger.warning(
                "Invalid candle format: %s",
                asset_code
            )
            return None

        if len(df) < MINIMUM_CANDLES:
            logger.warning(
                "%s: only %s candles received",
                asset_code,
                len(df)
            )
            return None

        logger.info(
            "LIVE candles received: %s | %s candles",
            asset_code,
            len(df)
        )

        return df

    except Exception as exc:
        logger.warning(
            "Candle request failed: %s | %s",
            asset_code,
            exc
        )
        return None


# ==========================================
# GET CANDLES
# ==========================================

async def get_candles(
    client,
    asset_code,
    timeframe_seconds,
    count=CANDLE_COUNT
):
    df = await call_candle_method(
        client,
        asset_code,
        timeframe_seconds,
        count
    )

    if df is None:
        logger.error(
            "NO LIVE CANDLE DATA: %s",
            asset_code
        )
        return None

    return df
    
# ==========================================
# PART 3 — TECHNICAL ANALYSIS ENGINE
# ==========================================

# ==========================================
# RSI — WILDER METHOD
# ==========================================

def calculate_rsi(series, period=14):
    series = pd.to_numeric(series, errors="coerce")

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    rsi = rsi.where(avg_loss != 0, 100)

    rsi = rsi.where(avg_gain != 0, 0)

    return rsi


# ==========================================
# EMA
# ==========================================

def calculate_ema(series, period):
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


# ==========================================
# TECHNICAL INDICATORS
# ==========================================

def add_indicators(df):
    if df is None or len(df) < MINIMUM_CANDLES:
        return None

    data = df.copy()

    data["EMA_9"] = calculate_ema(
        data["close"], 9
    )

    data["EMA_21"] = calculate_ema(
        data["close"], 21
    )

    data["EMA_50"] = calculate_ema(
        data["close"], 50
    )

    data["RSI"] = calculate_rsi(
        data["close"], 14
    )

    data["CANDLE_BODY"] = (
        data["close"] - data["open"]
    )

    data["CANDLE_RANGE"] = (
        data["high"] - data["low"]
    )

    data["BODY_PERCENT"] = (
        data["CANDLE_BODY"].abs()
        / data["CANDLE_RANGE"].replace(0, np.nan)
    )

    data["ATR"] = (
        data["high"] - data["low"]
    ).rolling(14).mean()

    return data.dropna().reset_index(drop=True)


# ==========================================
# TREND ANALYSIS
# ==========================================

def analyze_trend(df):
    data = add_indicators(df)

    if data is None or len(data) < 5:
        return "UNKNOWN", []

    current = data.iloc[-1]

    ema9 = current["EMA_9"]
    ema21 = current["EMA_21"]
    ema50 = current["EMA_50"]

    confirmations = []

    if ema9 > ema21:
        confirmations.append("EMA 9 > EMA 21")
    elif ema9 < ema21:
        confirmations.append("EMA 9 < EMA 21")

    if ema21 > ema50:
        confirmations.append("EMA 21 > EMA 50")
    elif ema21 < ema50:
        confirmations.append("EMA 21 < EMA 50")

    if current["close"] > ema50:
        confirmations.append("Price above EMA 50")
    elif current["close"] < ema50:
        confirmations.append("Price below EMA 50")

    if (
        ema9 > ema21 > ema50
        and current["close"] > ema9
    ):
        return "HIGHER", confirmations

    if (
        ema9 < ema21 < ema50
        and current["close"] < ema9
    ):
        return "LOWER", confirmations

    return "SIDEWAYS", confirmations


# ==========================================
# RSI CONFIRMATION
# ==========================================

def analyze_rsi(df):
    data = add_indicators(df)

    if data is None:
        return "UNKNOWN", None

    rsi = float(data.iloc[-1]["RSI"])

    # Strong direction confirmation.
    # Avoid entering extreme overbought/oversold zones.

    if 52 <= rsi <= 68:
        return "HIGHER", rsi

    if 32 <= rsi <= 48:
        return "LOWER", rsi

    return "NEUTRAL", rsi


# ==========================================
# CANDLE DIRECTION
# ==========================================

def analyze_candle(df):
    if df is None or len(df) < 3:
        return "UNKNOWN"

    candle = df.iloc[-1]

    if candle["close"] > candle["open"]:
        return "HIGHER"

    if candle["close"] < candle["open"]:
        return "LOWER"

    return "NEUTRAL"


# ==========================================
# PREVIOUS CANDLE CONFIRMATION
# ==========================================

def analyze_previous_candle(df):
    if df is None or len(df) < 3:
        return "UNKNOWN"

    candle = df.iloc[-2]

    if candle["close"] > candle["open"]:
        return "HIGHER"

    if candle["close"] < candle["open"]:
        return "LOWER"

    return "NEUTRAL"


# ==========================================
# SUPPORT AND RESISTANCE
# ==========================================

def calculate_support_resistance(df, lookback=30):
    if df is None or len(df) < lookback:
        return None, None

    recent = df.tail(lookback)

    support = float(recent["low"].min())

    resistance = float(recent["high"].max())

    return support, resistance


# ==========================================
# SUPPORT / RESISTANCE FILTER
# ==========================================

def support_resistance_filter(
    df,
    direction,
    distance_percent=0.001
):
    support, resistance = calculate_support_resistance(df)

    if support is None or resistance is None:
        return False

    price = float(df.iloc[-1]["close"])

    if price <= 0:
        return False

    distance_support = abs(price - support) / price

    distance_resistance = abs(resistance - price) / price

    if direction == "HIGHER":
        # Avoid buying directly into resistance.
        return distance_resistance > distance_percent

    if direction == "LOWER":
        # Avoid selling directly into support.
        return distance_support > distance_percent

    return False


# ==========================================
# HIGHER TIMEFRAME CONFIRMATION
# ==========================================

async def get_higher_timeframe_direction(
    client,
    asset_code,
    timeframe_name
):
    higher_name = HIGHER_TIMEFRAME.get(
        timeframe_name
    )

    if not higher_name:
        return "UNKNOWN"

    higher_seconds = TIMEFRAMES.get(higher_name)

    if not higher_seconds:
        return "UNKNOWN"

    df = await get_candles(
        client,
        asset_code,
        higher_seconds,
        CANDLE_COUNT
    )

    if df is None:
        return "UNKNOWN"

    direction, _ = analyze_trend(df)

    return direction


# ==========================================
# CONFIRMATION SCORE
# ==========================================

def calculate_confirmation_score(
    direction,
    confirmations
):
    if direction not in ("HIGHER", "LOWER"):
        return 0

    count = len(confirmations)

    score_map = {
        0: 0,
        1: 20,
        2: 40,
        3: 60,
        4: 80,
        5: 100,
    }

    return score_map.get(count, 100)


# ==========================================
# ULTRA CONFIRMATION ENGINE
# ==========================================

def ultra_confirmation(
    trend,
    rsi_direction,
    current_candle,
    previous_candle,
    higher_trend,
    df
):
    confirmations = []

    if trend == "UNKNOWN":
        return "WAIT", [], 0

    # 1 — Main trend
    if trend in ("HIGHER", "LOWER"):
        confirmations.append("Main trend confirmed")

    # 2 — RSI
    if rsi_direction == trend:
        confirmations.append("RSI confirmed")

    # 3 — Current candle
    if current_candle == trend:
        confirmations.append("Current candle confirmed")

    # 4 — Previous candle
    if previous_candle == trend:
        confirmations.append("Previous candle confirmed")

    # 5 — Higher timeframe
    if higher_trend == trend:
        confirmations.append("Higher timeframe confirmed")

    score = calculate_confirmation_score(
        trend,
        confirmations
    )

    # All five checks are considered.
    # At least four must agree.

    if len(confirmations) < MINIMUM_CONFIRMATIONS:
        return "WAIT", confirmations, score

    if not support_resistance_filter(
        df,
        trend
    ):
        return "WAIT", confirmations, score

    return trend, confirmations, score


# ==========================================
# ANALYSIS SUMMARY
# ==========================================

def build_analysis_summary(
    direction,
    confirmations,
    score,
    rsi_value
):
    if direction == "HIGHER":
        label = "🟢 HIGHER"

    elif direction == "LOWER":
        label = "🔴 LOWER"

    else:
        label = "⏳ WAIT"

    confirmation_text = "\n".join(
        f"✅ {item}" for item in confirmations
    )

    if not confirmation_text:
        confirmation_text = "⚠️ Confirmation not sufficient"

    rsi_text = (
        f"{rsi_value:.2f}"
        if rsi_value is not None
        else "Unavailable"
    )

    return (
        f"📊 Direction: {label}\n"
        f"📈 RSI: {rsi_text}\n"
        f"🧠 Confirmation score: {score}%\n\n"
        f"🔎 Confirmation details:\n"
        f"{confirmation_text}\n\n"
        f"🚫 Auto-trading: OFF\n"
        f"🚫 Backtesting: OFF\n"
        f"📡 Signal-only"
)
 
# ==========================================
# PART 4 — SIGNAL GENERATION ENGINE
# ==========================================

# ==========================================
# GEMINI AI ANALYSIS
# ==========================================

async def gemini_analysis(
    asset,
    timeframe,
    direction,
    confirmations,
    rsi_value,
    price
):
    if not GEMINI_API_KEY:
        return "Gemini API key not configured."

    prompt = f"""
You are NASIRFX AI market analysis assistant.

Analyze this LIVE technical signal.

Asset: {asset}
Timeframe: {timeframe}
Direction: {direction}
Price: {price}
RSI: {rsi_value}
Confirmations: {confirmations}

Rules:
- Do not invent market data.
- Do not change HIGHER or LOWER into a trade instruction.
- Explain the technical confirmations briefly.
- If direction is WAIT, explain that confirmation is insufficient.
- Do not claim guaranteed accuracy.
- Do not execute trades.
"""

    try:
        response = await asyncio.to_thread(
            requests.post,
            (
                "https://generativelanguage.googleapis.com/"
                "v1beta/models/"
                f"{AI_MODEL}:generateContent"
            ),
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            },
            timeout=20
        )

        response.raise_for_status()

        result = response.json()

        return (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

    except Exception as exc:
        logger.warning("Gemini error: %s", exc)

        return "AI explanation unavailable."


# ==========================================
# SIGNAL PANEL
# ==========================================

def build_signal_panel(
    asset,
    timeframe,
    expiry,
    direction,
    price,
    rsi_value,
    confirmations,
    score,
    ai_text=""
):
    if direction == "HIGHER":
        signal_label = "🟢 HIGHER"

    elif direction == "LOWER":
        signal_label = "🔴 LOWER"

    else:
        signal_label = "⏳ WAIT"

    confirmation_lines = "\n".join(
        f"✅ {item}"
        for item in confirmations
    )

    if not confirmation_lines:
        confirmation_lines = "⚠️ No sufficient confirmations"

    rsi_text = (
        f"{rsi_value:.2f}"
        if rsi_value is not None
        else "Unavailable"
    )

    message = f"""
━━━━━━━━━━━━━━━━━━━━
       NASIRFX AI SIGNAL
━━━━━━━━━━━━━━━━━━━━

💱 Asset: {asset}

📊 Timeframe: {timeframe}
⏳ Expiry: {expiry}

🎯 SIGNAL: {signal_label}

💰 Analysis price: {price}

📈 RSI: {rsi_text}

🧠 Confirmation score: {score}%

━━━━━━━━━━━━━━━━━━━━
       ULTRA CONFIRMATION
━━━━━━━━━━━━━━━━━━━━

{confirmation_lines}

━━━━━━━━━━━━━━━━━━━━
       AI ANALYSIS
━━━━━━━━━━━━━━━━━━━━

{ai_text}

━━━━━━━━━━━━━━━━━━━━

📡 Data source: Pocket Option API
🚫 Auto-trading: OFF
🚫 Backtesting: OFF
🔒 Signal-only mode

⚠️ Signals are not guaranteed.
━━━━━━━━━━━━━━━━━━━━
"""

    return message.strip()


# ==========================================
# GET SIGNAL
# ==========================================

async def get_signal(
    asset_code,
    timeframe_name,
    expiry_name,
    client=None
):
    own_client = client is None

    if own_client:
        client = await connect_client()

    try:
        timeframe_seconds = TIMEFRAMES.get(
            timeframe_name
        )

        if not timeframe_seconds:
            return None

        if expiry_name not in EXPIRIES:
            return None

        # Main timeframe candles
        df = await get_candles(
            client,
            asset_code,
            timeframe_seconds,
            CANDLE_COUNT
        )

        if df is None or len(df) < MINIMUM_CANDLES:
            logger.info(
                "Insufficient candles: %s",
                asset_code
            )
            return None

        # Technical indicators
        trend, trend_details = analyze_trend(df)

        rsi_direction, rsi_value = analyze_rsi(df)

        current_candle = analyze_candle(df)

        previous_candle = analyze_previous_candle(df)

        # Higher timeframe
        higher_trend = await get_higher_timeframe_direction(
            client,
            asset_code,
            timeframe_name
        )

        # Ultra confirmation
        direction, confirmations, score = ultra_confirmation(
            trend,
            rsi_direction,
            current_candle,
            previous_candle,
            higher_trend,
            df
        )

        # Latest available candle close
        price = float(df.iloc[-1]["close"])

        # Gemini explanation only.
        # Gemini cannot override technical direction.
        ai_text = await gemini_analysis(
            asset_code,
            timeframe_name,
            direction,
            confirmations,
            rsi_value,
            price
        )

        message = build_signal_panel(
            asset=asset_code,
            timeframe=timeframe_name,
            expiry=expiry_name,
            direction=direction,
            price=price,
            rsi_value=rsi_value,
            confirmations=confirmations,
            score=score,
            ai_text=ai_text
        )

        return {
            "asset": asset_code,
            "timeframe": timeframe_name,
            "expiry": expiry_name,
            "direction": direction,
            "price": price,
            "rsi": rsi_value,
            "confirmations": confirmations,
            "score": score,
            "message": message,
            "timestamp": time.time(),
        }

    except Exception as exc:
        logger.exception(
            "Signal generation failed for %s: %s",
            asset_code,
            exc
        )
        return None

    finally:
        if own_client:
            await disconnect_client(client)


# ==========================================
# SIGNAL DUPLICATE PROTECTION
# ==========================================

def signal_is_duplicate(
    user_id,
    asset,
    timeframe,
    direction
):
    key = (
        user_id,
        asset,
        timeframe,
        direction
    )

    now = time.time()

    previous = LAST_SENT_SIGNALS.get(key, 0)

    if now - previous < SIGNAL_COOLDOWN_SECONDS:
        return True

    LAST_SENT_SIGNALS[key] = now

    return False


# ==========================================
# SEND VALID SIGNAL
# ==========================================

async def send_signal_to_user(
    context,
    user_id,
    signal
):
    if not signal:
        return False

    if signal["direction"] not in ("HIGHER", "LOWER"):
        return False

    if len(signal["confirmations"]) < MINIMUM_CONFIRMATIONS:
        return False

    if signal_is_duplicate(
        user_id,
        signal["asset"],
        signal["timeframe"],
        signal["direction"]
    ):
        return False

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=signal["message"]
        )

        return True

    except Exception as exc:
        logger.warning(
            "Telegram send failed for %s: %s",
            user_id,
            exc
        )

        return False
        
# ==========================================
# PART 5 — TELEGRAM BOT AND USER INTERFACE
# ==========================================

# ==========================================
# MAIN MENU
# ==========================================

def main_menu():
    keyboard = [
        ["📡 MANUAL MODE", "🤖 AUTOMATIC MODE"],
        ["▶️ START AUTOMATIC", "⏹ STOP AUTOMATIC"],
        ["📊 FOREX", "🌐 FOREX OTC"],
        ["🍎 STOCKS", "🍎 STOCKS OTC"],
        ["⚙️ SETTINGS", "ℹ️ ABOUT"],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# ==========================================
# TIMEFRAME MENU
# ==========================================

def timeframe_menu():
    return ReplyKeyboardMarkup(
        button_rows(TIMEFRAMES.keys(), 2)
        + [["🔙 BACK TO MENU"]],
        resize_keyboard=True
    )


# ==========================================
# EXPIRY MENU
# ==========================================

def expiry_menu():
    return ReplyKeyboardMarkup(
        button_rows(EXPIRIES.keys(), 2)
        + [["🔙 BACK TO MENU"]],
        resize_keyboard=True
    )


# ==========================================
# PAIR MENU
# ==========================================

def pair_menu(category):
    pairs = CATEGORIES.get(category, {})

    return ReplyKeyboardMarkup(
        button_rows(pairs.keys(), 2)
        + [["🔙 BACK TO MENU"]],
        resize_keyboard=True
    )


# ==========================================
# START COMMAND
# ==========================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    USER_SESSIONS.setdefault(
        user_id,
        {
            "mode": None,
            "category": None,
            "asset": None,
            "timeframe": None,
            "expiry": None,
        }
    )

    await update.message.reply_text(
        f"""
👋 Welcome to {BOT_NAME}

📡 LIVE MARKET SIGNALS

Choose your mode below.

📌 Manual Mode
You select the market and pair.

🤖 Automatic Mode
Bot scans available markets.

🚫 Auto-trading: OFF
🚫 Backtesting: OFF
📡 Signal-only
""",
        reply_markup=main_menu()
    )


# ==========================================
# MANUAL MODE
# ==========================================

async def manual_mode(update, context):
    user_id = update.effective_user.id

    USER_SESSIONS[user_id]["mode"] = "MANUAL"

    await update.message.reply_text(
        "📡 MANUAL MODE\n\nChoose your market:",
        reply_markup=main_menu()
    )


# ==========================================
# AUTOMATIC MODE
# ==========================================

async def automatic_mode(update, context):
    user_id = update.effective_user.id

    USER_SESSIONS[user_id]["mode"] = "AUTOMATIC"

    await update.message.reply_text(
        """
🤖 AUTOMATIC MODE

Choose START AUTOMATIC to begin scanning.

The bot will send confirmed HIGHER/LOWER
signals only.

🚫 Auto-trading: OFF
🚫 Backtesting: OFF
""",
        reply_markup=main_menu()
    )


# ==========================================
# START AUTOMATIC SCANNING
# ==========================================

async def start_automatic(update, context):
    user_id = update.effective_user.id

    AUTO_USERS.add(user_id)

    await update.message.reply_text(
        """
<escape>🤖 AUTOMATIC SCANNING ACTIVATED</escape>

📡 Market scanning enabled.

Markets:
• Forex
• Forex OTC
• Stocks
• Stocks OTC

🚫 Auto-trading: OFF
🚫 Backtesting: OFF
📡 Signal-only
""",
        reply_markup=main_menu()
    )


# ==========================================
# STOP AUTOMATIC SCANNING
# ==========================================

async def stop_automatic(update, context):
    user_id = update.effective_user.id

    AUTO_USERS.discard(user_id)

    await update.message.reply_text(
        "⏹ Automatic scanning stopped.",
        reply_markup=main_menu()
    )


# ==========================================
# MARKET SELECTION
# ==========================================

async def select_market(update, context, category):
    user_id = update.effective_user.id

    USER_SESSIONS[user_id]["category"] = category

    await update.message.reply_text(
        f"Choose pair from {category}:",
        reply_markup=pair_menu(category)
    )


# ==========================================
# PAIR SELECTION
# ==========================================

async def select_pair(update, context, pair_name):
    user_id = update.effective_user.id

    session = USER_SESSIONS.setdefault(
        user_id,
        {}
    )

    category = session.get("category")

    if not category:
        return

    asset_code = CATEGORIES[category].get(pair_name)

    if not asset_code:
        return

    session["asset"] = asset_code
    session["pair_name"] = pair_name

    await update.message.reply_text(
        f"💱 Selected: {pair_name}\n\nChoose timeframe:",
        reply_markup=timeframe_menu()
    )


# ==========================================
# TIMEFRAME SELECTION
# ==========================================

async def select_timeframe(update, context, timeframe_name):
    user_id = update.effective_user.id

    session = USER_SESSIONS.get(user_id, {})

    if timeframe_name not in TIMEFRAMES:
        return

    session["timeframe"] = timeframe_name

    await update.message.reply_text(
        f"📊 Timeframe: {timeframe_name}\n\nChoose expiry:",
        reply_markup=expiry_menu()
    )


# ==========================================
# EXPIRY SELECTION
# ==========================================

async def select_expiry(update, context, expiry_name):
    user_id = update.effective_user.id

    session = USER_SESSIONS.get(user_id, {})

    if expiry_name not in EXPIRIES:
        return

    session["expiry"] = expiry_name

    await update.message.reply_text(
        "⏳ Preparing LIVE analysis...",
        reply_markup=main_menu()
    )

    asset = session.get("asset")
    timeframe = session.get("timeframe")

    if not asset or not timeframe:
        await update.message.reply_text(
            "⚠️ Please select the pair and timeframe again."
        )
        return

    await run_manual_analysis(
        update,
        context,
        asset,
        timeframe,
        expiry_name
    )


# ==========================================
# MANUAL ANALYSIS
# ==========================================

async def run_manual_analysis(
    update,
    context,
    asset,
    timeframe,
    expiry
):
    await update.message.reply_text(
        "🔄 Connecting to Pocket Option LIVE data..."
    )

    try:
        signal = await get_signal(
            asset,
            timeframe,
            expiry
        )

        if not signal:
            await update.message.reply_text(
                "⚠️ No reliable candle data received. Try again later."
            )
            return

        if signal["direction"] == "WAIT":
            await update.message.reply_text(
                signal["message"]
            )
            return

        await update.message.reply_text(
            signal["message"]
        )

    except Exception as exc:
        logger.exception("Manual analysis error: %s", exc)

        await update.message.reply_text(
            "❌ Analysis failed. Check Pocket Option connection and logs."
        )


# ==========================================
# SETTINGS
# ==========================================

async def settings_command(update, context):
    await update.message.reply_text(
        f"""
⚙️ NASIRFX SETTINGS

Manual Mode: {'ON' if MANUAL_MODE_ENABLED else 'OFF'}

Automatic Mode: {'ON' if AUTOMATIC_MODE_ENABLED else 'OFF'}

Auto-trading: OFF
Backtesting: OFF

Signal-only: ON

Timeframes:
{', '.join(TIMEFRAMES.keys())}

Expiries:
{', '.join(EXPIRIES.keys())}
"""
    )


# ==========================================
# ABOUT
# ==========================================

async def about_command(update, context):
    await update.message.reply_text(
        """
ℹ️ NASIRFX AI SIGNAL

LIVE market analysis.

Technical indicators:
• EMA 9 / 21 / 50
• RSI 14
• Support and Resistance
• Higher timeframe trend
• Ultra Confirmation
• Gemini AI explanation

🚫 No automatic trading.
🚫 No backtesting.
📡 Signal-only.
"""
    )


# ==========================================
# TEXT MESSAGE HANDLER
# ==========================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    USER_SESSIONS.setdefault(
        user_id,
        {
            "mode": None,
            "category": None,
            "asset": None,
            "timeframe": None,
            "expiry": None,
        }
    )

    if text == "📡 MANUAL MODE":
        await manual_mode(update, context)
        return

    if text == "🤖 AUTOMATIC MODE":
        await automatic_mode(update, context)
        return

    if text == "▶️ START AUTOMATIC":
        await start_automatic(update, context)
        return

    if text == "⏹ STOP AUTOMATIC":
        await stop_automatic(update, context)
        return

    if text == "⚙️ SETTINGS":
        await settings_command(update, context)
        return

    if text == "ℹ️ ABOUT":
        await about_command(update, context)
        return

    if text == "🔙 BACK TO MENU":
        await update.message.reply_text(
            "Main menu:",
            reply_markup=main_menu()
        )
        return

    if text in CATEGORIES:
        await select_market(update, context, text)
        return

    for category, pairs in CATEGORIES.items():
        if text in pairs:
            await select_pair(update, context, text)
            return

    if text in TIMEFRAMES:
        await select_timeframe(update, context, text)
        return

    if text in EXPIRIES:
        await select_expiry(update, context, text)
        return

    await update.message.reply_text(
        "Please select an option from the menu.",
        reply_markup=main_menu()
        )
    
# ==========================================
# PART 6 — AUTOMATIC SCANNER
# ==========================================

AUTO_SCAN_INTERVAL = 15

# Prevent multiple scanner tasks
AUTO_SCAN_TASK = None

# Prevent concurrent scans of the same asset
SCANNING_LOCK = asyncio.Lock()


# ==========================================
# AUTOMATIC SCAN CONFIGURATION
# ==========================================

AUTO_TIMEFRAME = "1m"
AUTO_EXPIRY = "2m"

# Limit scanning workload per cycle.
# Increase only after confirming API capacity.
MAX_ASSETS_PER_CYCLE = 12


# ==========================================
# BUILD AUTOMATIC ASSET LIST
# ==========================================

def get_automatic_assets():
    assets = []

    for category, pairs in CATEGORIES.items():
        for pair_name, asset_code in pairs.items():
            assets.append({
                "category": category,
                "pair": pair_name,
                "asset": asset_code,
            })

    return assets


# ==========================================
# AUTOMATIC SCAN ONE ASSET
# ==========================================

async def scan_one_asset(
    client,
    context,
    asset_info,
    user_ids
):
    asset = asset_info["asset"]

    try:
        signal = await get_signal(
            asset,
            AUTO_TIMEFRAME,
            AUTO_EXPIRY,
            client=client
        )

        if not signal:
            return

        if signal["direction"] not in ("HIGHER", "LOWER"):
            return

        if len(signal["confirmations"]) < MINIMUM_CONFIRMATIONS:
            return

        for user_id in list(user_ids):
            if user_id not in AUTO_USERS:
                continue

            await send_signal_to_user(
                context,
                user_id,
                signal
            )

    except Exception as exc:
        logger.warning(
            "Automatic scan failed for %s: %s",
            asset,
            exc
        )


# ==========================================
# AUTOMATIC SCANNER LOOP
# ==========================================

async def automatic_scanner(context):
    global AUTO_SCAN_RUNNING

    AUTO_SCAN_RUNNING = True

    logger.info("NASIRFX automatic scanner started.")

    asset_list = get_automatic_assets()

    position = 0

    while AUTO_USERS:
        user_ids = list(AUTO_USERS)

        if not user_ids:
            break

        if SCANNING_LOCK.locked():
            await asyncio.sleep(2)
            continue

        async with SCANNING_LOCK:

            client = None

            try:
                client = await connect_client()

                total_assets = len(asset_list)

                batch = []

                for _ in range(
                    min(MAX_ASSETS_PER_CYCLE, total_assets)
                ):
                    if not asset_list:
                        break

                    batch.append(
                        asset_list[position % total_assets]
                    )

                    position += 1

                for asset_info in batch:

                    if not AUTO_USERS:
                        break

                    await scan_one_asset(
                        client,
                        context,
                        asset_info,
                        user_ids
                    )

                    # Avoid overloading the API
                    await asyncio.sleep(1)

            except Exception as exc:
                logger.exception(
                    "Automatic scanner connection error: %s",
                    exc
                )

            finally:
                await disconnect_client(client)

        if AUTO_USERS:
            await asyncio.sleep(AUTO_SCAN_INTERVAL)

    AUTO_SCAN_RUNNING = False

    logger.info("NASIRFX automatic scanner stopped.")


# ==========================================
# START / STOP SCANNER TASK
# ==========================================

async def ensure_scanner_running(application):
    global AUTO_SCAN_TASK

    if AUTO_USERS and (
        AUTO_SCAN_TASK is None
        or AUTO_SCAN_TASK.done()
    ):
        AUTO_SCAN_TASK = asyncio.create_task(
            automatic_scanner(application)
        )


async def scanner_startup(application):
    logger.info("NASIRFX scanner startup complete.")


async def scanner_shutdown(application):
    global AUTO_SCAN_TASK

    AUTO_USERS.clear()

    if AUTO_SCAN_TASK and not AUTO_SCAN_TASK.done():
        AUTO_SCAN_TASK.cancel()

        try:
            await AUTO_SCAN_TASK
        except asyncio.CancelledError:
            pass


# ==========================================
# AUTOMATIC START HANDLER PATCH
# ==========================================

async def start_automatic(update, context):
    user_id = update.effective_user.id

    AUTO_USERS.add(user_id)

    await ensure_scanner_running(
        context.application
    )

    await update.message.reply_text(
        """
<escape>🤖 NASIRFX AUTOMATIC SCANNER STARTED</escape>

📡 Scanning enabled.

Markets:
• Forex
• Forex OTC
• Stocks
• Stocks OTC

Signal rules:
• EMA 9 / 21 / 50
• RSI 14
• Candle direction
• Previous candle
• Higher timeframe
• Minimum 4 confirmations

🚫 Auto-trading: OFF
🚫 Backtesting: OFF
📡 Signal-only
"""
    )


# ==========================================
# RENDER HEALTH SERVER
# ==========================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path in ("/", "/health"):

            body = (
                b"NASIRFX AI SIGNAL is running"
            )

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/plain"
            )

            self.send_header(
                "Content-Length",
                str(len(body))
            )

            self.end_headers()

            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def start_health_server():
    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    logger.info(
        "Health server running on port %s",
        PORT
    )

    server.serve_forever()


# ==========================================
# RENDER HEALTH THREAD
# ==========================================

def run_health_server():
    thread = Thread(
        target=start_health_server,
        daemon=True
    )

    thread.start()


# ==========================================
# POST INIT
# ==========================================

async def post_init(application):
    logger.info("NASIRFX Telegram bot initialized.")

    await scanner_startup(application)


# ==========================================
# POST SHUTDOWN
# ==========================================

async def post_shutdown(application):
    await scanner_shutdown(application)


# ==========================================
# MAIN APPLICATION
# ==========================================

def main():

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN missing in Render Environment."
        )

    if not POCKET_OPTION_SSID:
        raise RuntimeError(
            "POCKET_OPTION_SSID missing in Render Environment."
        )

    run_health_server()

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start_command)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )

    logger.info(
        "Starting %s",
        BOT_NAME
    )

    application.run_polling(
        drop_pending_updates=True
    )


# ==========================================
# START BOT
# ==========================================

if __name__ == "__main__":
    main()
            
