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


# =========================================================
# NAASIRFX SETTINGS
# =========================================================

BOT_NAME = "NaasirFx"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POCKET_SSID = os.getenv("POCKET_OPTION_SSID")

DEFAULT_ASSET = "EURUSD_otc"
DEFAULT_TIMEFRAME = 60
DEFAULT_EXPIRY = 300

CANDLE_COUNT = 100


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("NaasirFx")


# =========================================================
# USER SETTINGS
# =========================================================

USER_SETTINGS = {}


def get_user_settings(user_id):
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
            "text/plain"
        )
        self.end_headers()

        self.wfile.write(
            b"NaasirFx is running"
        )

    def log_message(self, format, *args):
        return


def start_web_server():

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    logger.info(
        "Health server started on port %s",
        port
    )

    server.serve_forever()


# =========================================================
# POCKET OPTION CONNECTION
# =========================================================

async def connect_pocket_option():

    if not POCKET_SSID:
        raise RuntimeError(
            "POCKET_OPTION_SSID is missing."
        )

    last_error = None

    for attempt in range(1, 4):

        try:

            logger.info(
                "Pocket Option connection %s/3",
                attempt
            )

            client = AsyncPocketOptionClient(
                POCKET_SSID,
                is_demo=True,
            )

            result = await client.connect()

            if result is False:
                raise RuntimeError(
                    "Pocket Option connect() returned False"
                )

            logger.info(
                "Pocket Option connected successfully."
            )

            return client

        except Exception as exc:

            last_error = exc

            logger.error(
                "Connection attempt %s failed: %s",
                attempt,
                exc
            )

            if attempt < 3:
                await asyncio.sleep(5)

    raise RuntimeError(
        "Pocket Option connection failed after 3 attempts. "
        f"Last error: {last_error}"
    )


# =========================================================
# GET CANDLES
# =========================================================

async def get_market_data(
    asset,
    timeframe,
    count=CANDLE_COUNT,
):

    client = None

    try:

        client = await connect_pocket_option()

        candles = await client.get_candles(
            asset,
            timeframe,
            count,
        )

        if not candles:
            raise RuntimeError(
                f"No candle data received for {asset}"
            )

        return candles

    finally:

        if client is not None:

            try:
                await client.disconnect()
            except Exception:
                pass


# =========================================================
# CANDLES TO DATAFRAME
# =========================================================

def candles_to_dataframe(candles):

    if not candles:
        return pd.DataFrame()

    rows = []

    for candle in candles:

        try:

            rows.append({
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
            })

        except Exception:

            if isinstance(candle, dict):

                try:

                    rows.append({
                        "open": float(
                            candle["open"]
                        ),
                        "high": float(
                            candle["high"]
                        ),
                        "low": float(
                            candle["low"]
                        ),
                        "close": float(
                            candle["close"]
                        ),
                    })

                except Exception:
                    continue

    return pd.DataFrame(rows)


# =========================================================
# RSI
# =========================================================

