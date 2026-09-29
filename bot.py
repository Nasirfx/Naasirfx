import os
import asyncio
import math
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

import pandas as pd
import numpy as np

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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POCKET_SSID = os.getenv("POCKET_OPTION_SSID")

DEFAULT_ASSET = "EURUSD_otc"

# TIMEFRAME and EXPIRY are completely independent
DEFAULT_TIMEFRAME = 180       # 3 minutes
DEFAULT_EXPIRY = 180          # 3 minutes

HIGHER_TIMEFRAME = 300        # 5 minutes
CANDLE_COUNT = 100


# =========================================================
# SIMPLE WEB SERVER FOR RENDER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"NaasirFx is running")

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


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
# KEYBOARD
# =========================================================

def main_keyboard():

    keyboard = [
        ["📊 SIGNAL"],
        ["📋 PAIRS"],
        ["⏱ TIMEFRAME", "⌛ EXPIRY"],
        ["ℹ️ STATUS"],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =========================================================
# HELPERS
# =========================================================

def timeframe_name(seconds):

    names = {
        60: "1 Minute",
        180: "3 Minutes",
        300: "5 Minutes",
        900: "15 Minutes",
        1800: "30 Minutes",
        3600: "1 Hour",
    }

    return names.get(seconds, f"{seconds} Seconds")


def expiry_name(seconds):

    names = {
        60: "1 Minute",
        180: "3 Minutes",
        300: "5 Minutes",
        600: "10 Minutes",
        900: "15 Minutes",
    }

    return names.get(seconds, f"{seconds} Seconds")


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
# GET CANDLES
# =========================================================

async def get_candles(asset, timeframe, count=CANDLE_COUNT):

    client = None

    try:

        if not POCKET_SSID:
            return None

        client = AsyncPocketOptionClient(
            POCKET_SSID,
            is_demo=True,
        )

        connected = await client.connect()

        if not connected:
            return None

        candles = await client.get_candles(
            asset,
            timeframe,
            count
        )

        if not candles:
            return None

        rows = []

        for candle in candles:

            try:

                # Object format
                if hasattr(candle, "open"):

                    rows.append({
                        "open": float(candle.open),
                        "high": float(candle.high),
                        "low": float(candle.low),
                        "close": float(candle.close),
                    })

                # Dictionary format
                elif isinstance(candle, dict):

                    rows.append({
                        "open": float(candle["open"]),
                        "high": float(candle["high"]),
                        "low": float(candle["low"]),
                        "close": float(candle["close"]),
                    })

            except Exception:
                continue

        if len(rows) < 20:
            return None

        return pd.DataFrame(rows)

    except Exception as e:

        print("CANDLE ERROR:", e)

        return None

    finally:

        try:
            if client:
                await client.disconnect()
        except Exception:
            pass


# =========================================================
# RSI
# =========================================================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


# =========================================================
# CANDLE DIRECTION
# =========================================================

def candle_direction(row):

    if row["close"] > row["open"]:
        return "CALL"

    if row["close"] < row["open"]:
        return "PUT"

    return "WAIT"


def candle_emoji(direction):

    if direction == "CALL":
        return "🟢"

    if direction == "PUT":
        return "🔴"

    return "⚪"


def candle_text(direction):

    if direction == "CALL":
        return "Bullish 🟢"

    if direction == "PUT":
        return "Bearish 🔴"

    return "Doji ⚪"


# =========================================================
# ASSET VALIDATION
# =========================================================

def get_asset_list():

    result = []

    try:

        if isinstance(ASSETS, dict):

            result = list(ASSETS.keys())

        elif isinstance(ASSETS, (list, tuple, set)):

            result = list(ASSETS)

    except Exception as e:

        print("ASSET LIST ERROR:", e)

    return sorted(
        [str(x) for x in result]
    )


def asset_exists(asset):

    assets = get_asset_list()

    return asset in assets


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Salaam sxbow!\n\n"
        "🤖 NaasirFx Signal Bot\n\n"
        "📌 Pair-ka adiga ayaa dooranaya.\n"
        "⏱ Timeframe-ka adiga ayaa dooranaya.\n"
        "⌛ Expiry-ga adiga ayaa dooranaya.\n\n"
        "⚠️ Automatic pair selection ma jiro.\n"
        "⚠️ Auto-trading ma jiro.\n\n"
        "Dooro waxa aad rabto 👇",
        reply_markup=main_keyboard()
    )


