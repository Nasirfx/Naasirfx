import os
import asyncio
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pandas as pd

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from pocketoptionapi_async import AsyncPocketOptionClient
from pocketoptionapi_async.constants import ASSETS


# =========================================================
# SETTINGS
# =========================================================

BOT_NAME = "NaasirFx"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POCKET_SSID = os.getenv("POCKET_OPTION_SSID")

DEFAULT_ASSET = "EURUSD_otc"

# 3 minutes
DEFAULT_TIMEFRAME = 180

# 3 minutes expiry
DEFAULT_EXPIRY = 180

# Higher timeframe = 5 minutes
HIGHER_TIMEFRAME = 300

CANDLE_COUNT = 100


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("NaasirFx")


# =========================================================
# ASSET CATALOG
# =========================================================

def load_assets():
    assets = []

    try:
        if isinstance(ASSETS, dict):

            for key, value in ASSETS.items():

                if isinstance(value, str):
                    assets.append(value)
                else:
                    assets.append(str(key))

        elif isinstance(ASSETS, (list, tuple, set)):

            for item in ASSETS:

                if isinstance(item, str):
                    assets.append(item)

                elif isinstance(item, dict):

                    symbol = (
                        item.get("symbol")
                        or item.get("asset")
                        or item.get("name")
                    )

                    if symbol:
                        assets.append(str(symbol))

    except Exception as exc:
        logger.error("ASSETS error: %s", exc)

    assets = list(dict.fromkeys(assets))

    if DEFAULT_ASSET not in assets:
        assets.insert(0, DEFAULT_ASSET)

    return assets


ASSET_CATALOG = load_assets()


# =========================================================
# USER SETTINGS
# =========================================================

USER_SETTINGS = {}


def get_settings(user_id):

    if user_id not in USER_SETTINGS:

        USER_SETTINGS[user_id] = {
            "asset": DEFAULT_ASSET,
            "timeframe": DEFAULT_TIMEFRAME,
            "expiry": DEFAULT_EXPIRY,
        }

    return USER_SETTINGS[user_id]


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain",
        )

        self.end_headers()

        self.wfile.write(
            b"NaasirFx is running"
        )

    def log_message(self, format, *args):
        return


def start_health_server():

    port = int(
        os.getenv("PORT", "10000")
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler,
    )

    logger.info(
        "Health server running on port %s",
        port,
    )

    server.serve_forever()


# =========================================================
# POCKET OPTION CONNECTION
# =========================================================

async def connect_pocket():

    if not POCKET_SSID:
        raise RuntimeError(
            "POCKET_OPTION_SSID is missing."
        )

    last_error = None

    for attempt in range(1, 4):

        try:

            logger.info(
                "Pocket Option connection %s/3",
                attempt,
            )

            client = AsyncPocketOptionClient(
                POCKET_SSID,
                is_demo=True,
            )

            result = await client.connect()

            if result is False:
                raise RuntimeError(
                    "Pocket Option connect returned False."
                )

            logger.info(
                "Pocket Option connected."
            )

            return client

        except Exception as exc:

            last_error = exc

            logger.error(
                "Connection %s failed: %s",
                attempt,
                exc,
            )

            if attempt < 3:
                await asyncio.sleep(5)

    raise RuntimeError(
        "Pocket Option connection failed. "
        f"Last error: {last_error}"
    )


# =========================================================
# GET CANDLES
# =========================================================

async def get_candles(
    asset,
    timeframe,
    count=CANDLE_COUNT,
):

    client = None

    try:

        client = await connect_pocket()

        candles = await client.get_candles(
            asset,
            timeframe,
            count,
        )

        if not candles:

            raise RuntimeError(
                f"No candle data for {asset}"
            )

        return candles

    finally:

        if client is not None:

            try:
                await client.disconnect()

            except Exception:
                pass


# =========================================================
# CANDLES -> DATAFRAME
# =========================================================

