import os
import json
import asyncio
import time
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
# ENVIRONMENT
# =========================================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PO_SSID = os.getenv("PO_SSID")

CONNECT_TIMEOUT = 45
CONNECT_RETRIES = 3


# =========================================================
# DEMO MODE
# =========================================================

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


# =========================================================
# POCKET OPTION CONNECTION
# =========================================================

async def connect_client():

    if not PO_SSID:
        raise RuntimeError("PO_SSID lama helin.")

    demo_mode = detect_demo_mode(PO_SSID)

    print(
        f"🔵 PO CONNECT: SSID waa jiraa "
        f"(length={len(PO_SSID)})",
        flush=True
    )

    print(
        f"🔵 PO AUTH: SSID isDemo={demo_mode}",
        flush=True
    )

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

            print(
                f"🔵 PO CONNECT: attempt "
                f"{attempt}/{CONNECT_RETRIES}...",
                flush=True
            )

            result = await asyncio.wait_for(
                client.connect(),
                timeout=CONNECT_TIMEOUT
            )

            last_result = result

            print(
                f"🟢 PO CONNECT: connect() returned: "
                f"{result!r}",
                flush=True
            )

            if result is True:

                print(
                    "🟢 PO CONNECT: connection READY.",
                    flush=True
                )

                return client

            stats_method = getattr(
                client,
                "get_connection_stats",
                None
            )

            if callable(stats_method):

                try:

                    stats = await stats_method()

                    print(
                        f"🔵 PO CONNECT STATS: {stats}",
                        flush=True
                    )

                    if (
                        stats.get("websocket_connected")
                        or stats.get("connected")
                    ):
                        return client

                except Exception as stats_error:

                    print(
                        f"🟡 PO STATS ERROR: "
                        f"{stats_error}",
                        flush=True
                    )

            raise RuntimeError(
                f"connect() returned {result!r}"
            )

        except asyncio.TimeoutError:

            last_error = (
                f"connection timeout after "
                f"{CONNECT_TIMEOUT}s"
            )

            print(
                f"🔴 PO CONNECT TIMEOUT: "
                f"{last_error}",
                flush=True
            )

        except Exception as e:

            last_error = (
                f"{type(e).__name__}: {e}"
            )

            print(
                f"🔴 PO CONNECT ERROR: "
                f"{last_error}",
                flush=True
            )

        finally:

            if client is not None and last_result is not True:

                try:
                    await client.disconnect()
                except Exception:
                    pass

        if attempt < CONNECT_RETRIES:
            await asyncio.sleep(3)

    raise RuntimeError(
        f"Pocket Option connection failed after "
        f"{CONNECT_RETRIES} attempts. "
        f"Last result={last_result!r}; "
        f"last error={last_error}"
    )


# =========================================================
# TIMEFRAME
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
# EXPIRY
# IMPORTANT:
# EXPIRY BUTTONS ARE DIFFERENT FROM TIMEFRAME BUTTONS
# =========================================================

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
# FOREX
# =========================================================

