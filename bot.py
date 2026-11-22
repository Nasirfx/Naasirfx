
import os
import asyncio
import logging
import time
from datetime import datetime, timezone

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


# ==========================================================
# NASIRFX AI SIGNAL - SIGNAL ONLY
# ==========================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
POCKETOPTION_SSID = os.getenv("POCKETOPTION_SSID", "").strip()
IS_DEMO = os.getenv("POCKETOPTION_DEMO", "true").lower() == "true"

MIN_CANDLES = 55
CANDLE_COUNT = 120
MIN_CONFIRMATION = 7
REQUEST_COOLDOWN = 10

TIMEFRAMES = {
    "S15": 15,
    "S30": 30,
    "M1": 60,
    "M2": 120,
    "M3": 180,
    "M5": 300,
}

EXPIRIES = ["15s", "30s", "1m", "2m", "3m", "5m"]

MARKETS = {
    "📈 FOREX": [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
        "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    ],
    "🌐 FOREX OTC": [
        "EURUSD_otc", "GBPUSD_otc", "AUDCAD_otc",
        "NZDUSD_otc", "USDJPY_otc", "EURGBP_otc",
        "GBPJPY_otc", "AUDUSD_otc",
    ],
    "🍎 STOCKS": ["AAPL", "TSLA", "MSFT", "AMZN"],
    "🍎 STOCKS OTC": ["AAPL_otc", "TSLA_otc"],
    "🪙 CRYPTO": ["BTCUSD", "ETHUSD"],
    "📊 INDICES": ["US30", "NAS100"],
    "🛢️ COMMODITIES": ["XAUUSD", "XAGUSD"],
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("NASIRFX")


# ==========================================================
# TELEGRAM MENUS
# ==========================================================

def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["📈 FOREX", "🌐 FOREX OTC"],
            ["🍎 STOCKS", "🍎 STOCKS OTC"],
            ["🪙 CRYPTO", "📊 INDICES"],
            ["🛢️ COMMODITIES"],
            ["⏱️ TIMEFRAME", "⌛ EXPIRY"],
            ["📊 GET SIGNAL", "⚙️ SETTINGS"],
        ],
        resize_keyboard=True,
    )