def candles_to_dataframe(candles):

    if not candles:
        return pd.DataFrame()

    rows = []

    for candle in candles:

        # Pocket Option object format
        try:

            rows.append({
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
            })

            continue

        except Exception:
            pass

        # Dictionary backup
        if isinstance(candle, dict):

            try:

                rows.append({
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                })

            except Exception:
                pass

    return pd.DataFrame(rows)


# =========================================================
# RSI
# =========================================================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(
        period
    ).mean()

    avg_loss = loss.rolling(
        period
    ).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        float("nan"),
    )

    return 100 - (
        100 / (1 + rs)
    )


# =========================================================
# ANALYZE MAIN TIMEFRAME
# =========================================================

def analyze_main(df):

    result = {
        "trend": "WAIT",
        "rsi_signal": "WAIT",
        "rsi": None,
        "current_candle": "WAIT",
        "previous_candle": "WAIT",
        "price": None,
        "ma10": None,
        "ma50": None,
    }

    if df.empty:
        return result

    if len(df) < 50:
        return result

    df = df.copy()

    # -----------------------------------------------------
    # MA10 / MA50
    # -----------------------------------------------------

    df["MA10"] = df["close"].rolling(
        10
    ).mean()

    df["MA50"] = df["close"].rolling(
        50
    ).mean()

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    df["RSI"] = calculate_rsi(
        df["close"],
        14,
    )

    # -----------------------------------------------------
    # LAST TWO CANDLES
    # -----------------------------------------------------

    last = df.iloc[-1]
    previous = df.iloc[-2]

    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------

    if last["MA10"] > last["MA50"]:

        trend = "CALL"

    elif last["MA10"] < last["MA50"]:

        trend = "PUT"

    else:

        trend = "WAIT"

    # -----------------------------------------------------
    # RSI
    #
    # > 50 = CALL
    # < 50 = PUT
    # -----------------------------------------------------

    rsi_value = last["RSI"]

    if pd.isna(rsi_value):

        rsi_signal = "WAIT"

    elif rsi_value > 50:

        rsi_signal = "CALL"

    elif rsi_value < 50:

        rsi_signal = "PUT"

    else:

        rsi_signal = "WAIT"

    # -----------------------------------------------------
    # CURRENT CANDLE
    # -----------------------------------------------------

    if last["close"] > last["open"]:

        current_candle = "CALL"

    elif last["close"] < last["open"]:

        current_candle = "PUT"

    else:

        current_candle = "WAIT"

    # -----------------------------------------------------
    # PREVIOUS CANDLE
    # -----------------------------------------------------

    if previous["close"] > previous["open"]:

        previous_candle = "CALL"

    elif previous["close"] < previous["open"]:

        previous_candle = "PUT"

    else:

        previous_candle = "WAIT"

    return {
        "trend": trend,
        "rsi_signal": rsi_signal,
        "rsi": rsi_value,
        "current_candle": current_candle,
        "previous_candle": previous_candle,
        "price": last["close"],
        "ma10": last["MA10"],
        "ma50": last["MA50"],
    }


# =========================================================
# HIGHER TIMEFRAME ANALYSIS
# =========================================================

def analyze_higher_timeframe(df):

    if df.empty:
        return "WAIT", "WAIT"

    if len(df) < 20:
        return "WAIT", "WAIT"

    df = df.copy()

    last = df.iloc[-1]

    if last["close"] > last["open"]:

        signal = "CALL"
        candle = "Bullish"

    elif last["close"] < last["open"]:

        signal = "PUT"
        candle = "Bearish"

    else:

        signal = "WAIT"
        candle = "Doji"

    return signal, candle


# =========================================================
# FINAL CONFIRMATION
# =========================================================

def final_confirmation(
    trend,
    rsi_signal,
    current_candle,
    previous_candle,
    higher_signal,
):

    checks = [
        trend,
        rsi_signal,
        current_candle,
        previous_candle,
        higher_signal,
    ]

    call_score = checks.count("CALL")
    put_score = checks.count("PUT")

    if call_score >= 4:

        final_signal = "CALL"

    elif put_score >= 4:

        final_signal = "PUT"

    else:

        final_signal = "WAIT"

    return (
        final_signal,
        call_score,
        put_score,
    )


