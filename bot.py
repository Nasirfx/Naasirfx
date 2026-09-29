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
DEFAULT_TIMEFRAME = 60
DEFAULT_EXPIRY = 300

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

    # Remove duplicates
    assets = list(dict.fromkeys(assets))

    # Always keep default asset
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
# RENDER HEALTH
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
    count=100,
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

        # Working Pocket Option object format
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

        # Backup dictionary format
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

def rsi(series, period=14):

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
# EMA
# =========================================================

def ema(series, period):

    return series.ewm(
        span=period,
        adjust=False,
    ).mean()


# =========================================================
# MACD
# =========================================================

def macd(series):

    ema12 = ema(
        series,
        12,
    )

    ema26 = ema(
        series,
        26,
    )

    macd_line = ema12 - ema26

    signal_line = ema(
        macd_line,
        9,
    )

    return macd_line, signal_line


# =========================================================
# BOLLINGER
# =========================================================

def bollinger(series):

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

def analyze(df):

    result = {
        "signal": "WAIT",
        "score": 0,
        "trend": "WAIT",
        "rsi": None,
        "macd": "WAIT",
        "bollinger": "WAIT",
        "candle": "WAIT",
    }

    if df.empty:
        return result

    if len(df) < 50:
        return result

    df = df.copy()

    # MA
    df["MA10"] = df["close"].rolling(
        10
    ).mean()

    df["MA50"] = df["close"].rolling(
        50
    ).mean()

    # RSI
    df["RSI"] = rsi(
        df["close"],
        14,
    )

    # MACD
    (
        df["MACD"],
        df["MACD_SIGNAL"],
    ) = macd(
        df["close"]
    )

    # Bollinger
    (
        df["BB_UPPER"],
        df["BB_MIDDLE"],
        df["BB_LOWER"],
    ) = bollinger(
        df["close"]
    )

    last = df.iloc[-1]

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
    # -----------------------------------------------------

    rsi_value = last["RSI"]

    rsi_signal = "WAIT"

    if pd.notna(rsi_value):

        if 55 <= rsi_value <= 70:
            rsi_signal = "CALL"

        elif 30 <= rsi_value <= 45:
            rsi_signal = "PUT"

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    macd_signal = "WAIT"

    if (
        pd.notna(last["MACD"])
        and
        pd.notna(last["MACD_SIGNAL"])
    ):

        if last["MACD"] > last["MACD_SIGNAL"]:
            macd_signal = "CALL"

        elif last["MACD"] < last["MACD_SIGNAL"]:
            macd_signal = "PUT"

    # -----------------------------------------------------
    # BOLLINGER
    # -----------------------------------------------------

    bollinger_signal = "WAIT"

    if pd.notna(last["BB_MIDDLE"]):

        if last["close"] > last["BB_MIDDLE"]:
            bollinger_signal = "CALL"

        elif last["close"] < last["BB_MIDDLE"]:
            bollinger_signal = "PUT"

    # -----------------------------------------------------
    # CANDLE
    # -----------------------------------------------------

    if last["close"] > last["open"]:

        candle_signal = "CALL"

    elif last["close"] < last["open"]:

        candle_signal = "PUT"

    else:

        candle_signal = "WAIT"

    # -----------------------------------------------------
    # SCORE
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

    final_signal = "WAIT"

    if call_score >= 4:

        final_signal = "CALL"

    elif put_score >= 4:

        final_signal = "PUT"

    result = {
        "signal": final_signal,
        "score": max(
            call_score,
            put_score,
        ),
        "trend": trend,
        "rsi": rsi_value,
        "macd": macd_signal,
        "bollinger": bollinger_signal,
        "candle": candle_signal,
    }

    return result


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
        f"⌛ Expiry: {settings['expiry']} sec\n\n"
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
        "ASSET #TSLA_otc"
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
        f"⏱ Timeframe: {timeframe} sec\n"
        f"⌛ Expiry: {expiry} sec"
    )

    try:

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

        analysis = analyze(df)

        final_signal = analysis["signal"]

        if final_signal == "CALL":

            signal_text = "🟢 CALL"

        elif final_signal == "PUT":

            signal_text = "🔴 PUT"

        else:

            signal_text = "⚪ WAIT"

        rsi_value = analysis["rsi"]

        if (
            rsi_value is None
            or pd.isna(rsi_value)
        ):

            rsi_text = "N/A"

        else:

            rsi_text = f"{rsi_value:.2f}"

        message = (
            "📊 NAASIRFX SIGNAL\n\n"
            f"💱 Asset: {asset}\n"
            f"⏱ Timeframe: {timeframe} sec\n"
            f"⌛ Expiry: {expiry} sec\n\n"
            f"🎯 FINAL SIGNAL: {signal_text}\n\n"
            "🔎 CONFIRMATION CHECK\n"
            f"📈 MA10 + MA50: {analysis['trend']}\n"
            f"📊 RSI: {rsi_text}\n"
            f"📉 MACD: {analysis['macd']}\n"
            f"〰️ Bollinger: {analysis['bollinger']}\n"
            f"🕯 Candle: {analysis['candle']}\n\n"
            f"🔥 Confirmation: {analysis['score']}/5\n\n"
            "⚠️ Signal adag ah ayaa la isticmaalaa.\n"
            "⚠️ 95% win lama dammaanad qaadi karo."
        )

        await update.message.reply_text(
            message,
            reply_markup=main_keyboard(),
        )

    except Exception as exc:

        logger.exception(
            "Signal error"
        )

        await update.message.reply_text(
            "❌ MARKET DATA ERROR\n\n"
            f"📊 Asset: {asset}\n"
            f"⏱ Timeframe: {timeframe} sec\n\n"
            f"Error: {type(exc).__name__}: {exc}",
            reply_markup=main_keyboard(),
        )