def pair_menu(market):
    pairs = MARKETS[market]
    rows = [pairs[i:i + 2] for i in range(0, len(pairs), 2)]
    rows.append(["⬅️ MAIN MENU"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def timeframe_menu():
    return ReplyKeyboardMarkup(
        [
            ["S15", "S30"],
            ["M1", "M2", "M3", "M5"],
            ["⬅️ MAIN MENU"],
        ],
        resize_keyboard=True,
    )


def expiry_menu():
    return ReplyKeyboardMarkup(
        [
            ["15s", "30s", "1m"],
            ["2m", "3m", "5m"],
            ["⬅️ MAIN MENU"],
        ],
        resize_keyboard=True,
    )


# ==========================================================
# CANDLE CONVERSION AND INDICATORS
# ==========================================================

def candle_timestamp(value):
    """Convert candle timestamp to Unix seconds."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    number = float(value)

    # Millisecond timestamps
    if number > 100_000_000_000:
        number /= 1000

    return number


def candles_to_dataframe(candles):
    rows = []

    for candle in candles:
        rows.append({
            "timestamp": candle_timestamp(candle.timestamp),
            "open": float(candle.open),
            "high": float(candle.high),
            "low": float(candle.low),
            "close": float(candle.close),
            "volume": float(getattr(candle, "volume", 0) or 0),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    return df.sort_values("timestamp").drop_duplicates(
        subset=["timestamp"], keep="last"
    ).reset_index(drop=True)


def closed_candles_only(df, timeframe_seconds):
    """
    Exclude the candle that is still forming.
    Only candles whose closing time has passed are analyzed.
    """
    if df.empty:
        return df

    now = time.time()

    return df[
        (df["timestamp"] + timeframe_seconds) <= now
    ].copy().reset_index(drop=True)


def add_indicators(df):
    df = df.copy()

    df["ema9"] = df["close"].ewm(
        span=9, adjust=False
    ).mean()

    df["ema21"] = df["close"].ewm(
        span=21, adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD 12, 26, 9
    ema12 = df["close"].ewm(
        span=12, adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26, adjust=False
    ).mean()

    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(
        span=9, adjust=False
    ).mean()

    df["macd_hist"] = df["macd"] - df["macd_signal"]

    return df.dropna().reset_index(drop=True)


# ==========================================================
# ULTRA CONFIRMATION ENGINE
# ==========================================================

def analyze_market(df):
    if len(df) < MIN_CANDLES:
        return {
            "signal": "WAIT",
            "score": 0,
            "reason": (
                f"Waxaa loo baahan yahay ugu yaraan "
                f"{MIN_CANDLES} candles xiran."
            ),
        }

    df = add_indicators(df)

    if len(df) < 3:
        return {
            "signal": "WAIT",
            "score": 0,
            "reason": "Indicators-ku wali ma diyaarsana.",
        }

    last = df.iloc[-1]
    previous = df.iloc[-2]

    higher_checks = [
        last["ema9"] > last["ema21"],
        last["ema21"] > last["ema50"],
        last["close"] > last["ema9"],
        last["close"] > last["ema21"],
        last["rsi"] > 50 and last["rsi"] < 70,
        last["macd"] > last["macd_signal"],
        last["macd_hist"] > 0,
        last["close"] > last["open"],
    ]

    lower_checks = [
        last["ema9"] < last["ema21"],
        last["ema21"] < last["ema50"],
        last["close"] < last["ema9"],
        last["close"] < last["ema21"],
        last["rsi"] < 50 and last["rsi"] > 30,
        last["macd"] < last["macd_signal"],
        last["macd_hist"] < 0,
        last["close"] < last["open"],
    ]

    higher_score = sum(higher_checks)
    lower_score = sum(lower_checks)

    if higher_score >= MIN_CONFIRMATION and higher_score > lower_score:
        signal = "HIGHER"
        score = higher_score
    elif lower_score >= MIN_CONFIRMATION and lower_score > higher_score:
        signal = "LOWER"
        score = lower_score
    else:
        signal = "WAIT"
        score = max(higher_score, lower_score)

    return {
        "signal": signal,
        "score": score,
        "higher_score": higher_score,
        "lower_score": lower_score,
        "price": float(last["close"]),
        "rsi": float(last["rsi"]),
        "ema9": float(last["ema9"]),
        "ema21": float(last["ema21"]),
        "ema50": float(last["ema50"]),
        "macd": float(last["macd"]),
        "macd_signal": float(last["macd_signal"]),
        "candle_time": float(last["timestamp"]),
    }


# ==========================================================
# SIGNAL REQUEST
# ==========================================================

async def get_signal(client, asset, timeframe_name):
    timeframe_seconds = TIMEFRAMES[timeframe_name]

    candles = await client.get_candles(
        asset=asset,
        timeframe=timeframe_seconds,
        count=CANDLE_COUNT,
    )

    if not candles:
        return None, "Pocket Option wax candle ah ma soo celin."

    df = candles_to_dataframe(candles)
    df = closed_candles_only(df, timeframe_seconds)

    if len(df) < MIN_CANDLES:
        return None, (
            f"Candles xiran oo ku filan lama helin. "
            f"Hadda: {len(df)} / {MIN_CANDLES}."
        )

    result = analyze_market(df)

    if result["signal"] == "WAIT":
        return result, None

    return result, None


# ==========================================================
# TELEGRAM COMMANDS
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("asset", "EURUSD_otc")
    context.user_data.setdefault("timeframe", "M1")
    context.user_data.setdefault("expiry", "2m")
    context.user_data.setdefault("last_request", 0)

    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "       NASIRFX AI SIGNAL\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ LIVE market analysis\n"
        "✅ Closed candle analysis\n"
        "✅ EMA 9 / 21 / 50\n"
        "✅ RSI 14\n"
        "✅ MACD 12 / 26 / 9\n"
        "✅ Ultra Confirmation\n\n"
        "🚫 Auto-trading: OFF\n"
        "🚫 Backtesting: OFF\n"
        "📡 Signal-only system\n\n"
        "Dooro market-ka:",
        reply_markup=main_menu(),
    )


async def send_settings(update, context):
    await update.message.reply_text(
        "⚙️ NASIRFX SETTINGS\n\n"
        f"Asset: {context.user_data.get('asset', 'EURUSD_otc')}\n"
        f"Timeframe: {context.user_data.get('timeframe', 'M1')}\n"
        f"Expiry: {context.user_data.get('expiry', '2m')}\n\n"
        "Auto-trading: OFF\n"
        "Backtesting: OFF",
        reply_markup=main_menu(),
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    msg = update.message.text.strip()

    if msg == "⬅️ MAIN MENU":
        await update.message.reply_text(
            "Dooro market-ka:",
            reply_markup=main_menu(),
        )
        return

    if msg in MARKETS:
        context.user_data["market"] = msg
        await update.message.reply_text(
            f"{msg}\nDooro asset-ka:",
            reply_markup=pair_menu(msg),
        )
        return

    all_pairs = [
        pair for pairs in MARKETS.values() for pair in pairs
    ]

    if msg in all_pairs:
        context.user_data["asset"] = msg
        await update.message.reply_text(
            f"Asset la doortay: {msg}\nDooro timeframe:",
            reply_markup=timeframe_menu(),
        )
        return

    if msg == "⏱️ TIMEFRAME":
        await update.message.reply_text(
            "Dooro timeframe:",
            reply_markup=timeframe_menu(),
        )
        return

    if msg in TIMEFRAMES:
        context.user_data["timeframe"] = msg
        await update.message.reply_text(
            f"Timeframe: {msg}\nDooro expiry:",
            reply_markup=expiry_menu(),
        )
        return

    if msg == "⌛ EXPIRY":
        await update.message.reply_text(
            "Dooro expiry:",
            reply_markup=expiry_menu(),
        )
        return

    if msg in EXPIRIES:
        context.user_data["expiry"] = msg
        await update.message.reply_text(
            f"✅ Settings waa la keydiyey.\n"
            f"Expiry: {msg}",
            reply_markup=main_menu(),
        )
        return

    if msg == "⚙️ SETTINGS":
        await send_settings(update, context)
        return

    if msg == "📊 GET SIGNAL":
        now = time.time()
        previous = context.user_data.get("last_request", 0)

        if now - previous < REQUEST_COOLDOWN:
            await update.message.reply_text(
                "⏳ Fadlan sug dhowr ilbiriqsi ka hor codsi kale."
            )
            return

        context.user_data["last_request"] = now

        client = context.application.bot_data.get("pocket_client")

        if client is None:
            await update.message.reply_text(
                "⚠️ Pocket Option connection ma jiro."
            )
            return

        asset = context.user_data.get("asset", "EURUSD_otc")
        timeframe = context.user_data.get("timeframe", "M1")
        expiry = context.user_data.get("expiry", "2m")

        status = await update.message.reply_text(
            "⏳ NASIRFX wuxuu hubinayaa LIVE candles...\n"
            "Fadlan sug."
        )

        try:
            result, error = await get_signal(
                client, asset, timeframe
            )

            if error:
                await status.edit_text(
                    "⚠️ CANDLE DATA UNAVAILABLE\n\n"
                    f"{error}\n\n"
                    "Signal lama samayn. Sug xog sax ah."
                )
                return

            signal = result["signal"]

            if signal == "HIGHER":
                direction = "🟢 HIGHER"
            elif signal == "LOWER":
                direction = "🔴 LOWER"
            else:
                direction = "⏳ WAIT"

            score = result["score"]
            confirmation = round(score / 8 * 100)

            message = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "       NASIRFX AI SIGNAL\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 Asset: {asset}\n"
                f"📊 Timeframe: {timeframe}\n"
                f"⌛ Expiry: {expiry}\n\n"
                f"🎯 SIGNAL: {direction}\n"
                f"💰 Analysis price: {result['price']}\n"
                f"📈 RSI: {result['rsi']:.2f}\n"
                f"📊 EMA 9: {result['ema9']:.6f}\n"
                f"📊 EMA 21: {result['ema21']:.6f}\n"
                f"📊 EMA 50: {result['ema50']:.6f}\n"
                f"📉 MACD: {result['macd']:.6f}\n"
                f"🧠 Confirmation: {score}/8 ({confirmation}%)\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "       ULTRA CONFIRMATION\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🟢 HIGHER checks: {result['higher_score']}/8\n"
                f"🔴 LOWER checks: {result['lower_score']}/8\n\n"
                "🚫 Auto-trading: OFF\n"
                "🚫 Backtesting: OFF\n"
                "📡 Signal-only\n\n"
                "⚠️ Signals are analysis, not guaranteed outcomes."
            )

            await status.edit_text(message)

        except Exception as exc:
            log.exception("Signal request failed")
            await status.edit_text(
                "⚠️ LIVE DATA ERROR\n\n"
                f"{type(exc).__name__}: {str(exc)[:500]}\n\n"
                "Signal lama soo saarin."
            )
        return

    await update.message.reply_text(
        "Fadlan isticmaal menu-ga hoose.",
        reply_markup=main_menu(),
    )


# ==========================================================
# APPLICATION STARTUP
# ==========================================================

async def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable waa maqan.")

    if not POCKETOPTION_SSID:
        raise RuntimeError("POCKETOPTION_SSID environment variable waa maqan.")

    client = AsyncPocketOptionClient(
        POCKETOPTION_SSID,
        is_demo=IS_DEMO,
        enable_logging=True,
    )

    log.info("Connecting to Pocket Option...")
    connected = await client.connect()

    if not connected:
        raise RuntimeError("Pocket Option connection waa fashilantay.")

    log.info("Pocket Option connected.")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.bot_data["pocket_client"] = client

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    log.info("NASIRFX AI SIGNAL is running.")

    try:
        await asyncio.Event().wait()
    finally:
        log.info("Stopping NASIRFX...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        log.info("Bot stopped.")
    except Exception:
        log.exception("NASIRFX startup failed.")
        raise