# =========================================================
# MAIN KEYBOARD
# =========================================================

def main_keyboard():

    keyboard = [
        [
            "📊 SIGNAL",
            "📋 ASSETS",
        ],
        [
            "⏱ TIMEFRAME",
            "⌛ EXPIRY",
        ],
        [
            "ℹ️ STATUS",
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🤖 NAASIRFX\n\n"
        "Ku soo dhawoow NaasirFx.\n\n"
        "📊 SIGNAL - Signal samee\n"
        "📋 ASSETS - Assets-ka\n"
        "⏱ TIMEFRAME - Timeframe\n"
        "⌛ EXPIRY - Expiry\n"
        "ℹ️ STATUS - Status",
        reply_markup=main_keyboard(),
    )


# =========================================================
# STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    settings = get_settings(
        update.effective_user.id
    )

    token = (
        "✅ OK"
        if TELEGRAM_TOKEN
        else "❌ Missing"
    )

    ssid = (
        "✅ OK"
        if POCKET_SSID
        else "❌ Missing"
    )

    await update.message.reply_text(
        "🤖 NAASIRFX STATUS\n\n"
        f"Telegram Token: {token}\n"
        f"Pocket Option SSID: {ssid}\n\n"
        f"📊 Asset: {settings['asset']}\n"
        f"⏱ Timeframe: {settings['timeframe']} sec\n"
        f"⌛ Expiry: {settings['expiry']} sec\n"
        f"⏱ Higher TF: {HIGHER_TIMEFRAME} sec\n\n"
        f"📋 Asset catalog: {len(ASSET_CATALOG)}",
        reply_markup=main_keyboard(),
    )


# =========================================================
# ASSETS
# =========================================================

async def assets_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not ASSET_CATALOG:

        await update.message.reply_text(
            "❌ Asset catalog lama helin."
        )

        return

    search = ""

    if context.args:

        search = " ".join(
            context.args
        ).strip().lower()

    if search:

        assets = [
            asset
            for asset in ASSET_CATALOG
            if search in asset.lower()
        ]

    else:

        assets = ASSET_CATALOG

    if not assets:

        await update.message.reply_text(
            "❌ Asset-kaas lama helin."
        )

        return

    await update.message.reply_text(
        "📋 NAASIRFX ASSETS\n\n"
        f"Total catalog: {len(ASSET_CATALOG)}\n"
        f"Found: {len(assets)}\n\n"
        "Asset dooro sidan:\n"
        "ASSET EURUSD_otc"
    )

    for i in range(
        0,
        len(assets),
        40,
    ):

        chunk = assets[
            i:i + 40
        ]

        text = "\n".join(
            f"• {asset}"
            for asset in chunk
        )

        await update.message.reply_text(
            text
        )


# =========================================================
# SELECT ASSET
# =========================================================

async def select_asset(
    update: Update,
    asset_name,
):

    asset_name = asset_name.strip()

    matched_asset = None

    for asset in ASSET_CATALOG:

        if asset.lower() == asset_name.lower():

            matched_asset = asset
            break

    if matched_asset is None:

        await update.message.reply_text(
            "❌ ASSET LAMA HELIN\n\n"
            f"Waxaad dirtay: {asset_name}\n\n"
            "Isticmaal 📋 ASSETS si aad u aragto magaca saxda ah."
        )

        return

    settings = get_settings(
        update.effective_user.id
    )

    settings["asset"] = matched_asset

    await update.message.reply_text(
        "✅ ASSET LA DOORTAY\n\n"
        f"📊 {matched_asset}\n\n"
        "Hadda riix 📊 SIGNAL.",
        reply_markup=main_keyboard(),
    )


# =========================================================
# TIMEFRAME MENU
# =========================================================