FOREX_ASSETS = {

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

FOREX_OTC_ASSETS = {

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
}


# =========================================================
# STOCKS
# =========================================================

STOCK_ASSETS = {}


def load_stock_assets():

    stocks = {}

    try:

        for symbol in PO_ASSETS:

            symbol = str(symbol)

            if not symbol.startswith("#"):
                continue

            label = symbol[1:]

            if label.lower().endswith("_otc"):
                label = label[:-4] + " OTC"

            stocks[label] = symbol

    except Exception as e:

        print(
            f"🔴 STOCK LOAD ERROR: {e}",
            flush=True
        )

    return stocks


STOCK_ASSETS = load_stock_assets()


# =========================================================
# USER STATE
# =========================================================

user_category = {}
user_assets = {}
user_selected_code = {}
user_selected_name = {}
user_timeframe = {}
user_expiry = {}


# =========================================================
# BUTTON ROWS
# =========================================================

def button_rows(items, size=2):

    rows = []
    row = []

    for item in items:

        row.append(item)

        if len(row) == size:

            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return rows


# =========================================================
# GET SIGNAL
# =========================================================

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

        df = await client.get_candles_dataframe(
            asset=asset_code,
            timeframe=timeframe
        )

        if df is None or len(df) == 0:

            return (
                "❌ DATA LAMA HELIN\n\n"
                f"Asset: {asset_code}\n"
                f"Timeframe: {timeframe_name}\n\n"
                "Pair-kan candles lagama helin."
            )

        required_columns = {
            "open",
            "close"
        }

        if not required_columns.issubset(df.columns):

            return (
                "❌ CANDLE DATA AAN DHAMMEYSTIRNAYN\n\n"
                f"Asset: {asset_code}\n"
                f"Timeframe: {timeframe_name}"
            )

        if len(df) < 55:

            return (
                "❌ CANDLES KU FILAN LAMA HELIN\n\n"
                f"Asset: {asset_code}\n"
                f"Timeframe: {timeframe_name}\n"
                f"Candles la helay: {len(df)}\n\n"
                "Ugu yaraan 55 candles ayaa loo baahan yahay."
            )

        df = df.copy()

        df["close"] = pd.to_numeric(
            df["close"],
            errors="coerce"
        )

        df["open"] = pd.to_numeric(
            df["open"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["open", "close"]
        )

        if len(df) < 55:

            return (
                "❌ CANDLES KU FILAN LAMA HELIN\n\n"
                f"Asset: {asset_code}"
            )

        # =================================================
        # MA10
        # =================================================

        df["MA10"] = (
            df["close"]
            .rolling(10)
            .mean()
        )

        # =================================================
        # MA50
        # =================================================

        df["MA50"] = (
            df["close"]
            .rolling(50)
            .mean()
        )

        # =================================================
        # RSI 14
        # =================================================

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

        # =================================================
        # SIGNAL
        # =================================================

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

        # =================================================
        # CANDLE
        # =================================================

        if bullish_candle:

            candle = "Bullish 🟢"

        elif bearish_candle:

            candle = "Bearish 🔴"

        else:

            candle = "Neutral 🟡"

        # =================================================
        # RESULT
        # =================================================

        return (
            "📊 NAASIRFX SIGNAL\n\n"

            f"💱 Asset: {asset_code}\n"
            f"📌 Signal: {signal}\n\n"

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
            b"NaasirFx is running!"
        )

    def log_message(
        self,
        format,
        *args
    ):
        pass


def run_server():

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

    print(
        f"🟢 HTTP SERVER RUNNING ON 0.0.0.0:{port}",
        flush=True
    )

    server.serve_forever()


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    return ReplyKeyboardMarkup(
        [
            ["📊 SIGNAL", "📋 PAIRS"],
            ["⏱ TIMEFRAME", "⌛ EXPIRY"],
        ],
        resize_keyboard=True
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Soo dhawoow NaasirFx.\n\n"
        "📊 Dooro Pair, Timeframe iyo Expiry.",
        reply_markup=main_menu()
    )


# =========================================================
# PAIR CATEGORIES
# =========================================================

async def show_pair_categories(
    update: Update
):

    keyboard = [
        ["💱 FOREX"],
        ["💱 FOREX OTC"],
        ["📈 STOCKS"],
        ["🔙 BACK"],
    ]

    await update.message.reply_text(
        "📋 PAIRS\n\n"
        "Dooro qaybta Pair-ka:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


# =========================================================
# SHOW PAIRS
# =========================================================

async def show_pairs(
    update: Update,
    category_key
):

    user_id = update.effective_user.id

    if category_key == "FOREX":

        assets = FOREX_ASSETS
        category = "💱 Forex"
        title = "💱 FOREX"

    elif category_key == "OTC":

        assets = FOREX_OTC_ASSETS
        category = "💱 Forex OTC"
        title = "💱 FOREX OTC"

    elif category_key == "STOCKS":

        assets = STOCK_ASSETS
        category = "📈 Stocks"
        title = "📈 STOCKS"

    else:

        return

    if not assets:

        await update.message.reply_text(
            "❌ Pairs lama helin qaybtaan."
        )

        return

    user_category[user_id] = category

    user_assets[user_id] = dict(assets)

    rows = button_rows(
        list(assets.keys()),
        2
    )

    rows.append(
        ["🔙 BACK"]
    )

    await update.message.reply_text(
        f"{title}\n\n"
        f"📊 {len(assets)} pairs/assets\n\n"
        "Dooro Pair-ka aad rabto.\n"
        "📌 Pair-ku automatic uma beddelmayo.",
        reply_markup=ReplyKeyboardMarkup(
            rows,
            resize_keyboard=True
        )
    )


# =========================================================
# TIMEFRAME
# =========================================================

async def show_timeframes(
    update: Update
):

    user_id = update.effective_user.id

    current = user_timeframe.get(
        user_id
    )

    rows = button_rows(
        list(TIMEFRAMES.keys()),
        2
    )

    rows.append(
        ["🔙 BACK"]
    )

    text = (
        "⏱ TIMEFRAME\n\n"
    )

    if current:

        text += (
            f"Current: {current}\n\n"
        )

    text += (
        "Dooro Timeframe-ka:\n\n"
        "📌 Timeframe-ku Expiry-ga ma beddelayo."
    )

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(
            rows,
            resize_keyboard=True
        )
    )


# =========================================================
# EXPIRY
# =========================================================

async def show_expiries(
    update: Update
):

    user_id = update.effective_user.id

    current = user_expiry.get(
        user_id
    )

    rows = button_rows(
        list(EXPIRIES.keys()),
        2
    )

    rows.append(
        ["🔙 BACK"]
    )

    text = (
        "⌛ EXPIRY\n\n"
    )

    if current:

        text += (
            f"Current: {current}\n\n"
        )

    text += (
        "Dooro Expiry-ga:\n\n"
        "📌 Expiry-ga Timeframe-ka ma beddelayo."
    )

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(
            rows,
            resize_keyboard=True
        )
    )


# =========================================================
# SEND SIGNAL
# =========================================================

async def send_signal(
    update: Update
):

    user_id = update.effective_user.id

    asset_code = user_selected_code.get(
        user_id
    )

    asset_name = user_selected_name.get(
        user_id
    )

    if not asset_code:

        await update.message.reply_text(
            "❌ Marka hore 📋 PAIRS ka dooro Pair."
        )

        return

    timeframe_name = user_timeframe.get(
        user_id
    )

    if not timeframe_name:

        await update.message.reply_text(
            "❌ Marka hore ⏱ TIMEFRAME dooro."
        )

        return

    expiry_name = user_expiry.get(
        user_id
    )

    if not expiry_name:

        await update.message.reply_text(
            "❌ Marka hore ⌛ EXPIRY dooro."
        )

        return

    timeframe = TIMEFRAMES[
        timeframe_name
    ]

    await update.message.reply_text(

        "⏳ Signal-ka waa la baarayaa...\n\n"

        f"💱 Pair: {asset_name}\n"
        f"🔑 API Code: {asset_code}\n"
        f"⏱ Timeframe: {timeframe_name}\n"
        f"⌛ Expiry: {expiry_name}"
    )

    signal = await get_signal(
        asset_code,
        timeframe,
        timeframe_name,
        expiry_name
    )

    await update.message.reply_text(
        signal,
        reply_markup=main_menu()
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

    text = update.message.text
    user_id = update.effective_user.id

    # -----------------------------------------------------
    # MAIN MENU
    # -----------------------------------------------------

    if text == "📋 PAIRS":

        await show_pair_categories(update)
        return

    if text == "⏱ TIMEFRAME":

        await show_timeframes(update)
        return

    if text == "⌛ EXPIRY":

        await show_expiries(update)
        return

    if text == "📊 SIGNAL":

        await send_signal(update)
        return

    # -----------------------------------------------------
    # BACK
    # -----------------------------------------------------

    if text == "🔙 BACK":

        await update.message.reply_text(
            "🏠 Main Menu",
            reply_markup=main_menu()
        )

        return

    # -----------------------------------------------------
    # PAIR CATEGORIES
    # -----------------------------------------------------

    if text == "💱 FOREX":

        await show_pairs(
            update,
            "FOREX"
        )

        return

    if text == "💱 FOREX OTC":

        await show_pairs(
            update,
            "OTC"
        )

        return

    if text == "📈 STOCKS":

        await show_pairs(
            update,
            "STOCKS"
        )

        return

    # -----------------------------------------------------
    # TIMEFRAME
    # -----------------------------------------------------

    if text in TIMEFRAMES:

        user_timeframe[user_id] = text

        await update.message.reply_text(

            "✅ TIMEFRAME WAA LA DOORTAY\n\n"

            f"⏱ {text}\n\n"

            "⌛ Expiry-ga isma beddelin.",

            reply_markup=main_menu()
        )

        return

    # -----------------------------------------------------
    # EXPIRY
    # -----------------------------------------------------

    if text in EXPIRIES:

        user_expiry[user_id] = text

        await update.message.reply_text(

            "✅ EXPIRY WAA LA DOORTAY\n\n"

            f"⌛ {text}\n\n"

            "⏱ Timeframe-ka isma beddelin.",

            reply_markup=main_menu()
        )

        return

    # -----------------------------------------------------
    # PAIR SELECTION
    # -----------------------------------------------------

    assets = user_assets.get(
        user_id,
        {}
    )

    if text in assets:

        user_selected_code[user_id] = (
            assets[text]
        )

        user_selected_name[user_id] = text

        await update.message.reply_text(

            "✅ PAIR WAA LA DOORTAY\n\n"

            f"💱 Pair: {text}\n"
            f"🔑 API Code: {assets[text]}\n\n"

            f"⏱ Timeframe: "
            f"{user_timeframe.get(user_id, 'Lama dooran')}\n"

            f"⌛ Expiry: "
            f"{user_expiry.get(user_id, 'Lama dooran')}\n\n"

            "📌 Pair-ku automatic uma beddelmayo.",

            reply_markup=main_menu()
        )

        return

    # -----------------------------------------------------
    # UNKNOWN
    # -----------------------------------------------------

    await update.message.reply_text(
        "❌ Fadlan ka dooro menu-ga hoose.",
        reply_markup=main_menu()
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # RENDER SERVER
    # -----------------------------------------------------

    Thread(
        target=run_server,
        daemon=True
    ).start()

    print(
        "🟡 Starting NaasirFx...",
        flush=True
    )

    # -----------------------------------------------------
    # TELEGRAM TOKEN
    # -----------------------------------------------------

    if not TOKEN:

        print(
            "❌ TELEGRAM_BOT_TOKEN lama helin!",
            flush=True
        )

        return

    print(
        "🟢 Telegram token waa la helay.",
        flush=True
    )

    # -----------------------------------------------------
    # PO SSID
    # -----------------------------------------------------

    if not PO_SSID:

        print(
            "⚠️ PO_SSID lama helin!",
            flush=True
        )

    else:

        print(
            f"🟢 PO_SSID waa jiraa "
            f"(length={len(PO_SSID)})",
            flush=True
        )

    # -----------------------------------------------------
    # TELEGRAM APP
    # -----------------------------------------------------

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # HANDLERS
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )

    print(
        "🟢 NAASIRFX IS RUNNING",
        flush=True
    )

    # -----------------------------------------------------
    # POLLING
    # -----------------------------------------------------

    app.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