# =========================================================
# STATUS
# =========================================================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    settings = get_settings(user_id)

    token_status = "✅ OK" if TOKEN else "❌ MISSING"
    ssid_status = "✅ OK" if POCKET_SSID else "❌ MISSING"

    await update.message.reply_text(
        "🤖 NAASIRFX STATUS\n\n"

        f"Telegram Token: {token_status}\n"
        f"Pocket Option SSID: {ssid_status}\n\n"

        f"💱 Pair: {settings['asset']}\n"
        f"⏱ Timeframe: {timeframe_name(settings['timeframe'])}\n"
        f"⌛ Expiry: {expiry_name(settings['expiry'])}\n\n"

        f"📋 Asset catalog: {len(get_asset_list())}"
    )


# =========================================================
# PAIRS
# =========================================================

async def pairs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    assets = get_asset_list()

    if not assets:

        await update.message.reply_text(
            "❌ Pair list lama helin."
        )

        return

    # Show common pairs first
    preferred = [
        "EURUSD_otc",
        "GBPUSD_otc",
        "USDJPY_otc",
        "AUDUSD_otc",
        "USDCAD_otc",
        "USDCHF_otc",
        "EURJPY_otc",
        "EURGBP_otc",
        "NZDUSD_otc",
        "EURCHF_otc",
        "GBPJPY_otc",
        "AUDJPY_otc",
    ]

    selected = []

    for pair in preferred:

        if pair in assets:
            selected.append(pair)

    for pair in assets:

        if pair not in selected:
            selected.append(pair)

    # Telegram message limit protection
    selected = selected[:80]

    text = "📋 PAIRS\n\n"

    for pair in selected:
        text += f"• {pair}\n"

    text += (
        "\n📌 Pair aad rabto ku qor:\n"
        "ASSET EURUSD_otc\n\n"
        "Tusaale:\n"
        "ASSET GBPUSD_otc"
    )

    await update.message.reply_text(text)


# =========================================================
# ASSET COMMAND
# =========================================================

async def asset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not context.args:

        await update.message.reply_text(
            "❌ Qor pair-ka.\n\n"
            "Tusaale:\n"
            "ASSET EURUSD_otc"
        )

        return

    asset = context.args[0].strip()

    if not asset_exists(asset):

        await update.message.reply_text(
            f"❌ Pair-kan catalog-ga kuma jiro:\n\n"
            f"{asset}\n\n"
            "Isticmaal 📋 PAIRS si aad u aragto pair-yada."
        )

        return

    settings = get_settings(user_id)

    settings["asset"] = asset

    await update.message.reply_text(
        "✅ PAIR-KA WAA LA DOORTAY\n\n"
        f"💱 Pair: {asset}\n\n"
        "⏱ Timeframe-ka iyo ⌛ Expiry-ga "
        "waxba kama beddelmin."
    )


# =========================================================
# TIMEFRAME MENU
# =========================================================

