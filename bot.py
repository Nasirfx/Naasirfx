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
# GEMINI AI
# =========================================================

try:
    from google import genai
except Exception:
    genai = None


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

AI_MODEL = "gemini-2.5-flash-lite"


# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
POCKET_SSID = os.getenv("POCKET_OPTION_SSID")

DEFAULT_ASSET = "EURUSD_otc"
DEFAULT_TIMEFRAME = 180
DEFAULT_EXPIRY = 180

CANDLE_COUNT = 100


# =========================================================
# FIX OLD ASSET CATALOG
# =========================================================

CNY_OTC_ASSETS = {
    "AEDCNY_otc": 538,
    "BHDCNY_otc": 536,
    "JODCNY_otc": 546,
    "OMRCNY_otc": 544,
    "QARCNY_otc": 542,
    "SARCNY_otc": 540,
}

try:

    if isinstance(ASSETS, dict):

        for asset_name, asset_id in CNY_OTC_ASSETS.items():

            ASSETS.setdefault(
                asset_name,
                asset_id
            )

        print(
            "CNY ASSETS LOADED:",
            list(CNY_OTC_ASSETS.keys()),
            flush=True
        )

except Exception as e:

    print(
        "CNY ASSET LOAD ERROR:",
        repr(e),
        flush=True
    )


# =========================================================
# WEB SERVER FOR RENDER
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

    def log_message(
        self,
        format,
        *args
    ):
        return


def run_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    server.serve_forever()


# =========================================================
# USER SETTINGS
# =========================================================

USER_SETTINGS = {}


def get_settings(user_id):

    if user_id not in USER_SETTINGS:

        USER_SETTINGS[user_id] = {

            "asset": DEFAULT_ASSET,

            "timeframe":
                DEFAULT_TIMEFRAME,

            "expiry":
                DEFAULT_EXPIRY,
        }

    return USER_SETTINGS[user_id]


# =========================================================
# MAIN KEYBOARD
# =========================================================

def main_keyboard():

    keyboard = [

        ["📊 SIGNAL"],

        ["📋 PAIRS"],

        [
            "⏱ TIMEFRAME",
            "⌛ EXPIRY"
        ],

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
# FOREX PAIRS
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
# FOREX OTC PAIRS
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
}


# =========================================================
# STOCK COMPANY NAMES
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
# STOCK OTC COMPANY NAMES
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
# STOCKS
# =========================================================

def get_stock_assets():

    stocks = {}

    try:

        available_assets = {
            str(item)
            for item in ASSETS
        }

        for code, name in STOCK_NAMES.items():

            if code in available_assets:

                stocks[name] = code

        for asset in sorted(
            available_assets
        ):

            if not asset.startswith("#"):
                continue

            if asset.lower().endswith("_otc"):
                continue

            if asset in STOCK_NAMES:
                continue

            stocks[asset] = asset

    except Exception as e:

        print(
            "STOCK LIST ERROR:",
            e,
            flush=True
        )

    return dict(
        sorted(
            stocks.items(),
            key=lambda x: x[0].lower()
        )
    )


# =========================================================
# STOCKS OTC
# =========================================================

def get_stock_otc_assets():

    stocks_otc = {}

    try:

        available_assets = {
            str(item)
            for item in ASSETS
        }

        for code, name in STOCK_OTC_NAMES.items():

            if code in available_assets:

                stocks_otc[name] = code

        for asset in sorted(
            available_assets
        ):

            if not asset.startswith("#"):
                continue

            if not asset.lower().endswith("_otc"):
                continue

            if asset in STOCK_OTC_NAMES:
                continue

            stocks_otc[asset] = asset

    except Exception as e:

        print(
            "STOCK OTC LIST ERROR:",
            e,
            flush=True
        )

    return dict(
        sorted(
            stocks_otc.items(),
            key=lambda x: x[0].lower()
        )
    )


# =========================================================
# ALL SEPARATED PAIRS
# =========================================================