async def timeframe_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    keyboard = [
        [
            "1️⃣ 1 Minute",
            "3️⃣ 3 Minutes",
        ],
        [
            "5️⃣ 5 Minutes",
            "15️⃣ 15 Minutes",
        ],
        [
            "30️⃣ 30 Minutes",
            "60️⃣ 1 Hour",
        ],
    ]

    await update.message.reply_text(
        "⏱ DOORO TIMEFRAME-KA",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


# =========================================================
# TIMEFRAME COMMAND
# =========================================================

async def timeframe_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_text(
            "❌ Tusaale:\n"
            "/timeframe 180"
        )

        return

    try:

        value = int(
            context.args[0]
        )

        allowed = [
            60,
            180,
            300,
            900,
            1800,
            3600,
        ]

        if value not in allowed:
            raise ValueError

        settings = get_settings(
            update.effective_user.id
        )

        settings["timeframe"] = value

        await update.message.reply_text(
            "✅ TIMEFRAME LA DOORTAY\n\n"
            f"⏱ {value} seconds",
            reply_markup=main_keyboard(),
        )

    except Exception:

        await update.message.reply_text(
            "❌ Timeframe khalad ah.\n\n"
            "60, 180, 300, 900, 1800 ama 3600."
        )


# =========================================================
# EXPIRY MENU
# =========================================================

async def expiry_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "⌛ EXPIRY\n\n"
        "Isticmaal:\n\n"
        "/expiry 60\n"
        "/expiry 180\n"
        "/expiry 300\n"
        "/expiry 600\n"
        "/expiry 900"
    )


# =========================================================
# EXPIRY COMMAND
# =========================================================

async def expiry_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_text(
            "❌ Tusaale:\n"
            "/expiry 180"
        )

        return

    try:

        value = int(
            context.args[0]
        )

        allowed = [
            60,
            180,
            300,
            600,
            900,
        ]

        if value not in allowed:
            raise ValueError

        settings = get_settings(
            update.effective_user.id
        )

        settings["expiry"] = value

        await update.message.reply_text(
            "✅ EXPIRY LA DOORTAY\n\n"
            f"⌛ {value} seconds",
            reply_markup=main_keyboard(),
        )

    except Exception:

        await update.message.reply_text(
            "❌ Expiry khalad ah.\n\n"
            "60, 180, 300, 600 ama 900."
        )


# =========================================================
# SIGNAL
# =========================================================

