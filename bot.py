import os
import asyncio
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pandas as pd
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
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


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("NaasirFx")


# =========================================================
# RENDER KEEP-ALIVE
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"NaasirFx is running")

    def log_message(self, format, *args):
        return


def start_web_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info("Health server started on port %s", port)
    server.serve_forever()


# =========================================================
# POCKET OPTION CONNECTION
# =========================================================

async def connect_pocket_option():

    if not POCKET_SSID:
        raise RuntimeError(
            "POCKET_OPTION_SSID environment variable is missing."
        )

    last_error = None

    for attempt in range(1, 4):

        try:
            logger.info(
                "Pocket Option connection attempt %s/3",
                attempt,
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

            logger.info("Pocket Option connected successfully.")

            return client

        except Exception as exc:

            last_error = exc

            logger.error(
                "Connection attempt %s failed: %s",
                attempt,
                exc,
            )

            if attempt < 3:
                await asyncio.sleep(5)

    raise RuntimeError(
        f"Pocket Option connection failed after 3 attempts. "
        f"Last error: {last_error}"
    )


# =========================================================
# GET CANDLES
# =========================================================

async def get_market_data(
    asset=DEFAULT_ASSET,
    timeframe=DEFAULT_TIMEFRAME,
    count=100,
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
# DATAFRAME
# =========================================================

def candles_to_dataframe(candles):
    if not candles:
        return pd.DataFrame()

    rows = []

    for candle in candles:
        rows.append({
            "open": float(candle.open),
            "high": float(candle.high),
            "low": float(candle.low),
            "close": float(candle.close),
        })

    df = pd.DataFrame(rows)

    return df


# =========================================================
# RSI
# =========================================================

def calculate_rsi(
    series,
    period=14,
):

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

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# =========================================================
# SIGNAL ANALYSIS
# =========================================================

def analyze_market(df):

    if len(df) < 50:

        return {
            "signal": "WAIT",
            "reason": "Not enough candles",
            "trend": "WAIT",
            "rsi": None,
            "confirmation": "WAIT",
        }

    df = df.copy()

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
        df["close"],
        14,
    )

    last = df.iloc[-1]

    trend = "WAIT"

    if last["MA10"] > last["MA50"]:
        trend = "CALL"

    elif last["MA10"] < last["MA50"]:
        trend = "PUT"

    rsi_value = last["RSI"]

    momentum = "WAIT"

    if pd.notna(rsi_value):

        if rsi_value >= 55:
            momentum = "CALL"

        elif rsi_value <= 45:
            momentum = "PUT"

    candle = "WAIT"

    if last["close"] > last["open"]:
        candle = "CALL"

    elif last["close"] < last["open"]:
        candle = "PUT"

    signal = "WAIT"

    if (
        trend == "CALL"
        and momentum == "CALL"
        and candle == "CALL"
    ):
        signal = "CALL"

    elif (
        trend == "PUT"
        and momentum == "PUT"
        and candle == "PUT"
    ):
        signal = "PUT"

    return {
        "signal": signal,
        "trend": trend,
        "rsi": rsi_value,
        "momentum": momentum,
        "confirmation": candle,
    }


# =========================================================
# TELEGRAM /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "🤖 NAASIRFX\n\n"
        "Ku soo dhawoow NaasirFx.\n\n"
        "📊 /signal - EURUSD OTC\n"
        "ℹ️ /status - Bot status"
    )


# =========================================================
# TELEGRAM /status
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

    await update.message.reply_text(
        "🤖 NAASIRFX STATUS\n\n"
        f"Telegram Token: {token_status}\n"
        f"Pocket Option SSID: {ssid_status}"
    )


# =========================================================
# TELEGRAM /signal
# =========================================================

async def signal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "⏳ NaasirFx ayaa market data soo qaadanaya..."
    )

    try:

        candles = await get_market_data(
            DEFAULT_ASSET,
            DEFAULT_TIMEFRAME,
            100,
        )

        df = candles_to_dataframe(
            candles
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

        if rsi is None:
            rsi_text = "N/A"
        else:
            rsi_text = f"{rsi:.2f}"

        message = (
            "📊 NAASIRFX SIGNAL\n\n"
            f"💱 Asset: {DEFAULT_ASSET}\n"
            "⏱ Timeframe: 1 Minute\n\n"
            f"🎯 FINAL SIGNAL: {signal_text}\n\n"
            "🔎 CONFIRMATION CHECK\n"
            f"📈 MA10 + MA50: {result['trend']}\n"
            f"📊 RSI: {rsi_text}\n"
            f"🕯 Candle: {result['confirmation']}\n"
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
            f"Asset: {DEFAULT_ASSET}\n"
            "Timeframe: 1 Minute\n\n"
            f"Error: {type(exc).__name__}: {exc}"
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
        daemon=True,
    ).start()

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

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
            signal,
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
