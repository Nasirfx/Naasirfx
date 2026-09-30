import os
import asyncio
import numpy as np
import pandas as pd

from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
DEFAULT_TIMEFRAME = 180
DEFAULT_EXPIRY = 180

HIGHER_TIMEFRAME = 300
CANDLE_COUNT = 100


# =========================================================
# WEB SERVER FOR RENDER
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
# MAIN KEYBOARD
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
# NAMES
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
# ASSET LIST
# =========================================================

def get_asset_list():

    try:

        if isinstance(ASSETS, dict):
            assets = list(ASSETS.keys())

        elif isinstance(ASSETS, (list, tuple, set)):
            assets = list(ASSETS)

        else:
            assets = []

        return sorted(
            list(dict.fromkeys(str(x) for x in assets))
        )

    except Exception as e:

        print("ASSET LIST ERROR:", e)
        return []


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    settings = get_settings(
        update.effective_user.id
    )

    await update.message.reply_text(

        "👋 Salaam sxbow!\n\n"

        "🤖 NAASIRFX SIGNAL BOT\n\n"

        f"💱 Pair: {settings['asset']}\n"
        f"⏱ Timeframe: {timeframe_name(settings['timeframe'])}\n"
        f"⌛ Expiry: {expiry_name(settings['expiry'])}\n\n"

        "📌 Pair-ka adiga ayaa dooranaya.\n"
        "📌 Timeframe-ka adiga ayaa dooranaya.\n"
        "📌 Expiry-ga adiga ayaa dooranaya.\n\n"

        "⚠️ Automatic pair selection ma jiro.\n"
        "⚠️ Auto-trading ma jiro.",

        reply_markup=main_keyboard()
    )


# =========================================================
# PAIRS MENU
# =========================================================