# =========================================================
# ASSET SELECTION
# =========================================================

async def select_asset(
    update: Update,
    symbol,
):

    symbol = symbol.strip()

    if not symbol:

        await update.message.reply_text(
            "❌ Asset ma qorna."
        )

        return

    match = next(
        (
            asset
            for asset in ASSET_CATALOG
            if asset.lower() == symbol.lower()
        ),
        None,
    )

    if match is None:

        await update.message.reply_text(
            "❌ Asset-kan catalog-ga lama helin.\n\n"
            f"📊 {symbol}\n\n"
            "Isticmaal 📋 ASSETS."
        )

        return

    settings = get_settings(
        update.effective_user.id
    )

    settings["asset"] = match

    await update.message.reply_text(
        "✅ ASSET LA DOORTAY\n\n"
        f"📊 {match}\n\n"
        "Hadda riix 📊 SIGNAL.",
        reply_markup=main_keyboard(),
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = (
        update.message.text
        or ""
    ).strip()

    if not text:
        return

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
    # TIMEFRAME BUTTON VALUES
    # -----------------------------------------------------

    timeframe_map = {

        "1️⃣ 1 MINUTE": 60,

        "3️⃣ 3 MINUTES": 180,

        "5️⃣ 5 MINUTES": 300,

        "15️⃣ 15 MINUTES": 900,

        "30️⃣ 30 MINUTES": 1800,

        "60️⃣ 1 HOUR": 3600,
    }

    normalized = upper

    for key, value in timeframe_map.items():

        if normalized == key:

            settings = get_settings(
                update.effective_user.id
            )

            settings["timeframe"] = value

            await update.message.reply_text(
                "✅ TIMEFRAME LA DOORTAY\n\n"
                f"⏱ {value} seconds\n\n"
                "Hadda riix 📊 SIGNAL.",
                reply_markup=main_keyboard(),
            )

            return

    # -----------------------------------------------------
    # ASSET TEXT
    # -----------------------------------------------------

    if upper.startswith("ASSET "):

        symbol = text[6:].strip()

        await select_asset(
            update,
            symbol,
        )

        return

    # -----------------------------------------------------
    # UNKNOWN MESSAGE
    # -----------------------------------------------------

    await update.message.reply_text(
        "🤖 NAASIRFX\n\n"
        "Isticmaal buttons-ka hoose.",
        reply_markup=main_keyboard(),
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.error(
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

    Thread(
        target=start_health_server,
        daemon=True,
    ).start()

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

    # Text / buttons
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
        "NaasirFx starting..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