async def signal_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    settings = get_settings(
        update.effective_user.id
    )

    asset = settings["asset"]
    timeframe = settings["timeframe"]
    expiry = settings["expiry"]

    await update.message.reply_text(
        "⏳ SIGNAL...\n\n"
        f"📊 Asset: {asset}\n"
        f"⏱ Timeframe: {timeframe // 60} Minutes\n"
        f"⌛ Expiry: {expiry // 60} minutes\n"
        f"⏱ Higher TF: 5 Minutes"
    )

    try:

        # =================================================
        # MAIN TIMEFRAME CANDLES
        # =================================================

        candles = await get_candles(
            asset,
            timeframe,
            CANDLE_COUNT,
        )

        df = candles_to_dataframe(
            candles
        )

        if df.empty:

            raise RuntimeError(
                "Candle data lama akhrin karin."
            )

        if len(df) < 50:

            raise RuntimeError(
                f"Candles ku filan lama helin: {len(df)}"
            )

        # =================================================
        # MAIN ANALYSIS
        # =================================================

        main = analyze_main(df)

        # =================================================
        # HIGHER TIMEFRAME
        # =================================================

        higher_candles = await get_candles(
            asset,
            HIGHER_TIMEFRAME,
            CANDLE_COUNT,
        )

        higher_df = candles_to_dataframe(
            higher_candles
        )

        if higher_df.empty:

            higher_signal = "WAIT"
            higher_candle_text = "No Data"

        else:

            (
                higher_signal,
                higher_candle_text,
            ) = analyze_higher_timeframe(
                higher_df
            )

        # =================================================
        # FINAL CONFIRMATION
        # =================================================

        (
            final_signal,
            call_score,
            put_score,
        ) = final_confirmation(
            main["trend"],
            main["rsi_signal"],
            main["current_candle"],
            main["previous_candle"],
            higher_signal,
        )

        # =================================================
        # SIGNAL DISPLAY
        # =================================================

        if final_signal == "CALL":

            signal_text = "🟢 CALL — STRONG CONFIRMATION"

        elif final_signal == "PUT":

            signal_text = "🔴 PUT — STRONG CONFIRMATION"

        else:

            signal_text = "⚪ WAIT — NO STRONG CONFIRMATION"

        # =================================================
        # RSI
        # =================================================

        rsi_value = main["rsi"]

        if (
            rsi_value is None
            or pd.isna(rsi_value)
        ):

            rsi_text = "N/A"

        else:

            rsi_text = f"{rsi_value:.2f}"

        # =================================================
        # PRICE / MA
        # =================================================

        price = main["price"]
        ma10 = main["ma10"]
        ma50 = main["ma50"]

        price_text = (
            f"{price:.5f}"
            if price is not None
            else "N/A"
        )

        ma10_text = (
            f"{ma10:.5f}"
            if ma10 is not None
            else "N/A"
        )

        ma50_text = (
            f"{ma50:.5f}"
            if ma50 is not None
            else "N/A"
        )

        # =================================================
        # CURRENT CANDLE TEXT
        # =================================================

        if main["current_candle"] == "CALL":

            current_candle_text = "Bullish 🟢"

        elif main["current_candle"] == "PUT":

            current_candle_text = "Bearish 🔴"

        else:

            current_candle_text = "Doji ⚪"

        # =================================================
        # PREVIOUS CANDLE TEXT
        # =================================================

        if main["previous_candle"] == "CALL":

            previous_candle_text = "Bullish 🟢"

        elif main["previous_candle"] == "PUT":

            previous_candle_text = "Bearish 🔴"

        else:

            previous_candle_text = "Doji ⚪"

        # =================================================
        # HIGHER TF TEXT
        # =================================================

        if higher_signal == "CALL":

            higher_signal_text = "CALL 🟢"

        elif higher_signal == "PUT":

            higher_signal_text = "PUT 🔴"

        else:

            higher_signal_text = "WAIT ⚪"

        # =================================================
        # FINAL MESSAGE
        # =================================================

        message = (
            "📊 LALAA24BOT SIGNAL\n\n"

            f"💱 Asset: {asset}\n\n"

            "📌 FINAL SIGNAL:\n"
            f"{signal_text}\n\n"

            "🔎 CONFIRMATION CHECK\n\n"

            "📈 Trend — MA10 + MA50:\n"
            f"{main['trend']}\n\n"

            "📊 Momentum — RSI:\n"
            f"{main['rsi_signal']} "
            f"({'🟢' if main['rsi_signal'] == 'CALL' else '🔴' if main['rsi_signal'] == 'PUT' else '⚪'} "
            f"(RSI {rsi_text}))\n\n"

            "🕯 Candle confirmation:\n"
            f"{main['current_candle']} "
            f"({'🟢' if main['current_candle'] == 'CALL' else '🔴' if main['current_candle'] == 'PUT' else '⚪'})\n"
            f"Current: {current_candle_text}\n\n"

            "🔎 Previous candle confirmation:\n"
            f"{main['previous_candle']} "
            f"({'🟢' if main['previous_candle'] == 'CALL' else '🔴' if main['previous_candle'] == 'PUT' else '⚪'})\n"
            f"Previous: {previous_candle_text}\n\n"

            "⏱ Higher Timeframe confirmation:\n"
            f"{higher_signal_text}\n"
            "Higher TF: 5 Minutes\n"
            f"Higher candle: {higher_candle_text} "
            f"{'🟢' if higher_signal == 'CALL' else '🔴' if higher_signal == 'PUT' else '⚪'}\n\n"

            "📊 CONFIRMATION RESULT\n"
            f"🟢 CALL confirmations: {call_score}/5\n"
            f"🔴 PUT confirmations: {put_score}/5\n\n"

            f"💰 Price: {price_text}\n"
            f"MA10: {ma10_text}\n"
            f"MA50: {ma50_text}\n"
            f"RSI: {rsi_text}\n\n"

            f"⏱ Timeframe: {timeframe // 60}️⃣ "
            f"{timeframe // 60} Minutes\n"
            f"⌛ Expiry: {expiry // 60} minutes\n\n"

            "⚠️ Signal-ku waa technical confirmation oo keliya.\n"
            "⚠️ 95% win lama dammaanad qaadi karo."
        )

        await update.message.reply_text(
            message,
            reply_markup=main_keyboard(),
        )

    except Exception as exc:

        logger.exception(
            "SIGNAL ERROR"
        )

        await update.message.reply_text(
            "❌ MARKET DATA ERROR\n\n"
            f"Asset: {asset}\n"
            f"Timeframe: {timeframe // 60} Minutes\n\n"
            f"Faahfaahin: {exc}\n\n"
            "ℹ️ Bot-ku signal been ah ma sameynayo.",
            reply_markup=main_keyboard(),
        )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = (
        update.message.text or ""
    ).strip()

    upper = text.upper()

    # -----------------------------------------------------
    # SIGNAL BUTTON
    # -----------------------------------------------------

    if "SIGNAL" in upper:

        await signal_command(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # ASSETS BUTTON
    # -----------------------------------------------------

    if "ASSETS" in upper:

        await assets_command(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # TIMEFRAME BUTTON
    # -----------------------------------------------------

    if "TIMEFRAME" in upper:

        await timeframe_menu(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # EXPIRY BUTTON
    # -----------------------------------------------------

    if "EXPIRY" in upper:

        await expiry_menu(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # STATUS BUTTON
    # -----------------------------------------------------

    if "STATUS" in upper:

        await status(
            update,
            context,
        )

        return

    # -----------------------------------------------------
    # TIMEFRAME BUTTONS
    # -----------------------------------------------------

    timeframe_map = {
        "1️⃣ 1 MINUTE": 60,
        "3️⃣ 3 MINUTES": 180,
        "5️⃣ 5 MINUTES": 300,
        "15️⃣ 15 MINUTES": 900,
        "30️⃣ 30 MINUTES": 1800,
        "60️⃣ 1 HOUR": 3600,
    }

    if upper in timeframe_map:

        settings = get_settings(
            update.effective_user.id
        )

        settings["timeframe"] = (
            timeframe_map[upper]
        )

        await update.message.reply_text(
            "✅ TIMEFRAME LA DOORTAY\n\n"
            f"⏱ {timeframe_map[upper] // 60} Minutes",
            reply_markup=main_keyboard(),
        )

        return

    # -----------------------------------------------------
    # ASSET SELECTION
    # -----------------------------------------------------

    if upper.startswith("ASSET "):

        asset_name = text[6:].strip()

        await select_asset(
            update,
            asset_name,
        )

        return

    # -----------------------------------------------------
    # DEFAULT
    # -----------------------------------------------------

    await update.message.reply_text(
        "🤖 NAASIRFX\n\n"
        "Isticmaal:\n"
        "📊 SIGNAL\n"
        "📋 ASSETS\n"
        "⏱ TIMEFRAME\n"
        "⌛ EXPIRY\n"
        "ℹ️ STATUS\n\n"
        "Ama asset dooro:\n"
        "ASSET EURUSD_otc",
        reply_markup=main_keyboard(),
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context,
):

    logger.exception(
        "Telegram error: %s",
        context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TELEGRAM_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    # Render health server
    health_thread = Thread(
        target=start_health_server,
        daemon=True,
    )

    health_thread.start()

    # Telegram application
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status,
        )
    )

    application.add_handler(
        CommandHandler(
            "signal",
            signal_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "assets",
            assets_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "timeframe",
            timeframe_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "expiry",
            expiry_command,
        )
    )

    # Text messages/buttons
    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "%s starting...",
        BOT_NAME,
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