async def pairs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    assets = get_asset_list()

    if not assets:

        await update.message.reply_text(
            "❌ Pair-yada lama helin."
        )

        return

    user_id = update.effective_user.id
    settings = get_settings(user_id)
    current = settings["asset"]

    buttons = []

    row = []

    for asset in assets:

        if asset == current:
            text = f"✅ {asset}"
        else:
            text = asset

        row.append(
            InlineKeyboardButton(
                text,
                callback_data=f"PAIR|{asset}"
            )
        )

        if len(row) == 2:

            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(
            "🔙 BACK",
            callback_data="BACK"
        )
    ])

    await update.message.reply_text(

        "📋 PAIR SELECTION\n\n"

        f"Current Pair: {current}\n\n"

        "👇 Dooro pair-ka aad rabto:\n"
        "Automatic pair selection ma jiro.",

        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================================================
# TIMEFRAME MENU
# =========================================================

async def timeframe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    buttons = [
        [
            InlineKeyboardButton(
                "1️⃣ 1 Minute",
                callback_data="TF|60"
            ),
            InlineKeyboardButton(
                "3️⃣ 3 Minutes",
                callback_data="TF|180"
            ),
        ],
        [
            InlineKeyboardButton(
                "5️⃣ 5 Minutes",
                callback_data="TF|300"
            ),
            InlineKeyboardButton(
                "1️⃣5️⃣ 15 Minutes",
                callback_data="TF|900"
            ),
        ],
        [
            InlineKeyboardButton(
                "3️⃣0️⃣ 30 Minutes",
                callback_data="TF|1800"
            ),
            InlineKeyboardButton(
                "1️⃣ Hour",
                callback_data="TF|3600"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 BACK",
                callback_data="BACK"
            )
        ]
    ]

    settings = get_settings(
        update.effective_user.id
    )

    await update.message.reply_text(

        "⏱ TIMEFRAME\n\n"

        f"Current: {timeframe_name(settings['timeframe'])}\n\n"

        "Dooro timeframe-ka.\n"
        "📌 Expiry-ga ma beddelayo.",

        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================================================
# EXPIRY MENU
# =========================================================

async def expiry_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    buttons = [
        [
            InlineKeyboardButton(
                "1️⃣ 1 Minute",
                callback_data="EXP|60"
            ),
            InlineKeyboardButton(
                "3️⃣ 3 Minutes",
                callback_data="EXP|180"
            ),
        ],
        [
            InlineKeyboardButton(
                "5️⃣ 5 Minutes",
                callback_data="EXP|300"
            ),
            InlineKeyboardButton(
                "🔟 10 Minutes",
                callback_data="EXP|600"
            ),
        ],
        [
            InlineKeyboardButton(
                "1️⃣5️⃣ 15 Minutes",
                callback_data="EXP|900"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 BACK",
                callback_data="BACK"
            )
        ]
    ]

    settings = get_settings(
        update.effective_user.id
    )

    await update.message.reply_text(

        "⌛ EXPIRY\n\n"

        f"Current: {expiry_name(settings['expiry'])}\n\n"

        "Dooro expiry-ga.\n"
        "📌 Timeframe-ka ma beddelayo.",

        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================================================
# CALLBACK BUTTONS
# =========================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = update.effective_user.id
    settings = get_settings(user_id)

    data = query.data

    # -----------------------------------------------------
    # PAIR
    # -----------------------------------------------------

    if data.startswith("PAIR|"):

        asset = data.split("|", 1)[1]

        assets = get_asset_list()

        if asset not in assets:

            await query.edit_message_text(
                "❌ Pair-kan hadda lama helin."
            )

            return

        settings["asset"] = asset

        await query.edit_message_text(

            "✅ PAIR WAA LA DOORTAY\n\n"

            f"💱 Pair: {asset}\n"
            f"⏱ Timeframe: "
            f"{timeframe_name(settings['timeframe'])}\n"
            f"⌛ Expiry: "
            f"{expiry_name(settings['expiry'])}\n\n"

            "📌 Pair-ku automatic ma beddelmayo."
        )

        return

    # -----------------------------------------------------
    # TIMEFRAME
    # -----------------------------------------------------

    if data.startswith("TF|"):

        seconds = int(
            data.split("|", 1)[1]
        )

        settings["timeframe"] = seconds

        await query.edit_message_text(

            "✅ TIMEFRAME WAA LA DOORTAY\n\n"

            f"⏱ Timeframe: {timeframe_name(seconds)}\n"
            f"💱 Pair: {settings['asset']}\n"
            f"⌛ Expiry: "
            f"{expiry_name(settings['expiry'])}\n\n"

            "📌 Expiry-ga isma beddelin."
        )

        return

    # -----------------------------------------------------
    # EXPIRY
    # -----------------------------------------------------

    if data.startswith("EXP|"):

        seconds = int(
            data.split("|", 1)[1]
        )

        settings["expiry"] = seconds

        await query.edit_message_text(

            "✅ EXPIRY WAA LA DOORTAY\n\n"

            f"⌛ Expiry: {expiry_name(seconds)}\n"
            f"💱 Pair: {settings['asset']}\n"
            f"⏱ Timeframe: "
            f"{timeframe_name(settings['timeframe'])}\n\n"

            "📌 Timeframe-ku isma beddelin."
        )

        return

    # -----------------------------------------------------
    # BACK
    # -----------------------------------------------------

    if data == "BACK":

        await query.edit_message_text(
            "🔙 Ku noqo main menu."
        )

        return


# =========================================================
# STATUS
# =========================================================

async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    settings = get_settings(
        update.effective_user.id
    )

    token_status = (
        "✅ OK"
        if TOKEN
        else "❌ MISSING"
    )

    ssid_status = (
        "✅ OK"
        if POCKET_SSID
        else "❌ MISSING"
    )

    await update.message.reply_text(

        "🤖 NAASIRFX STATUS\n\n"

        f"Telegram Token: {token_status}\n"
        f"Pocket Option SSID: {ssid_status}\n\n"

        f"💱 Pair: {settings['asset']}\n"
        f"⏱ Timeframe: "
        f"{timeframe_name(settings['timeframe'])}\n"
        f"⌛ Expiry: "
        f"{expiry_name(settings['expiry'])}\n\n"

        f"📋 Asset catalog: "
        f"{len(get_asset_list())}"
    )


# =========================================================
# GET CANDLES
# =========================================================

async def get_candles(
    asset,
    timeframe,
    count=CANDLE_COUNT
):

    client = None

    try:

        if not POCKET_SSID:
            return None

        client = AsyncPocketOptionClient(
            POCKET_SSID,
            is_demo=True
        )

        result = await client.connect()

        if not result:
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

                if hasattr(candle, "open"):

                    rows.append({
                        "open": float(candle.open),
                        "high": float(candle.high),
                        "low": float(candle.low),
                        "close": float(candle.close),
                    })

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

def calculate_rsi(
    series,
    period=14
):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    return 100 - (
        100 / (1 + rs)
    )


# =========================================================
# CANDLE
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
# SIGNAL
# =========================================================

async def signal_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id
    settings = get_settings(user_id)

    asset = settings["asset"]
    timeframe = settings["timeframe"]
    expiry = settings["expiry"]

    await update.message.reply_text(

        "🔎 SIGNAL-KA WAA LA BAARAYAA...\n\n"

        f"💱 Pair: {asset}\n"
        f"⏱ Timeframe: "
        f"{timeframe_name(timeframe)}\n"
        f"⌛ Expiry: "
        f"{expiry_name(expiry)}"
    )

    # Main timeframe candles
    df = await get_candles(
        asset,
        timeframe,
        CANDLE_COUNT
    )

    if df is None or len(df) < 60:

        await update.message.reply_text(

            "❌ DATA LAMA HELIN\n\n"

            f"Asset: {asset}\n"
            f"Timeframe: "
            f"{timeframe_name(timeframe)}\n\n"

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
            f"Higher TF: "
            f"{timeframe_name(HIGHER_TIMEFRAME)}\n\n"

            "Bot-ku ma sameynayo signal been ah."
        )

        return

    # -----------------------------------------------------
    # INDICATORS
    # -----------------------------------------------------

    df["MA10"] = (
        df["close"].rolling(10).mean()
    )

    df["MA50"] = (
        df["close"].rolling(50).mean()
    )

    df["RSI"] = calculate_rsi(
        df["close"]
    )

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    price = float(latest["close"])
    ma10 = float(latest["MA10"])
    ma50 = float(latest["MA50"])
    rsi = float(latest["RSI"])

    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------

    if ma10 > ma50:
        trend = "CALL"

    elif ma10 < ma50:
        trend = "PUT"

    else:
        trend = "WAIT"

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    if rsi >= 50:
        rsi_signal = "CALL"
    else:
        rsi_signal = "PUT"

    # -----------------------------------------------------
    # CANDLES
    # -----------------------------------------------------

    current_candle = candle_direction(
        latest
    )

    previous_candle = candle_direction(
        previous
    )

    higher_latest = higher_df.iloc[-1]

    higher_signal = candle_direction(
        higher_latest
    )

    # -----------------------------------------------------
    # CONFIRMATIONS
    # -----------------------------------------------------

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

        final_text = (
            "🟢 CALL — STRONG CONFIRMATION"
        )

    elif put_count >= 4:

        final_text = (
            "🔴 PUT — STRONG CONFIRMATION"
        )

    else:

        final_text = (
            "⚪ WAIT — NO STRONG CONFIRMATION"
        )

    # -----------------------------------------------------
    # MESSAGE
    # -----------------------------------------------------

    message = (

        "📊 NAASIRFX SIGNAL\n\n"

        f"💱 Asset: {asset}\n\n"

        "📌 FINAL SIGNAL:\n"
        f"{final_text}\n\n"

        "🔎 CONFIRMATION CHECK\n\n"

        "📈 Trend — MA10 + MA50:\n"
        f"{trend}\n\n"

        "📊 Momentum — RSI:\n"
        f"{rsi_signal} "
        f"({candle_emoji(rsi_signal)} "
        f"RSI {rsi:.2f})\n\n"

        "🕯 Candle confirmation:\n"
        f"{current_candle} "
        f"({candle_emoji(current_candle)})\n"
        f"Current: "
        f"{candle_text(current_candle)}\n\n"

        "🔎 Previous candle confirmation:\n"
        f"{previous_candle} "
        f"({candle_emoji(previous_candle)})\n"
        f"Previous: "
        f"{candle_text(previous_candle)}\n\n"

        "⏱ Higher Timeframe confirmation:\n"
        f"{higher_signal} "
        f"{candle_emoji(higher_signal)}\n"
        f"Higher TF: "
        f"{timeframe_name(HIGHER_TIMEFRAME)}\n"
        f"Higher candle: "
        f"{candle_text(higher_signal)}\n\n"

        "📊 CONFIRMATION RESULT\n"
        f"🟢 CALL confirmations: "
        f"{call_count}/5\n"
        f"🔴 PUT confirmations: "
        f"{put_count}/5\n\n"

        f"💰 Price: "
        f"{format_price(price)}\n"
        f"MA10: "
        f"{format_price(ma10)}\n"
        f"MA50: "
        f"{format_price(ma50)}\n"
        f"RSI: {rsi:.2f}\n\n"

        f"⏱ Timeframe: "
        f"{timeframe_name(timeframe)}\n"
        f"⌛ Expiry: "
        f"{expiry_name(expiry)}\n\n"

        "⚠️ Signal-ku waa technical "
        "confirmation .\n"
        "⚠️ 95% win la qaadi karo."
    )

    await update.message.reply_text(
        message,
        reply_markup=main_keyboard()
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()
    upper = text.upper()

    if "SIGNAL" in upper:

        await signal_command(
            update,
            context
        )

        return

    if "PAIRS" in upper:

        await pairs_menu(
            update,
            context
        )

        return

    if "TIMEFRAME" in upper:

        await timeframe_menu(
            update,
            context
        )

        return

    if "EXPIRY" in upper:

        await expiry_menu(
            update,
            context
        )

        return

    if "STATUS" in upper:

        await status_command(
            update,
            context
        )

        return

    await update.message.reply_text(
        "❓ Dooro button-ka aad rabto.",
        reply_markup=main_keyboard()
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not TOKEN:

        print(
            "ERROR: TELEGRAM_BOT_TOKEN is missing"
        )

        return

    Thread(
        target=run_web_server,
        daemon=True
    ).start()

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
            "pairs",
            pairs_menu
        )
    )

    application.add_handler(
        CommandHandler(
            "assets",
            pairs_menu
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    print("NaasirFx is running...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