def get_all_pairs():

    return {

        "FOREX": dict(
            FOREX_PAIRS
        ),

        "FOREX_OTC": dict(
            FOREX_OTC_PAIRS
        ),

        "STOCKS": get_stock_assets(),

        "STOCKS_OTC":
            get_stock_otc_assets(),
    }


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

    await update.message.reply_text(

        "👋 Salaam sxbow!\n\n"

        "🤖 NAASIRFX SIGNAL BOT\n\n"

        f"💱 Pair: "
        f"{settings['asset']}\n"

        f"⏱ Timeframe: "
        f"{timeframe_name(settings['timeframe'])}\n"

        f"⌛ Expiry: "
        f"{expiry_name(settings['expiry'])}\n\n"

        "📌 Pair-ka adiga ayaa dooranaya.\n"
        "📌 Timeframe-ka adiga ayaa dooranaya.\n"
        "📌 Expiry-ga adiga ayaa dooranaya.\n\n"

        "🤖 AI confirmation waa shaqaynayaa "
        "haddii GEMINI_API_KEY la geliyo.\n"

        "⚠️ Automatic pair selection ma jiro.\n"
        "⚠️ Auto-trading ma jiro.",

        reply_markup=main_keyboard()
    )


# =========================================================
# PAIRS MENU
# =========================================================

async def pairs_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [

        [
            InlineKeyboardButton(
                "💱 FOREX",
                callback_data="CATEGORY|FOREX"
            )
        ],

        [
            InlineKeyboardButton(
                "💱 FOREX OTC",
                callback_data="CATEGORY|FOREX_OTC"
            )
        ],

        [
            InlineKeyboardButton(
                "📈 STOCKS",
                callback_data="CATEGORY|STOCKS"
            )
        ],

        [
            InlineKeyboardButton(
                "📈 STOCKS OTC",
                callback_data="CATEGORY|STOCKS_OTC"
            )
        ],

        [
            InlineKeyboardButton(
                "🔙 BACK",
                callback_data="BACK"
            )
        ],
    ]

    await update.message.reply_text(

        "📋 PAIRS\n\n"

        "Dooro qaybta aad rabto:\n\n"

        "💱 FOREX\n"
        "💱 FOREX OTC\n"
        "📈 STOCKS\n"
        "📈 STOCKS OTC",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# TIMEFRAME MENU
# =========================================================

async def timeframe_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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
                "4️⃣ Hours",
                callback_data="TF|14400"
            ),
        ],

        [
            InlineKeyboardButton(
                "🔙 BACK",
                callback_data="BACK"
            )
        ],
    ]

    settings = get_settings(
        update.effective_user.id
    )

    await update.message.reply_text(

        "⏱ TIMEFRAME\n\n"

        f"Current: "
        f"{timeframe_name(settings['timeframe'])}\n\n"

        "Dooro timeframe-ka.\n"
        "📌 Expiry-ga ma beddelayo.",

        reply_markup=InlineKeyboardMarkup(
            buttons
        )
    )


# =========================================================
# EXPIRY MENU
# =========================================================