async def timeframe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["1️⃣ 1 Minute", "3️⃣ 3 Minutes"],
        ["5️⃣ 5 Minutes", "1️⃣5️⃣ 15 Minutes"],
        ["3️⃣0️⃣ 30 Minutes", "1️⃣ Hour"],
        ["🔙 BACK"],
    ]

    await update.message.reply_text(
        "⏱ TIMEFRAME\n\n"
        "Dooro timeframe-ka aad rabto.\n\n"
        "📌 Timeframe-ku waa madax-bannaan.\n"
        "⌛ Expiry-ga ma beddelayo.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# =========================================================
# EXPIRY MENU
# =========================================================

async def expiry_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["1️⃣ 1 Minute", "3️⃣ 3 Minutes"],
        ["5️⃣ 5 Minutes", "🔟 10 Minutes"],
        ["1️⃣5️⃣ 15 Minutes"],
        ["🔙 BACK"],
    ]

    await update.message.reply_text(
        "⌛ EXPIRY\n\n"
        "Dooro expiry-ga aad rabto.\n\n"
        "📌 Expiry-gu waa madax-bannaan.\n"
        "⏱ Timeframe-ka ma beddelayo.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# =========================================================
# TIMEFRAME SET
# =========================================================

async def set_timeframe(update: Update, seconds):

    user_id = update.effective_user.id
    settings = get_settings(user_id)

    # ONLY timeframe changes
    settings["timeframe"] = seconds

    await update.message.reply_text(
        "✅ TIMEFRAME WAA LA DOORTAY\n\n"
        f"⏱ Timeframe: {timeframe_name(seconds)}\n"
        f"💱 Pair: {settings['asset']}\n"
        f"⌛ Expiry: {expiry_name(settings['expiry'])}\n\n"
        "📌 Expiry-gu isma beddelin."
    )


# =========================================================
# EXPIRY SET
# =========================================================

async def set_expiry(update: Update, seconds):

    user_id = update.effective_user.id
    settings = get_settings(user_id)

    # ONLY expiry changes
    settings["expiry"] = seconds

    await update.message.reply_text(
        "✅ EXPIRY WAA LA DOORTAY\n\n"
        f"⌛ Expiry: {expiry_name(seconds)}\n"
        f"💱 Pair: {settings['asset']}\n"
        f"⏱ Timeframe: {timeframe_name(settings['timeframe'])}\n\n"
        "📌 Timeframe-ku isma beddelin."
    )


# =========================================================
# SIGNAL
# =========================================================

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    settings = get_settings(user_id)

    asset = settings["asset"]
    timeframe = settings["timeframe"]
    expiry = settings["expiry"]

    await update.message.reply_text(
        "🔎 Signal-ka waan baarayaa...\n\n"
        f"💱 {asset}\n"
        f"⏱ {timeframe_name(timeframe)}\n"
        f"⌛ Expiry: {expiry_name(expiry)}"
    )

    # Main timeframe
    df = await get_candles(
        asset,
        timeframe,
        CANDLE_COUNT
    )

    if df is None or len(df) < 60:

        await update.message.reply_text(
            "❌ DATA LAMA HELIN\n\n"

            f"Asset: {asset}\n"
            f"Timeframe: {timeframe_name(timeframe)}\n\n"

            "Bot-ku candles kama helin "
            "Pocket Option API-ga asset-kan.\n\n"

            "ℹ️ Bot-ku ma sameynayo signal been ah."
        )

        return

    # Higher timeframe
    higher_df = await get_candles(
        asset,
        HIGHER_TIMEFRAME,
        CANDLE_COUNT
    )

    if higher_df is None or len(higher_df) < 60:

        await update.message.reply_text(
            "❌ HIGHER TIMEFRAME DATA LAMA HELIN\n\n"

            f"Asset: {asset}\n"
            f"Higher TF: {timeframe_name(HIGHER_TIMEFRAME)}\n\n"

            "Bot-ku ma sameynayo signal been ah."
        )

        return

    # =====================================================
    # MAIN INDICATORS
    # =====================================================

    df["MA10"] = df["close"].rolling(10).mean()
    df["MA50"] = df["close"].rolling(50).mean()
    df["RSI"] = calculate_rsi(df["close"])

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    price = float(latest["close"])

    ma10 = float(latest["MA10"])
    ma50 = float(latest["MA50"])

    rsi = float(latest["RSI"])

    # =====================================================
    # TREND
    # =====================================================

    if ma10 > ma50:
        trend = "CALL"

    elif ma10 < ma50:
        trend = "PUT"

    else:
        trend = "WAIT"

    # =====================================================
    # RSI
    # =====================================================

    if rsi >= 50:
        rsi_signal = "CALL"

    else:
        rsi_signal = "PUT"

    # =====================================================
    # CURRENT CANDLE
    # =====================================================

    current_candle = candle_direction(latest)

    # =====================================================
    # PREVIOUS CANDLE
    # =====================================================

    previous_candle = candle_direction(previous)

    # =====================================================
    # HIGHER TIMEFRAME
    # =====================================================

    higher_latest = higher_df.iloc[-1]

    higher_candle = candle_direction(
        higher_latest
    )

    higher_signal = higher_candle

    # =====================================================
    # CONFIRMATIONS
    # =====================================================

    checks = [
        trend,
        rsi_signal,
        current_candle,
        previous_candle,
        higher_signal,
    ]

    call_count = checks.count("CALL")
    put_count = checks.count("PUT")

    if call_count >= 4:

        final_signal = "CALL"
        final_text = "🟢 CALL — STRONG CONFIRMATION"

    elif put_count >= 4:

        final_signal = "PUT"
        final_text = "🔴 PUT — STRONG CONFIRMATION"

    else:

        final_signal = "WAIT"
        final_text = "⚪ WAIT — NO STRONG CONFIRMATION"

    # =====================================================
    # RSI DISPLAY
    # =====================================================

    rsi_emoji = "🟢" if rsi_signal == "CALL" else "🔴"

    # =====================================================
    # FINAL MESSAGE
    # =====================================================

    message = (
        "📊 LALAA24BOT SIGNAL\n\n"

        f"💱 Asset: {asset}\n\n"

        "📌 FINAL SIGNAL:\n"
        f"{final_text}\n\n"

        "🔎 CONFIRMATION CHECK\n\n"

        "📈 Trend — MA10 + MA50:\n"
        f"{trend}\n\n"

        "📊 Momentum — RSI:\n"
        f"{rsi_signal} ({rsi_emoji} RSI {rsi:.2f})\n\n"

        "🕯 Candle confirmation:\n"
        f"{current_candle} "
        f"({candle_emoji(current_candle)})\n"
        f"Current: {candle_text(current_candle)}\n\n"

        "🔎 Previous candle confirmation:\n"
        f"{previous_candle} "
        f"({candle_emoji(previous_candle)})\n"
        f"Previous: {candle_text(previous_candle)}\n\n"

        "⏱ Higher Timeframe confirmation:\n"
        f"{higher_signal} {candle_emoji(higher_signal)}\n"
        f"Higher TF: {timeframe_name(HIGHER_TIMEFRAME)}\n"
        f"Higher candle: {candle_text(higher_signal)}\n\n"

        "📊 CONFIRMATION RESULT\n"
        f"🟢 CALL confirmations: {call_count}/5\n"
        f"🔴 PUT confirmations: {put_count}/5\n\n"

        f"💰 Price: {format_price(price)}\n"
        f"MA10: {format_price(ma10)}\n"
        f"MA50: {format_price(ma50)}\n"
        f"RSI: {rsi:.2f}\n\n"

        f"⏱ Timeframe: {timeframe_name(timeframe)}\n"
        f"⌛ Expiry: {expiry_name(expiry)}\n\n"

        "⚠️ Signal-ku waa technical confirmation oo keliya.\n"
        "⚠️ 95% win lama dammaanad qaadi karo."
    )

    await update.message.reply_text(
        message,
        reply_markup=main_keyboard()
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text.strip()
    upper = text.upper()

    # SIGNAL
    if "SIGNAL" in upper:

        await signal_command(update, context)
        return

    # PAIRS
    if "PAIRS" in upper:

        await pairs_command(update, context)
        return

    # TIMEFRAME
    if "TIMEFRAME" in upper:

        await timeframe_menu(update, context)
        return

    # EXPIRY
    if "EXPIRY" in upper:

        await expiry_menu(update, context)
        return

    # STATUS
    if "STATUS" in upper:

        await status_command(update, context)
        return

    # BACK
    if "BACK" in upper:

        await update.message.reply_text(
            "🔙 Main menu",
            reply_markup=main_keyboard()
        )
        return

    # TIMEFRAME BUTTONS
    if text == "1️⃣ 1 Minute":

        await set_timeframe(update, 60)
        return

    if text == "3️⃣ 3 Minutes":

        # This button is shared by both menus.
        # If user is in expiry menu, expiry should be handled
        # by explicit expiry command or the expiry buttons below.
        await set_timeframe(update, 180)
        return

    if text == "5️⃣ 5 Minutes":

        await set_timeframe(update, 300)
        return

    if text == "1️⃣5️⃣ 15 Minutes":

        await set_timeframe(update, 900)
        return

    if text == "3️⃣0️⃣ 30 Minutes":

        await set_timeframe(update, 1800)
        return

    if text == "1️⃣ Hour":

        await set_timeframe(update, 3600)
        return

    # EXPIRY BUTTONS
    if text == "🔟 10 Minutes":

        await set_expiry(update, 600)
        return

    # Because 1/3/5/15 minute labels overlap with timeframe,
    # commands below provide guaranteed independent expiry selection.

    await update.message.reply_text(
        "❓ Amarka lama fahmin.\n\n"
        "Isticmaal menu-ga hoose.",
        reply_markup=main_keyboard()
    )


# =========================================================
# EXPIRY COMMAND
# =========================================================

async def expiry_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "⌛ EXPIRY\n\n"
            "/expiry 60  → 1 Minute\n"
            "/expiry 180 → 3 Minutes\n"
            "/expiry 300 → 5 Minutes\n"
            "/expiry 600 → 10 Minutes\n"
            "/expiry 900 → 15 Minutes"
        )

        return

    try:

        seconds = int(context.args[0])

    except Exception:

        await update.message.reply_text(
            "❌ Geli tiro sax ah."
        )

        return

    allowed = [60, 180, 300, 600, 900]

    if seconds not in allowed:

        await update.message.reply_text(
            "❌ Expiry-ga la oggol yahay:\n\n"
            "60\n"
            "180\n"
            "300\n"
            "600\n"
            "900"
        )

        return

    await set_expiry(
        update,
        seconds
    )


# =========================================================
# APPLICATION
# =========================================================

def main():

    if not TOKEN:

        print("ERROR: TELEGRAM_BOT_TOKEN is missing")
        return

    web_thread = Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    application = (
        Application.builder()
        .token(TOKEN)
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
            status_command
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
            pairs_command
        )
    )

    application.add_handler(
        CommandHandler(
            "pairs",
            pairs_command
        )
    )

    application.add_handler(
        CommandHandler(
            "asset",
            asset_command
        )
    )

    application.add_handler(
        CommandHandler(
            "expiry",
            expiry_command
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    print("NaasirFx bot is running...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
