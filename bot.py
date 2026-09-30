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
# API CODE -> TELEGRAM DISPLAY NAME
#
# API code lama ma beddelmayo.
# Telegram-ka waxaa lagu tusayaa magaca company-ga.
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
# API CODE -> TELEGRAM DISPLAY NAME
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

        # Marka hore company names-ka aan rabno
        # kaliya haddii API catalog-ku leeyahay code-ka.
        for code, name in STOCK_NAMES.items():

            if code in available_assets:

                stocks[name] = code

        # Haddii ASSETS leeyahay stock kale oo aan
        # mapping-ka kore ku jirin, ha lumin.
        # Waxaa loo tusi doonaa ticker-ka API-ga.
        for asset in sorted(available_assets):

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

        # Company names-ka OTC
        # kaliya haddii API catalog-ku leeyahay code-ka.
        for code, name in STOCK_OTC_NAMES.items():

            if code in available_assets:

                stocks_otc[name] = code

        # Stock OTC kale oo catalog-ka ku jira
        # laakiin aan mapping-ka kore ku jirin.
        for asset in sorted(available_assets):

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

        "STOCKS_OTC": get_stock_otc_assets(),
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

        f"💱 Pair: {settings['asset']}\n"
        f"⏱ Timeframe: "
        f"{timeframe_name(settings['timeframe'])}\n"
        f"⌛ Expiry: "
        f"{expiry_name(settings['expiry'])}\n\n"

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
        ]
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
        ]
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

    if data.startswith("CATEGORY|"):

        category = data.split(
            "|",
            1
        )[1]

        all_pairs = get_all_pairs()

        if category == "FOREX":

            title = "💱 FOREX"

            assets = all_pairs[
                "FOREX"
            ]

        elif category == "FOREX_OTC":

            title = "💱 FOREX OTC"

            assets = all_pairs[
                "FOREX_OTC"
            ]

        elif category == "STOCKS":

            title = "📈 STOCKS"

            assets = all_pairs[
                "STOCKS"
            ]

        elif category == "STOCKS_OTC":

            title = "📈 STOCKS OTC"

            assets = all_pairs[
                "STOCKS_OTC"
            ]

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

        current = settings[
            "asset"
        ]

        for name, code in assets.items():

            if code == current:

                button_text = (
                    f"✅ {name}"
                )

            else:

                button_text = name

            row.append(

                InlineKeyboardButton(
                    button_text,
                    callback_data=(
                        f"PAIR|{code}"
                    )
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
            ]
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

    if data.startswith("PAIR|"):

        asset = data.split(
            "|",
            1
        )[1]

        all_pairs = get_all_pairs()

        valid_assets = []

        for category_assets in (
            all_pairs.values()
        ):

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

    if data.startswith("TF|"):

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

    if data.startswith("EXP|"):

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
        f"{ssid_status}\n\n"

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

                if hasattr(
                    candle,
                    "open"
                ):

                    rows.append({

                        "open": float(
                            candle.open
                        ),

                        "high": float(
                            candle.high
                        ),

                        "low": float(
                            candle.low
                        ),

                        "close": float(
                            candle.close
                        ),

                    })

                elif isinstance(
                    candle,
                    dict
                ):

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

        if len(rows) < 20:
            return None

        return pd.DataFrame(
            rows
        )

    except Exception as e:

        print(
            "CANDLE ERROR:",
            e,
            flush=True
        )

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

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = (
        gain.rolling(period)
        .mean()
    )

    avg_loss = (
        loss.rolling(period)
        .mean()
    )

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

    settings = get_settings(
        user_id
    )

    asset = settings[
        "asset"
    ]

    timeframe = settings[
        "timeframe"
    ]

    expiry = settings[
        "expiry"
    ]

    await update.message.reply_text(

        "🔎 SIGNAL-KA WAA LA BAARAYAA...\n\n"

        f"💱 Pair: {asset}\n"

        f"⏱ Timeframe: "
        f"{timeframe_name(timeframe)}\n"

        f"⌛ Expiry: "
        f"{expiry_name(expiry)}"
    )

    # -----------------------------------------------------
    # MAIN TIMEFRAME
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # HIGHER TIMEFRAME
    # -----------------------------------------------------

    higher_df = await get_candles(
        asset,
        HIGHER_TIMEFRAME,
        CANDLE_COUNT
    )

    if higher_df is None or len(
        higher_df
    ) < 60:

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

    call_count = checks.count(
        "CALL"
    )

    put_count = checks.count(
        "PUT"
    )

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
        "confirmation oo keliya.\n"

        "⚠️ 95% win lama dammaanad qaadi karo."
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
            "ERROR: TELEGRAM_BOT_TOKEN is missing",
            flush=True
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

    print(
        "NaasirFx is running...",
        flush=True
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    main()