def calculate_rsi(
    series,
    period=14,
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

    rs = avg_gain / avg_loss.replace(
        0,
        float("nan")
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# =========================================================
# EMA
# =========================================================

def calculate_ema(
    series,
    period,
):

    return series.ewm(
        span=period,
        adjust=False
    ).mean()


# =========================================================
# MACD
# =========================================================

def calculate_macd(series):

    ema12 = calculate_ema(
        series,
        12
    )

    ema26 = calculate_ema(
        series,
        26
    )

    macd = ema12 - ema26

    signal = calculate_ema(
        macd,
        9
    )

    return macd, signal


# =========================================================
# BOLLINGER BANDS
# =========================================================

def calculate_bollinger(series):

    middle = series.rolling(
        20
    ).mean()

    std = series.rolling(
        20
    ).std()

    upper = middle + (
        2 * std
    )

    lower = middle - (
        2 * std
    )

    return upper, middle, lower


# =========================================================
# MARKET ANALYSIS
# =========================================================

def analyze_market(df):

    empty_result = {
        "signal": "WAIT",
        "score": 0,
        "trend": "WAIT",
        "rsi": None,
        "macd": "WAIT",
        "bollinger": "WAIT",
        "candle": "WAIT",
    }

    if df.empty:
        return empty_result

    if len(df) < 50:
        return empty_result

    df = df.copy()

    # -----------------------------------------------------
    # MA10 / MA50
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    df["RSI"] = calculate_rsi(
        df["close"],
        14
    )

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    (
        df["MACD"],
        df["MACD_SIGNAL"]
    ) = calculate_macd(
        df["close"]
    )

    # -----------------------------------------------------
    # BOLLINGER
    # -----------------------------------------------------

    (
        df["BB_UPPER"],
        df["BB_MIDDLE"],
        df["BB_LOWER"]
    ) = calculate_bollinger(
        df["close"]
    )

    last = df.iloc[-1]

    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------

    trend = "WAIT"

    if last["MA10"] > last["MA50"]:
        trend = "CALL"

    elif last["MA10"] < last["MA50"]:
        trend = "PUT"

    # -----------------------------------------------------
    # RSI MOMENTUM
    # -----------------------------------------------------

    rsi = last["RSI"]

    rsi_signal = "WAIT"

    if pd.notna(rsi):

        if 55 <= rsi <= 70:
            rsi_signal = "CALL"

        elif 30 <= rsi <= 45:
            rsi_signal = "PUT"

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    macd_signal = "WAIT"

    if (
        pd.notna(last["MACD"])
        and pd.notna(last["MACD_SIGNAL"])
    ):

        if last["MACD"] > last["MACD_SIGNAL"]:
            macd_signal = "CALL"

        elif last["MACD"] < last["MACD_SIGNAL"]:
            macd_signal = "PUT"

    # -----------------------------------------------------
    # BOLLINGER
    # -----------------------------------------------------

    bollinger_signal = "WAIT"

    if (
        pd.notna(last["BB_MIDDLE"])
        and pd.notna(last["BB_UPPER"])
        and pd.notna(last["BB_LOWER"])
    ):

        if last["close"] > last["BB_MIDDLE"]:
            bollinger_signal = "CALL"

        elif last["close"] < last["BB_MIDDLE"]:
            bollinger_signal = "PUT"

    # -----------------------------------------------------
    # CANDLE
    # -----------------------------------------------------

    candle_signal = "WAIT"

    if last["close"] > last["open"]:
        candle_signal = "CALL"

    elif last["close"] < last["open"]:
        candle_signal = "PUT"

    # -----------------------------------------------------
    # CONFIRMATION SCORE
    # -----------------------------------------------------

    checks = [
        trend,
        rsi_signal,
        macd_signal,
        bollinger_signal,
        candle_signal,
    ]

    call_score = checks.count("CALL")
    put_score = checks.count("PUT")

    # -----------------------------------------------------
    # STRICT SIGNAL
    # -----------------------------------------------------

    signal = "WAIT"

    if call_score >= 4:
        signal = "CALL"

    elif put_score >= 4:
        signal = "PUT"

    return {
        "signal": signal,
        "score": max(
            call_score,
            put_score
        ),
        "trend": trend,
        "rsi": rsi,
        "macd": macd_signal,
        "bollinger": bollinger_signal,
        "candle": candle_signal,
    }


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

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

    markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 NAASIRFX\n\n"
        "Ku soo dhawoow NaasirFx.\n\n"
        "📊 SIGNAL - Signal samee\n"
        "📋 ASSETS - Assets-ka\n"
        "⏱ TIMEFRAME - Candle timeframe\n"
        "⌛ EXPIRY - Signal expiry\n"
        "ℹ️ STATUS - Bot status",
        reply_markup=markup
    )


# =========================================================
# STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    token_status = (
        "✅ OK"
        if TELEGRAM_TOKEN
        else "❌ Missing"
    )

    ssid_status = (
        "✅ OK"
        if POCKET_SSID
        else "❌ Missing"
    )

    settings = get_user_settings(
        update.effective_user.id
    )

    await update.message.reply_text(
        "🤖 NAASIRFX STATUS\n\n"
        f"Telegram Token: {token_status}\n"
        f"Pocket Option SSID: {ssid_status}\n\n"
        f"📊 Asset: {settings['asset']}\n"
        f"⏱ Timeframe: {settings['timeframe']} sec\n"
        f"⌛ Expiry: {settings['expiry']} sec"
    )