async def expiry_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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
        ],
    ]

    settings = get_settings(
        update.effective_user.id
    )

    await update.message.reply_text(

        "⌛ EXPIRY\n\n"

        f"Current: "
        f"{expiry_name(settings['expiry'])}\n\n"

        "Dooro expiry-ga.\n"
        "📌 Timeframe-ka ma beddelayo.",

        reply_markup=InlineKeyboardMarkup(
            buttons
        )
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

    settings = get_settings(
        user_id
    )

    data = query.data

    # =====================================================
    # PAIR CATEGORY
    # =====================================================

    if data.startswith(
        "CATEGORY|"
    ):

        category = data.split(
            "|",
            1
        )[1]

        all_pairs = get_all_pairs()

        if category == "FOREX":

            title = "💱 FOREX"

            assets = all_pairs["FOREX"]

        elif category == "FOREX_OTC":

            title = "💱 FOREX OTC"

            assets = all_pairs["FOREX_OTC"]

        elif category == "STOCKS":

            title = "📈 STOCKS"

            assets = all_pairs["STOCKS"]

        elif category == "STOCKS_OTC":

            title = "📈 STOCKS OTC"

            assets = all_pairs["STOCKS_OTC"]

        else:

            await query.edit_message_text(
                "❌ Category lama helin."
            )

            return

        if not assets:

            await query.edit_message_text(

                f"{title}\n\n"
                "❌ Pairs lama helin qaybtaan."

            )

            return

        buttons = []

        row = []

        current = settings["asset"]

        for name, code in assets.items():

            if code == current:

                button_text = f"✅ {name}"

            else:

                button_text = name

            row.append(

                InlineKeyboardButton(
                    button_text,
                    callback_data=f"PAIR|{code}"
                )
            )

            if len(row) == 2:

                buttons.append(row)

                row = []

        if row:

            buttons.append(row)

        buttons.append([

            InlineKeyboardButton(
                "🔙 PAIRS",
                callback_data="PAIRS_MENU"
            )
        ])

        await query.edit_message_text(

            f"{title}\n\n"

            f"📊 {len(assets)} pairs/assets\n\n"

            "👇 Dooro Pair-ka:",

            reply_markup=InlineKeyboardMarkup(
                buttons
            )
        )

        return

    # =====================================================
    # BACK TO PAIRS CATEGORIES
    # =====================================================

    if data == "PAIRS_MENU":

        keyboard = [

            [
                InlineKeyboardButton(
                    "💱 FOREX",
                    callback_data="CATEGORY|FOREX"
                )
            ],

            [
                InlineKeyboardButton(
                    "💱 FOREX OTC",
                    callback_data="CATEGORY|FOREX_OTC"
                )
            ],

            [
                InlineKeyboardButton(
                    "📈 STOCKS",
                    callback_data="CATEGORY|STOCKS"
                )
            ],

            [
                InlineKeyboardButton(
                    "📈 STOCKS OTC",
                    callback_data="CATEGORY|STOCKS_OTC"
                )
            ],

            [
                InlineKeyboardButton(
                    "🔙 BACK",
                    callback_data="BACK"
                )
            ],
        ]

        await query.edit_message_text(

            "📋 PAIRS\n\n"
            "Dooro qaybta aad rabto:",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # =====================================================
    # PAIR
    # =====================================================

    if data.startswith(
        "PAIR|"
    ):

        asset = data.split(
            "|",
            1
        )[1]

        all_pairs = get_all_pairs()

        valid_assets = []

        for category_assets in all_pairs.values():

            valid_assets.extend(
                category_assets.values()
            )

        if asset not in valid_assets:

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

    # =====================================================
    # TIMEFRAME
    # =====================================================

    if data.startswith(
        "TF|"
    ):

        seconds = int(
            data.split(
                "|",
                1
            )[1]
        )

        settings["timeframe"] = seconds

        await query.edit_message_text(

            "✅ TIMEFRAME WAA LA DOORTAY\n\n"

            f"⏱ Timeframe: "
            f"{timeframe_name(seconds)}\n"

            f"💱 Pair: "
            f"{settings['asset']}\n"

            f"⌛ Expiry: "
            f"{expiry_name(settings['expiry'])}\n\n"

            "📌 Expiry-ga isma beddelin."
        )

        return

    # =====================================================
    # EXPIRY
    # =====================================================

    if data.startswith(
        "EXP|"
    ):

        seconds = int(
            data.split(
                "|",
                1
            )[1]
        )

        settings["expiry"] = seconds

        await query.edit_message_text(

            "✅ EXPIRY WAA LA DOORTAY\n\n"

            f"⌛ Expiry: "
            f"{expiry_name(seconds)}\n"

            f"💱 Pair: "
            f"{settings['asset']}\n"

            f"⏱ Timeframe: "
            f"{timeframe_name(settings['timeframe'])}\n\n"

            "📌 Timeframe-ku isma beddelin."
        )

        return

    # =====================================================
    # BACK
    # =====================================================

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

    ai_status = (
        "✅ READY"
        if GEMINI_API_KEY and genai
        else "❌ MISSING"
    )

    all_pairs = get_all_pairs()

    total_pairs = sum(
        len(x)
        for x in all_pairs.values()
    )

    await update.message.reply_text(

        "🤖 NAASIRFX STATUS\n\n"

        f"Telegram Token: "
        f"{token_status}\n"

        f"Pocket Option SSID: "
        f"{ssid_status}\n"

        f"Gemini AI: "
        f"{ai_status}\n\n"

        f"💱 Pair: "
        f"{settings['asset']}\n"

        f"⏱ Timeframe: "
        f"{timeframe_name(settings['timeframe'])}\n"

        f"⌛ Expiry: "
        f"{expiry_name(settings['expiry'])}\n\n"

        f"💱 Forex: "
        f"{len(all_pairs['FOREX'])}\n"

        f"💱 Forex OTC: "
        f"{len(all_pairs['FOREX_OTC'])}\n"

        f"📈 Stocks: "
        f"{len(all_pairs['STOCKS'])}\n"

        f"📈 Stocks OTC: "
        f"{len(all_pairs['STOCKS_OTC'])}\n\n"

        f"📋 Total separated pairs: "
        f"{total_pairs}"
    )


# =========================================================
# CANDLE OBJECT TO ROW
# =========================================================

def candle_to_row(candle):

    try:

        if isinstance(candle, dict):

            open_value = candle.get(
                "open",
                candle.get("o")
            )

            high_value = candle.get(
                "high",
                candle.get("h")
            )

            low_value = candle.get(
                "low",
                candle.get("l")
            )

            close_value = candle.get(
                "close",
                candle.get("c")
            )

        else:

            open_value = getattr(
                candle,
                "open",
                getattr(
                    candle,
                    "o",
                    None
                )
            )

            high_value = getattr(
                candle,
                "high",
                getattr(
                    candle,
                    "h",
                    None
                )
            )

            low_value = getattr(
                candle,
                "low",
                getattr(
                    candle,
                    "l",
                    None
                )
            )

            close_value = getattr(
                candle,
                "close",
                getattr(
                    candle,
                    "c",
                    None
                )
            )

        if any(
            value is None
            for value in (
                open_value,
                high_value,
                low_value,
                close_value
            )
        ):

            return None

        return {

            "open": float(open_value),

            "high": float(high_value),

            "low": float(low_value),

            "close": float(close_value),
        }

    except Exception:

        return None


# =========================================================
# CONVERT CANDLES TO DATAFRAME
# =========================================================

def candles_to_dataframe(candles):

    if candles is None:
        return None

    if isinstance(
        candles,
        pd.DataFrame
    ):

        df = candles.copy()

        rename_map = {}

        for column in df.columns:

            lower = str(column).lower()

            if lower == "o":
                rename_map[column] = "open"

            elif lower == "h":
                rename_map[column] = "high"

            elif lower == "l":
                rename_map[column] = "low"

            elif lower == "c":
                rename_map[column] = "close"

        if rename_map:

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

            return None

        for column in required:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df = df.dropna(
            subset=required
        )

        if len(df) < 20:
            return None

        return df[
            required
        ].reset_index(
            drop=True
        )

    if isinstance(
        candles,
        dict
    ):

        for key in (
            "candles",
            "data",
            "result",
            "rows"
        ):

            if key in candles:

                result = candles_to_dataframe(
                    candles[key]
                )

                if result is not None:

                    return result

    if isinstance(
        candles,
        (list, tuple)
    ):

        rows = []

        for candle in candles:

            row = candle_to_row(
                candle
            )

            if row is not None:

                rows.append(row)

        if len(rows) < 20:
            return None

        return pd.DataFrame(
            rows
        ).reset_index(
            drop=True
        )

    try:

        rows = []

        for candle in candles:

            row = candle_to_row(
                candle
            )

            if row is not None:

                rows.append(row)

        if len(rows) >= 20:

            return pd.DataFrame(
                rows
            ).reset_index(
                drop=True
            )

    except Exception:
        pass

    return None


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

            print(
                "CANDLE ERROR: "
                "POCKET_OPTION_SSID missing",
                flush=True
            )

            return None

        client = AsyncPocketOptionClient(
            POCKET_SSID,
            is_demo=True
        )

        print(
            f"CONNECTING TO POCKET OPTION "
            f"FOR {asset}...",
            flush=True
        )

        result = await client.connect()

        if not result:

            print(
                "POCKET OPTION CONNECTION FAILED",
                flush=True
            )

            return None

        print(
            "POCKET OPTION CONNECTED",
            flush=True
        )

        print(
            "CANDLE TRY:",
            asset,
            timeframe,
            count,
            flush=True
        )

        try:

            candles = await client.get_candles(
                asset,
                timeframe,
                count
            )

            df = candles_to_dataframe(
                candles
            )

            if df is not None:

                print(
                    f"CANDLE SUCCESS: "
                    f"{asset} "
                    f"{timeframe}s "
                    f"{len(df)} candles",
                    flush=True
                )

                return df

            print(
                "CANDLE DATA EMPTY:",
                asset,
                flush=True
            )

        except Exception as e:

            print(
                "GET_CANDLES ERROR:",
                asset,
                timeframe,
                repr(e),
                flush=True
            )

        # -------------------------------------------------
        # DATAFRAME FALLBACK
        # -------------------------------------------------

        method = getattr(
            client,
            "get_candles_dataframe",
            None
        )

        if callable(method):

            try:

                print(
                    "DATAFRAME TRY:",
                    asset,
                    timeframe,
                    count,
                    flush=True
                )

                result = await method(
                    asset,
                    timeframe,
                    count
                )

                df = candles_to_dataframe(
                    result
                )

                if df is not None:

                    print(
                        f"DATAFRAME SUCCESS: "
                        f"{asset} "
                        f"{timeframe}s "
                        f"{len(df)} candles",
                        flush=True
                    )

                    return df

            except Exception as e:

                print(
                    "DATAFRAME ERROR:",
                    asset,
                    timeframe,
                    repr(e),
                    flush=True
                )

        print(
            f"ALL CANDLE METHODS FAILED: "
            f"{asset} {timeframe}s",
            flush=True
        )

        return None

    except Exception as e:

        print(
            "CANDLE ERROR:",
            repr(e),
            flush=True
        )

        return None

    finally:

        try:

            if client:

                await client.disconnect()

                print(
                    "POCKET OPTION DISCONNECTED",
                    flush=True
                )

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

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    average_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    average_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = (
        average_gain /
        average_loss.replace(
            0,
            np.nan
        )
    )

    rsi = (
        100 -
        (100 / (1 + rs))
    )

    return rsi.fillna(50)


# =========================================================
# HIGHER TIMEFRAME
# =========================================================

def higher_timeframe_for(
    timeframe
):

    mapping = {

        60: 180,

        180: 300,

        300: 900,

        900: 1800,

        1800: 3600,

        3600: 14400,

        14400: 14400,
    }

    return mapping.get(
        timeframe,
        300
    )


# =========================================================
# SUPPORT & RESISTANCE
# =========================================================

def calculate_support_resistance(
    df,
    lookback=20
):

    try:

        if df is None:
            return None, None

        if len(df) < 5:
            return None, None

        window = df.tail(
            min(
                lookback,
                len(df)
            )
        )

        support = float(
            window["low"].min()
        )

        resistance = float(
            window["high"].max()
        )

        return support, resistance

    except Exception as e:

        print(
            "SUPPORT/RESISTANCE ERROR:",
            repr(e),
            flush=True
        )

        return None, None
# =========================================================
# SUPPORT / RESISTANCE FILTER
# =========================================================

def support_resistance_filter(
    price,
    support,
    resistance,
    signal
):

    try:

        if (
            price is None
            or support is None
            or resistance is None
        ):

            return False

        price = float(price)
        support = float(support)
        resistance = float(resistance)

        if resistance <= support:

            return False

        total_range = (
            resistance - support
        )

        distance_to_support = (
            price - support
        )

        distance_to_resistance = (
            resistance - price
        )

        if signal == "CALL":

            minimum_room = (
                total_range * 0.20
            )

            return (
                distance_to_resistance
                >= minimum_room
            )

        if signal == "PUT":

            minimum_room = (
                total_range * 0.20
            )

            return (
                distance_to_support
                >= minimum_room
            )

        return False

    except Exception as e:

        print(
            "S/R FILTER ERROR:",
            repr(e),
            flush=True
        )

        return False


# =========================================================
# TECHNICAL SIGNAL
# =========================================================

def technical_signal_from_counts(
    call_count,
    put_count
):

    # 5/5 = strongest technical setup
    if call_count == 5:
        return "CALL", "5/5"

    if put_count == 5:
        return "PUT", "5/5"

    # 4/5 = allowed, but must pass AI + S/R
    if call_count == 4:
        return "CALL", "4/5"

    if put_count == 4:
        return "PUT", "4/5"

    # 3/5 or lower = WAIT
    return "WAIT", "0-3/5"


# =========================================================
# GEMINI AI ANALYSIS
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

        return "WAIT"

    if genai is None:

        print(
            "AI ERROR: google-genai package missing",
            flush=True
        )

        return "WAIT"

    try:

        # Only send recent candles to AI.
        recent = df.tail(20)[
            ["open", "high", "low", "close"]
        ].copy()

        recent_rows = []

        for _, row in recent.iterrows():

            recent_rows.append({
                "open": round(float(row["open"]), 8),
                "high": round(float(row["high"]), 8),
                "low": round(float(row["low"]), 8),
                "close": round(float(row["close"]), 8),
            })

        prompt = f"""
You are a conservative market-analysis confirmation engine.

You are NOT placing trades.
You must analyze the supplied technical market data only.

Asset: {asset}
Timeframe: {timeframe_name(timeframe)}
Expiry: {expiry_name(expiry)}

Technical direction:
{("CALL" if call_count > put_count else "PUT" if put_count > call_count else "WAIT")}

Technical confirmations:
CALL = {call_count}/5
PUT = {put_count}/5

MA trend:
{trend_signal}

RSI direction:
{rsi_signal}

Current candle:
{current_signal}

Previous candle:
{previous_signal}

Higher timeframe:
{higher_signal}

Current price:
{price}

Support:
{support}

Resistance:
{resistance}

Recent candles:
{json.dumps(recent_rows)}

Rules:

1. Return BUY only if the market evidence supports upward direction.
2. Return SELL only if the market evidence supports downward direction.
3. Return WAIT if the evidence is mixed, weak, near an important level,
   or there is not enough confidence.
4. Do not invent information.
5. Do not give explanations.
6. Your entire response MUST be exactly one word:
BUY
SELL
or
WAIT
"""

        def call_ai():

            client = genai.Client(
                api_key=GEMINI_API_KEY
            )

            response = client.models.generate_content(
                model=AI_MODEL,
                contents=prompt
            )

            return response.text if response else ""

        text = await asyncio.to_thread(
            call_ai
        )

        if not text:

            return "WAIT"

        answer = text.strip().upper()

        # Clean accidental markdown / punctuation
        answer = re.sub(
            r"[^A-Z]",
            "",
            answer
        )

        if answer == "BUY":

            return "BUY"

        if answer == "SELL":

            return "SELL"

        return "WAIT"

    except Exception as e:

        print(
            "GEMINI AI ERROR:",
            repr(e),
            flush=True
        )

        return "WAIT"


# =========================================================
# SIGNAL ANALYSIS
# =========================================================

async def analyze_signal(
    asset,
    timeframe,
    expiry
):

    df = await get_candles(
        asset,
        timeframe,
        CANDLE_COUNT
    )

    if df is None:

        return {
            "error": "DATA LAMA HELIN"
        }

    if len(df) < 60:

        return {
            "error": "DATA LAMA HELIN"
        }

    df = df.copy()

    # -----------------------------------------------------
    # INDICATORS
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

    df["RSI"] = calculate_rsi(
        df["close"]
    )

    latest = df.iloc[-1]

    previous = df.iloc[-2]

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

    # -----------------------------------------------------
    # SUPPORT / RESISTANCE
    # -----------------------------------------------------

    support, resistance = (
        calculate_support_resistance(
            df,
            lookback=20
        )
    )

    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------

    if ma10 > ma50:

        trend_signal = "CALL"

    elif ma10 < ma50:

        trend_signal = "PUT"

    else:

        trend_signal = "WAIT"

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    if rsi >= 50:

        rsi_signal = "CALL"

    else:

        rsi_signal = "PUT"

    # -----------------------------------------------------
    # CURRENT CANDLE
    # -----------------------------------------------------

    if latest["close"] > latest["open"]:

        current_signal = "CALL"

    elif latest["close"] < latest["open"]:

        current_signal = "PUT"

    else:

        current_signal = "WAIT"

    # -----------------------------------------------------
    # PREVIOUS CANDLE
    # -----------------------------------------------------

    if previous["close"] > previous["open"]:

        previous_signal = "CALL"

    elif previous["close"] < previous["open"]:

        previous_signal = "PUT"

    else:

        previous_signal = "WAIT"

    # -----------------------------------------------------
    # HIGHER TIMEFRAME
    # -----------------------------------------------------

    higher_tf = higher_timeframe_for(
        timeframe
    )

    higher_df = await get_candles(
        asset,
        higher_tf,
        CANDLE_COUNT
    )

    if (
        higher_df is not None
        and len(higher_df) >= 2
    ):

        higher_latest = (
            higher_df.iloc[-1]
        )

        if (
            higher_latest["close"]
            >
            higher_latest["open"]
        ):

            higher_signal = "CALL"

        elif (
            higher_latest["close"]
            <
            higher_latest["open"]
        ):

            higher_signal = "PUT"

        else:

            higher_signal = "WAIT"

    else:

        higher_signal = "WAIT"

    # -----------------------------------------------------
    # COUNT 5 CONFIRMATIONS
    # -----------------------------------------------------

    signals = [

        trend_signal,

        rsi_signal,

        current_signal,

        previous_signal,

        higher_signal,
    ]

    call_count = signals.count(
        "CALL"
    )

    put_count = signals.count(
        "PUT"
    )

    # -----------------------------------------------------
    # 5/5 OR 4/5
    # -----------------------------------------------------

    raw_signal, confirmation_level = (
        technical_signal_from_counts(
            call_count,
            put_count
        )
    )

    # -----------------------------------------------------
    # S/R FILTER
    # -----------------------------------------------------

    sr_filter_pass = False

    if raw_signal in (
        "CALL",
        "PUT"
    ):

        sr_filter_pass = (
            support_resistance_filter(
                price,
                support,
                resistance,
                raw_signal
            )
        )

    # -----------------------------------------------------
    # AI
    # -----------------------------------------------------

    ai_signal = "WAIT"

    if raw_signal in (
        "CALL",
        "PUT"
    ):

        ai_signal = await ask_gemini(
            asset=asset,
            timeframe=timeframe,
            expiry=expiry,
            df=df,
            higher_signal=higher_signal,
            trend_signal=trend_signal,
            rsi_signal=rsi_signal,
            current_signal=current_signal,
            previous_signal=previous_signal,
            call_count=call_count,
            put_count=put_count,
            support=support,
            resistance=resistance,
            price=price
        )

    # -----------------------------------------------------
    # FINAL DECISION
    # -----------------------------------------------------
    #
    # 5/5:
    # technical + S/R + AI must agree.
    #
    # 4/5:
    # technical + S/R + AI must agree.
    #
    # 3/5 or lower:
    # WAIT.
    #
    # -----------------------------------------------------

    final_signal = "WAIT"

    if raw_signal == "CALL":

        if (
            sr_filter_pass
            and ai_signal == "BUY"
        ):

            final_signal = "CALL"

    elif raw_signal == "PUT":

        if (
            sr_filter_pass
            and ai_signal == "SELL"
        ):

            final_signal = "PUT"

    # -----------------------------------------------------
    # EMOJI
    # -----------------------------------------------------

    if final_signal == "CALL":

        final_emoji = "🟢"

    elif final_signal == "PUT":

        final_emoji = "🔴"

    else:

        final_emoji = "⚪"

    return {

        "final_signal":
            final_signal,

        "raw_signal":
            raw_signal,

        "confirmation_level":
            confirmation_level,

        "final_emoji":
            final_emoji,

        "ai_signal":
            ai_signal,

        "trend":
            trend_signal,

        "rsi_signal":
            rsi_signal,

        "current_candle":
            current_signal,

        "previous_candle":
            previous_signal,

        "higher_signal":
            higher_signal,

        "call_count":
            call_count,

        "put_count":
            put_count,

        "price":
            price,

        "ma10":
            ma10,

        "ma50":
            ma50,

        "rsi":
            rsi,

        "support":
            support,

        "resistance":
            resistance,

        "sr_filter_pass":
            sr_filter_pass,

        "higher_tf":
            higher_tf,

        "timeframe":
            timeframe,

        "expiry":
            expiry,
    }


# =========================================================
# SIGNAL COMMAND
# =========================================================

async def signal_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    settings = get_settings(
        update.effective_user.id
    )

    asset = settings["asset"]

    timeframe = settings["timeframe"]

    expiry = settings["expiry"]

    message = await update.message.reply_text(

        "⏳ NAASIRFX AI\n\n"

        "Market-ka ayaa la falanqeynayaa...\n\n"

        f"💱 {asset}\n"

        f"⏱ {timeframe_name(timeframe)}\n"

        f"⌛ {expiry_name(expiry)}"
    )

    result = await analyze_signal(
        asset,
        timeframe,
        expiry
    )

    if "error" in result:

        await message.edit_text(

            "⚪ WAIT\n\n"

            f"💱 {asset}\n\n"

            "Candles ku filan lama helin.\n"
            "Signal been ah lama sameynayo."
        )

        return

    final_signal = result[
        "final_signal"
    ]

    # -----------------------------------------------------
    # SIMPLE USER OUTPUT
    # -----------------------------------------------------

    if final_signal == "CALL":

        await message.edit_text(

            f"💱 {asset}\n\n"

            "🤖 NAASIRFX AI\n\n"

            "🟢 BUY\n\n"

            f"⏱ Timeframe: "
            f"{timeframe_name(timeframe)}\n"

            f"⌛ Expiry: "
            f"{expiry_name(expiry)}"
        )

    elif final_signal == "PUT":

        await message.edit_text(

            f"💱 {asset}\n\n"

            "🤖 NAASIRFX AI\n\n"

            "🔴 SELL\n\n"

            f"⏱ Timeframe: "
            f"{timeframe_name(timeframe)}\n"

            f"⌛ Expiry: "
            f"{expiry_name(expiry)}"
        )

    else:

        await message.edit_text(

            f"💱 {asset}\n\n"

            "🤖 NAASIRFX AI\n\n"

            "⚪ WAIT\n\n"

            "Suuqa hadda signal cad ma siinayo.\n\n"

            f"⏱ Timeframe: "
            f"{timeframe_name(timeframe)}\n"

            f"⌛ Expiry: "
            f"{expiry_name(expiry)}"
        )


# =========================================================
# TEXT MESSAGE HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        update.message.text
        if update.message
        else ""
    )

    if text == "📋 PAIRS":

        await pairs_menu(
            update,
            context
        )

        return

    if text == "⏱ TIMEFRAME":

        await timeframe_menu(
            update,
            context
        )

        return

    if text == "⌛ EXPIRY":

        await expiry_menu(
            update,
            context
        )

        return

    if text == "📊 SIGNAL":

        await signal_command(
            update,
            context
        )

        return

    if text == "ℹ️ STATUS":

        await status_command(
            update,
            context
        )

        return


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "========================================",
        flush=True
    )

    print(
        "NAASIRFX BOT STARTING...",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    if TOKEN:

        print(
            "TELEGRAM TOKEN FOUND",
            flush=True
        )

    else:

        print(
            "❌ TELEGRAM_BOT_TOKEN MISSING",
            flush=True
        )

    if POCKET_SSID:

        print(
            "POCKET OPTION SSID FOUND",
            flush=True
        )

    else:

        print(
            "❌ POCKET_OPTION_SSID MISSING",
            flush=True
        )

    if GEMINI_API_KEY:

        print(
            "GEMINI API KEY FOUND",
            flush=True
        )

    else:

        print(
            "⚠️ GEMINI_API_KEY MISSING",
            flush=True
        )

    if genai:

        print(
            "GEMINI SDK READY",
            flush=True
        )

    else:

        print(
            "⚠️ google-genai SDK NOT FOUND",
            flush=True
        )

    try:

        print(
            "CNY ASSET CHECK:",
            {
                asset: (
                    asset in ASSETS
                    if isinstance(
                        ASSETS,
                        dict
                    )
                    else False
                )
                for asset in CNY_OTC_ASSETS
            },
            flush=True
        )

    except Exception:
        pass
       # -----------------------------------------------------
    # RENDER HEALTH SERVER
    # -----------------------------------------------------

    web_thread = Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    # -----------------------------------------------------
    # TELEGRAM
    # -----------------------------------------------------

    if not TOKEN:

        print(
            "❌ Telegram token lama helin.",
            flush=True
        )

        return

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
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_handler
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    print(
        "NAASIRFX BOT IS RUNNING",
        flush=True
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()             