# =========================================================
# ASSETS
# =========================================================

async def assets_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "📋 NAASIRFX ASSETS\n\n"
        "Asset discovery automatic ah "
        "API-ga client-kaaga hadda ma taageero.\n\n"
        "Waxaad signal-ka u dooran kartaa asset "
        "adigoo qoraya:\n\n"
        "ASSET EURUSD_otc\n"
        "ASSET GBPUSD_otc\n"
        "ASSET USDJPY_otc\n\n"
        "Kadib riix 📊 SIGNAL."
    )


# =========================================================
# TIMEFRAME
# =========================================================

async def timeframe_command(
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

    markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "⏱ DOORO TIMEFRAME-KA\n\n"
        "Dooro candle timeframe-ka:",
        reply_markup=markup
    )


# =========================================================
# EXPIRY
# =========================================================

async def expiry_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "⌛ EXPIRY\n\n"
        "Ku qor tusaale ahaan:\n\n"
        "/expiry 300\n\n"
        "60 = 1 minute\n"
        "180 = 3 minutes\n"
        "300 = 5 minutes\n"
        "600 = 10 minutes\n"
        "900 = 15 minutes"
    )


# =========================================================
# TIMEFRAME VALUE
# =========================================================

async def timeframe_value(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_text(
            "❌ Tusaale:\n"
            "/timeframe 60"
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

        settings = get_user_settings(
            update.effective_user.id
        )

        settings["timeframe"] = value

        await update.message.reply_text(
            "✅ TIMEFRAME LA BEDDELAY\n\n"
            f"⏱ {value} seconds"
        )

    except Exception:

        await update.message.reply_text(
            "❌ Timeframe khalad ah.\n\n"
            "Isticmaal 60, 180, 300, 900, "
            "1800 ama 3600."
        )


# =========================================================
# EXPIRY VALUE
# =========================================================

async def expiry_value(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_text(
            "❌ Tusaale:\n"
            "/expiry 300"
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

        settings = get_user_settings(
            update.effective_user.id
        )

        settings["expiry"] = value

        await update.message.reply_text(
            "✅ EXPIRY LA BEDDELAY\n\n"
            f"⌛ {value} seconds"
        )

    except Exception:

        await update.message.reply_text(
            "❌ Expiry khalad ah.\n\n"
            "Isticmaal 60, 180, 300, 600 ama 900."
        )


# =========================================================
# SIGNAL
# =========================================================

async def signal_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    settings = get_user_settings(
        user_id
    )

    asset = settings["asset"]
    timeframe = settings["timeframe"]
    expiry = settings["expiry"]

    await update.message.reply_text(
        "⏳ NaasirFx market data ayuu soo qaadanayaa...\n\n"
        f"📊 {asset}\n"
        f"⏱ Timeframe: {timeframe} sec\n"
        f"⌛ Expiry: {expiry} sec"
    )

    try:

        candles = await get_market_data(
            asset,
            timeframe,
            CANDLE_COUNT
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
                f"Candles ku filan lama helin. "
                f"Received: {len(df)}"
            )

        result = analyze_market(
            df
        )

        signal_name = result["signal"]

        if signal_name == "CALL":
            signal_text = "🟢 CALL"

        elif signal_name == "PUT":
            signal_text = "🔴 PUT"

        else:
            signal_text = "⚪ WAIT"

        rsi = result["rsi"]

        if rsi is None or pd.isna(rsi):
            rsi_text = "N/A"
        else:
            rsi_text = f"{rsi:.2f}"

        message = (
            "📊 NAASIRFX SIGNAL\n\n"

            f"💱 Asset: {asset}\n"
            f"⏱ Timeframe: {timeframe} sec\n"
            f"⌛ Expiry: {expiry} sec\n\n"

            f"🎯 FINAL SIGNAL: {signal_text}\n\n"

            "🔎 CONFIRMATION CHECK\n"

            f"📈 MA10 + MA50: "
            f"{result['trend']}\n"

            f"📊 RSI: "
            f"{rsi_text}\n"

            f"📉 MACD: "
            f"{result['macd']}\n"

            f"〰️ Bollinger: "
            f"{result['bollinger']}\n"

            f"🕯 Candle: "
            f"{result['candle']}\n\n"

            f"🔥 Confirmation: "
            f"{result['score']}/5\n\n"

            "⚠️ Signal adag ah ayaa la isticmaalaa.\n"
            "⚠️ 95% win lama dammaanad qaadi karo."
        )

        await update.message.reply_text(
            message
        )

    except Exception as exc:

        logger.exception(
            "Signal error"
        )

        await update.message.reply_text(
            "❌ MARKET DATA ERROR\n\n"
            f"Asset: {asset}\n"
            f"Timeframe: {timeframe} sec\n\n"
            f"Error: {type(exc).__name__}: {exc}"
        )


# =========================================================
# TEXT MESSAGE HANDLER
# =========================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = update.message.text.strip()

    user_id = update.effective_user.id

    settings = get_user_settings(
        user_id
    )

     # -----------------------------------------------------
    # BUTTONS
    # -----------------------------------------------------

    if text == "📊 SIGNAL":

        await signal_command(
            update,
            context
        )

        return

    if text == "📋 ASSETS":

        await assets_command(
            update,
            context
        )

        return

    if text == "⏱ TIMEFRAME":

        await timeframe_command(
            update,
            context
        )

        return

    if text == "⌛ EXPIRY":

        await expiry_command(
            update,
            context
        )

        return

    if text == "ℹ️ STATUS":

        await status(
            update,
            context
        )

        return

    # -----------------------------------------------------
    # TIMEFRAME BUTTONS
    # -----------------------------------------------------

    timeframe_map = {

        "1️⃣ 1 Minute": 60,

        "3️⃣ 3 Minutes": 180,

        "5️⃣ 5 Minutes": 300,

        "15️⃣ 15 Minutes": 900,

        "30️⃣ 30 Minutes": 1800,

        "60️⃣ 1 Hour": 3600,
    }

    if text in timeframe_map:

        settings["timeframe"] = (
            timeframe_map[text]
        )

        await update.message.reply_text(
            "✅ TIMEFRAME LA DOORTAY\n\n"
            f"⏱ {text}\n\n"
            "Hadda riix 📊 SIGNAL."
        )

        return

    # -----------------------------------------------------
    # ASSET
    # -----------------------------------------------------

    if text.upper().startswith("ASSET "):

        symbol = text[6:].strip()

        if symbol:

            settings["asset"] = symbol

            await update.message.reply_text(
                "✅ ASSET LA DOORTAY\n\n"
                f"📊 {symbol}\n\n"
                "Hadda riix 📊 SIGNAL."
            )

            return

    await update.message.reply_text(
        "🤖 NAASIRFX\n\n"
        "Isticmaal:\n"
        "📊 SIGNAL\n"
        "📋 ASSETS\n"
        "⏱ TIMEFRAME\n"
        "⌛ EXPIRY\n"
        "ℹ️ STATUS"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TELEGRAM_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    Thread(
        target=start_web_server,
        daemon=True
    ).start()

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status
        )
    )

    application.add_handler(
        CommandHandler(
            "signal",
            signal_command
        )
    )

    application.add_handler(
        CommandHandler(
            "assets",
            assets_command
        )
    )

    application.add_handler(
        CommandHandler(
            "timeframe",
            timeframe_value
        )
    )

    application.add_handler(
        CommandHandler(
            "expiry",
            expiry_value
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler
        )
    )

    logger.info(
        "NaasirFx starting..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
