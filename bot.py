import os, asyncio, json, re, inspect, time
from datetime import datetime, timezone
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pandas as pd
import requests

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from pocketoptionapi_async import AsyncPocketOptionClient

# Register CNY OTC symbols in the async client's local asset registry.
# Some package versions omit these OTC symbols from their static ASSETS list.
try:
    from pocketoptionapi_async.constants import ASSETS as PO_ASSETS
except Exception:
    PO_ASSETS = None


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PO_SSID = os.getenv("POCKET_OPTION_SSID") or os.getenv("PO_SSID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

IS_DEMO = True
CONNECT_TIMEOUT = 40
CANDLE_TIMEOUT = 30
CANDLE_COUNT = 100
AI_MODEL = "gemini-2.5-flash-lite"

TIMEFRAMES = {
    "1️⃣ 1 Minute": 60,
    "3️⃣ 3 Minutes": 180,
    "5️⃣ 5 Minutes": 300,
    "15️⃣ 15 Minutes": 900,
    "30️⃣ 30 Minutes": 1800,
    "60️⃣ 1 Hour": 3600,
    "4️⃣ 4 Hours": 14400,
}

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

HIGHER_TIMEFRAME = {
    60: 180,
    180: 300,
    300: 900,
    900: 1800,
    1800: 3600,
    3600: 14400,
    14400: 14400
}

HIGHER_TIMEFRAME_NAME = {
    60: "3 Minutes",
    180: "5 Minutes",
    300: "15 Minutes",
    900: "30 Minutes",
    1800: "1 Hour",
    3600: "4 Hours",
    14400: "4 Hours"
}

FOREX_PAIRS = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "USD/JPY": "USDJPY",
    "USD/CHF": "USDCHF",
    "AUD/USD": "AUDUSD",
    "NZD/USD": "NZDUSD",
    "USD/CAD": "USDCAD",
    "EUR/GBP": "EURGBP",
    "EUR/JPY": "EURJPY",
    "GBP/JPY": "GBPJPY",
    "EUR/CHF": "EURCHF",
    "AUD/JPY": "AUDJPY",
    "EUR/AUD": "EURAUD",
    "EUR/CAD": "EURCAD",
    "EUR/NZD": "EURNZD",
    "GBP/CHF": "GBPCHF",
    "GBP/CAD": "GBPCAD",
    "GBP/AUD": "GBPAUD",
    "AUD/CAD": "AUDCAD",
    "AUD/CHF": "AUDCHF",
    "AUD/NZD": "AUDNZD",
    "CAD/JPY": "CADJPY",
    "CAD/CHF": "CADCHF",
    "CHF/JPY": "CHFJPY"
}

FOREX_OTC_PAIRS = {
    "EUR/USD OTC": "EURUSD_otc",
    "GBP/USD OTC": "GBPUSD_otc",
    "USD/JPY OTC": "USDJPY_otc",
    "USD/CHF OTC": "USDCHF_otc",
    "AUD/USD OTC": "AUDUSD_otc",
    "NZD/USD OTC": "NZDUSD_otc",
    "USD/CAD OTC": "USDCAD_otc",
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
    "NZD/JPY OTC": "NZDJPY_otc",
    "USD/RUB OTC": "USDRUB_otc",
    "USD/CNH OTC": "USDCNH_otc",
    "USD/INR OTC": "USDINR_otc",
    "USD/PHP OTC": "USDPHP_otc",
    "USD/DZD OTC": "USDDZD_otc",
    "USD/BDT OTC": "USDBDT_otc",
    "USD/EGP OTC": "USDEGP_otc",
    "USD/CLP OTC": "USDCLP_otc",
    "USD/PKR OTC": "USDPKR_otc",
    "USD/COP OTC": "USDCOP_otc",
    "USD/ARS OTC": "USDARS_otc",
    "USD/MYR OTC": "USDMYR_otc",
    "USD/BRL OTC": "USDBRL_otc",
    "USD/IDR OTC": "USDIDR_otc",
    "USD/MXN OTC": "USDMXN_otc",
    "USD/THB OTC": "USDTHB_otc",
    "USD/VND OTC": "USDVND_otc",
    "USD/SGD OTC": "USDSGD_otc",
    "KES/USD OTC": "KESUSD_otc",
    "NGN/USD OTC": "NGNUSD_otc",
    "ZAR/USD OTC": "ZARUSD_otc",
    "UAH/USD OTC": "UAHUSD_otc",
    "YER/USD OTC": "YERUSD_otc",
    "LBP/USD OTC": "LBPUSD_otc",
    "MAD/USD OTC": "MADUSD_otc",
    "TND/USD OTC": "TNDUSD_otc",
    "AED/CNY OTC": "AEDCNY_otc",
    "BHD/CNY OTC": "BHDCNY_otc",
    "JOD/CNY OTC": "JODCNY_otc",
    "OMR/CNY OTC": "OMRCNY_otc",
    "QAR/CNY OTC": "QARCNY_otc",
    "SAR/CNY OTC": "SARCNY_otc",
    "SAR/USD OTC": "SARUSD_otc"
}

STOCK_NAMES = {
    "🍎 Apple": "#AAPL",
    "💳 American Express": "#AXP",
    "🍔 McDonald's": "#MCD",
    "🟢 Microsoft": "#MSFT",
    "🔵 Meta": "#META",
    "🟠 Amazon": "#AMZN",
    "🚗 Tesla": "#TSLA",
    "🟢 NVIDIA": "#NVDA",
    "🔴 Coca-Cola": "#KO",
    "💳 Mastercard": "#MA",
    "💳 Visa": "#V",
    "🔵 Google": "#GOOGL",
    "🔵 Google (GOOG)": "#GOOG",
    "🎬 Netflix": "#NFLX",
    "🔴 AMD": "#AMD",
    "🔵 Intel": "#INTC",
    "🔵 IBM": "#IBM",
    "🔴 Oracle": "#ORCL",
    "☁️ Salesforce": "#CRM",
    "🏰 Disney": "#DIS",
    "👟 Nike": "#NKE",
    "🥤 PepsiCo": "#PEP",
    "🛒 Walmart": "#WMT",
    "🏦 JPMorgan Chase": "#JPM",
    "🏦 Bank of America": "#BAC",
    "🏦 Citigroup": "#C",
    "🏦 Goldman Sachs": "#GS",
    "⛽ Exxon Mobil": "#XOM",
    "⛽ Chevron": "#CVX",
    "✈️ Boeing": "#BA",
    "💊 Pfizer": "#PFE",
    "💊 Johnson & Johnson": "#JNJ",
    "🌐 Cisco": "#CSCO",
    "🎨 Adobe": "#ADBE",
    "📱 Qualcomm": "#QCOM",
    "🚕 Uber": "#UBER",
    "💳 PayPal": "#PYPL",
    "🛍 Shopify": "#SHOP",
    "🛒 Alibaba": "#BABA",
    "📡 AT&T": "#T",
    "📡 Verizon": "#VZ"
}

STOCK_OTC_NAMES = {
    "🍎 Apple OTC": "#AAPL_otc",
    "💳 American Express OTC": "#AXP_otc",
    "🍔 McDonald's OTC": "#MCD_otc",
    "🟢 Microsoft OTC": "#MSFT_otc",
    "🔵 Meta OTC": "#META_otc",
    "🟠 Amazon OTC": "#AMZN_otc",
    "🚗 Tesla OTC": "#TSLA_otc",
    "🟢 NVIDIA OTC": "#NVDA_otc",
    "🔴 Coca-Cola OTC": "#KO_otc",
    "💳 Mastercard OTC": "#MA_otc",
    "💳 Visa OTC": "#V_otc",
    "🔵 Google OTC": "#GOOGL_otc",
    "🔵 Google (GOOG) OTC": "#GOOG_otc",
    "🎬 Netflix OTC": "#NFLX_otc",
    "🔴 AMD OTC": "#AMD_otc",
    "🔵 Intel OTC": "#INTC_otc",
    "🔵 IBM OTC": "#IBM_otc",
    "🔴 Oracle OTC": "#ORCL_otc",
    "☁️ Salesforce OTC": "#CRM_otc",
    "🏰 Disney OTC": "#DIS_otc",
    "👟 Nike OTC": "#NKE_otc",
    "🥤 PepsiCo OTC": "#PEP_otc",
    "🛒 Walmart OTC": "#WMT_otc",
    "🏦 JPMorgan Chase OTC": "#JPM_otc",
    "🏦 Bank of America OTC": "#BAC_otc",
    "🏦 Citigroup OTC": "#C_otc",
    "🏦 Goldman Sachs OTC": "#GS_otc",
    "⛽ Exxon Mobil OTC": "#XOM_otc",
    "⛽ Chevron OTC": "#CVX_otc",
    "✈️ Boeing OTC": "#BA_otc",
    "💊 Pfizer OTC": "#PFE_otc",
    "💊 Johnson & Johnson OTC": "#JNJ_otc",
    "🌐 Cisco OTC": "#CSCO_otc",
    "🎨 Adobe OTC": "#ADBE_otc",
    "📱 Qualcomm OTC": "#QCOM_otc",
    "🚕 Uber OTC": "#UBER_otc",
    "💳 PayPal OTC": "#PYPL_otc",
    "🛍 Shopify OTC": "#SHOP_otc",
    "🛒 Alibaba OTC": "#BABA_otc",
    "📡 AT&T OTC": "#T_otc",
    "📡 Verizon OTC": "#VZ_otc"
}

CATEGORIES = {
    "💱 Forex": FOREX_PAIRS,
    "💱 Forex OTC": FOREX_OTC_PAIRS,
    "📈 Stocks": STOCK_NAMES,
    "📈 Stocks OTC": STOCK_OTC_NAMES
}

CNY_OTC_ASSETS = {
    "AEDCNY_otc": 538,
    "BHDCNY_otc": 536,
    "JODCNY_otc": 546,
    "OMRCNY_otc": 544,
    "QARCNY_otc": 542,
    "SARCNY_otc": 540
}

LAST_SIGNAL_DATA_SOURCE = "UNKNOWN"

CNY_OTC_SYMBOLS = tuple(CNY_OTC_ASSETS.keys())


def register_otc_assets():
    """Register every Forex OTC symbol defined by the bot."""
    if PO_ASSETS is None:
        print("🟡 POCKET OPTION ASSETS registry not available.", flush=True)
        return

    symbols = set(CNY_OTC_SYMBOLS)
    try:
        symbols.update(str(v).strip() for v in FOREX_OTC_PAIRS.values())
    except Exception:
        pass

    added = []
    for symbol in sorted(s for s in symbols if s):
        if symbol not in PO_ASSETS:
            PO_ASSETS[symbol] = {"name": symbol, "symbol": symbol}
            added.append(symbol)

    print(
        f"🟢 OTC ASSETS REGISTERED: {len(symbols)} total, "
        f"{len(added)} added",
        flush=True
    )


register_otc_assets()


user_category = {}
user_timeframe = {}
user_expiry = {}


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


async def connect_client():
    if not PO_SSID:
        raise RuntimeError("POCKET_OPTION_SSID / PO_SSID lama helin.")

    client = AsyncPocketOptionClient(
        PO_SSID,
        is_demo=IS_DEMO,
        enable_logging=True
    )

    try:
        await asyncio.wait_for(
            client.connect(),
            timeout=CONNECT_TIMEOUT
        )

        print("🟢 PO CONNECT: SUCCESS", flush=True)
        return client

    except Exception:
        try:
            await client.disconnect()
        except Exception:
            pass

        raise


def get_asset_variants(asset_code):
    original = str(asset_code).strip()
    variants = []

    def add(value):
        if value and value not in variants:
            variants.append(value)

    add(original)
    add(original.replace("/", ""))

    if original.lower().endswith("_otc"):
        base = original[:-4]

        add(base + "_otc")
        add(base.upper() + "_otc")
        add(base.upper() + "-OTC")
        add(base.upper() + " OTC")
        add(base.upper() + "_OTC")

        if base.startswith("#"):
            clean = base[1:]
            add("#" + clean + "_otc")
            add(clean + "_otc")

    else:
        add(original + "_otc")
        add(original.replace("/", "") + "_otc")

    return variants


async def discover_asset_variants_by_id(client, asset_code):
    asset_id = CNY_OTC_ASSETS.get(asset_code)

    if asset_id is None:
        return []

    method = getattr(client, "get_assets", None)

    if not callable(method):
        return []

    try:
        assets = await asyncio.wait_for(
            method(),
            timeout=10
        )

    except Exception as e:
        print(
            f"🟡 ASSET DISCOVERY ERROR {asset_code}: {e}",
            flush=True
        )
        return []

    found = []

    def add(value):
        if value is None:
            return

        value = str(value).strip()

        if value and value not in found:
            found.append(value)

    def same_id(value):
        try:
            return int(value) == int(asset_id)
        except Exception:
            return str(value).strip() == str(asset_id)

    id_keys = (
        "id",
        "asset_id",
        "active_id",
        "activeId",
        "symbol_id"
    )

    name_keys = (
        "symbol",
        "asset",
        "name",
        "ticker",
        "code",
        "pair"
    )

    if isinstance(assets, dict):

        for key, value in assets.items():

            if same_id(key):

                if isinstance(value, dict):

                    for k in name_keys:
                        add(value.get(k))

                else:
                    add(value)

            if same_id(value):
                add(key)

            if isinstance(value, dict):

                ids = [
                    value.get(k)
                    for k in id_keys
                ]

                if any(same_id(v) for v in ids):

                    for k in name_keys:
                        add(value.get(k))

        candidates = list(assets.values())

    elif isinstance(assets, (list, tuple, set)):
        candidates = list(assets)

    else:
        candidates = [assets]

    for item in candidates:

        if isinstance(item, dict):

            ids = [
                item.get(k)
                for k in id_keys
            ]

            if any(same_id(v) for v in ids):

                for k in name_keys:
                    add(item.get(k))

        else:

            ids = []

            for k in id_keys:

                try:
                    ids.append(getattr(item, k, None))
                except Exception:
                    pass

            if any(same_id(v) for v in ids):

                for k in name_keys:

                    try:
                        add(getattr(item, k, None))
                    except Exception:
                        pass

    if found:
        print(
            f"🟢 ASSET DISCOVERY {asset_code}: {found}",
            flush=True
        )

    return found


def _find_time_column(df):
    candidates = [
        "timestamp",
        "time",
        "time_stamp",
        "datetime",
        "date",
        "from",
        "at"
    ]

    for column in candidates:
        if column in df.columns:
            return column

    return None


def _timestamp_to_seconds(value):
    try:

        if isinstance(value, pd.Timestamp):
            return value.timestamp()

        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)

            return value.timestamp()

        number = float(value)

        # milliseconds
        if number > 10_000_000_000:
            number = number / 1000.0

        # microseconds
        if number > 10_000_000_000_000:
            number = number / 1_000_000.0

        return number

    except Exception:
        return None


def normalize_candle_dataframe(raw):
    if raw is None:
        return None

    try:

        if isinstance(raw, pd.DataFrame):
            df = raw.copy()

        elif isinstance(raw, dict):

            # Common API shape:
            # {"timestamp": [...], "open": [...], ...}
            if all(
                isinstance(v, (list, tuple, np.ndarray))
                for v in raw.values()
            ):
                df = pd.DataFrame(raw)

            # Common API shape:
            # {"candles": [...]}
            elif isinstance(raw.get("candles"), (list, tuple)):
                df = pd.DataFrame(raw["candles"])

            elif isinstance(raw.get("data"), (list, tuple)):
                df = pd.DataFrame(raw["data"])

            else:
                df = pd.DataFrame(raw)

        else:
            df = pd.DataFrame(raw)

        if df.empty:
            return None

        df.columns = [
            str(c).strip().lower()
            for c in df.columns
        ]

        rename_map = {
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "t": "timestamp"
        }

        df = df.rename(columns=rename_map)

        required = [
            "open",
            "close"
        ]

        if not all(c in df.columns for c in required):
            return None

        for column in (
            "open",
            "high",
            "low",
            "close",
            "volume"
        ):

            if column in df.columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce"
                )

        df = df.dropna(
            subset=["open", "close"]
        )

        if df.empty:
            return None

        time_column = _find_time_column(df)

        if time_column:

            parsed = []

            for value in df[time_column]:
                parsed.append(
                    _timestamp_to_seconds(value)
                )

            df["_ts"] = parsed

            # Keep only rows where timestamp is usable.
            if df["_ts"].notna().any():
                df = df.sort_values(
                    "_ts"
                ).reset_index(drop=True)

        else:
            df = df.reset_index(drop=True)

        return df

    except Exception as e:

        print(
            "🟡 NORMALIZE CANDLE ERROR:",
            repr(e),
            flush=True
        )

        return None


def candle_is_current_or_recent(df, timeframe, tolerance_bars=1):
    """
    Verifies that the newest candle is not several candles behind.

    We do NOT reject the current candle simply because it is still open.
    An open/current candle is exactly what is needed for on-time analysis.
    """

    if df is None or df.empty:
        return False

    if "_ts" not in df.columns:
        # Some Pocket Option responses don't expose timestamps.
        # In that case we cannot prove staleness.
        return True

    timestamps = df["_ts"].dropna()

    if timestamps.empty:
        return True

    latest_ts = float(timestamps.iloc[-1])
    now_ts = time.time()

    age = now_ts - latest_ts

    max_age = (
        timeframe * (tolerance_bars + 1)
        + 15
    )

    if age > max_age:
        print(
            f"🔴 STALE CANDLES: age={age:.1f}s "
            f"timeframe={timeframe}s",
            flush=True
        )
        return False

    return True


async def call_method_flexible(method, variants, timeframe):
    """
    Tries the common Pocket Option candle method signatures.
    """

    now_utc = datetime.now(timezone.utc)

    for variant in variants:

        calls = [
            (
                (variant, timeframe, CANDLE_COUNT, now_utc),
                {}
            ),
            (
                (variant, timeframe, CANDLE_COUNT),
                {}
            ),
            (
                (),
                {
                    "asset": variant,
                    "timeframe": timeframe,
                    "count": CANDLE_COUNT,
                    "end_time": now_utc
                }
            ),
            (
                (),
                {
                    "asset": variant,
                    "timeframe": timeframe
                }
            )
        ]

        for args, kwargs in calls:

            try:

                raw = await asyncio.wait_for(
                    method(*args, **kwargs),
                    timeout=CANDLE_TIMEOUT
                )

                df = normalize_candle_dataframe(raw)

                if df is not None and len(df) >= 2:

                    print(
                        f"🟢 CANDLES OK: {variant} "
                        f"TF={timeframe}s rows={len(df)}",
                        flush=True
                    )

                    return df

            except TypeError:
                continue

            except Exception as e:

                print(
                    f"🟡 CANDLE METHOD FAIL {variant}: {e}",
                    flush=True
                )

    return None


async def try_realtime_candles(client, variants, timeframe):
    """
    If the installed Pocket Option client exposes a realtime/live
    candle method, use it before falling back to historical candles.
    """

    method_names = [
        "get_realtime_candles",
        "get_realtime_candle",
        "get_live_candles",
        "get_live_candle"
    ]

    for method_name in method_names:

        method = getattr(
            client,
            method_name,
            None
        )

        if not callable(method):
            continue

        print(
            f"🟢 REALTIME METHOD FOUND: {method_name}",
            flush=True
        )

        for variant in variants:

            calls = [
                (
                    (variant, timeframe),
                    {}
                ),
                (
                    (),
                    {
                        "asset": variant,
                        "timeframe": timeframe
                    }
                ),
                (
                    (variant,),
                    {
                        "timeframe": timeframe
                    }
                )
            ]

            for args, kwargs in calls:

                try:

                    raw = await asyncio.wait_for(
                        method(*args, **kwargs),
                        timeout=15
                    )

                    df = normalize_candle_dataframe(raw)

                    if df is not None and len(df) >= 2:

                        print(
                            f"🟢 REALTIME CANDLES OK: "
                            f"{variant} -> {len(df)}",
                            flush=True
                        )

                        return df

                except TypeError:
                    continue

                except Exception as e:

                    print(
                        f"🟡 REALTIME FAIL "
                        f"{method_name}/{variant}: {e}",
                        flush=True
                    )

    return None


async def get_candles(client, asset_code, timeframe):
    global LAST_SIGNAL_DATA_SOURCE
    LAST_SIGNAL_DATA_SOURCE = "UNKNOWN"


    variants = get_asset_variants(asset_code)

    # OTC assets: exact Pocket Option symbol first.
    is_otc = str(asset_code).strip().lower().endswith("_otc")

    if is_otc:
        exact = str(asset_code).strip()
        variants = [exact] + [v for v in variants if v != exact]

        if exact.upper().endswith("CNY_OTC"):
            try:
                discovered = await discover_cny_asset_variants(
                    client,
                    asset_code
                )
            except Exception:
                discovered = []

            for item in discovered:
                if item not in variants:
                    variants.append(item)

        print(
            f"🔎 OTC CANDLE VARIANTS [{asset_code}]: {variants}",
            flush=True
        )
    else:
        id_discovered = await discover_asset_variants_by_id(
            client,
            asset_code
        )
        for item in id_discovered:
            if item not in variants:
                variants.append(item)

    # ---------------------------------------------------------
    # 1. REALTIME/LIVE CANDLE FIRST
    # ---------------------------------------------------------
    # Prefer the live stream when the installed client exposes it.
    # If the client does not expose a usable realtime method, fall back
    # to the freshest candle endpoint instead of returning DATA LAMA HELIN.

    realtime_df = await try_realtime_candles(
        client,
        variants,
        timeframe
    )

    if realtime_df is not None:
        if candle_is_current_or_recent(
            realtime_df,
            timeframe,
            tolerance_bars=1
        ):
            LAST_SIGNAL_DATA_SOURCE = "REALTIME"
            print(
                f"🟢 SIGNAL DATA SOURCE: REALTIME {asset_code}",
                flush=True
            )
            return realtime_df

    # ---------------------------------------------------------
    # 2. RAW GET_CANDLES
    # ---------------------------------------------------------

    raw_method = getattr(
        client,
        "get_candles",
        None
    )

    if callable(raw_method):

        df = await call_method_flexible(
            raw_method,
            variants,
            timeframe
        )

        if df is not None:

            if candle_is_current_or_recent(
                df,
                timeframe,
                tolerance_bars=1
            ):
                LAST_SIGNAL_DATA_SOURCE = "FRESH GET_CANDLES"
                print(
                    f"🟢 SIGNAL DATA SOURCE: FRESH GET_CANDLES {asset_code}",
                    flush=True
                )
                return df

            print(
                "🟡 RAW candles stale; retrying...",
                flush=True
            )

    # ---------------------------------------------------------
    # 3. DATAFRAME METHOD
    # ---------------------------------------------------------

    df_method = getattr(
        client,
        "get_candles_dataframe",
        None
    )

    if callable(df_method):

        df = await call_method_flexible(
            df_method,
            variants,
            timeframe
        )

        if df is not None:

            if candle_is_current_or_recent(
                df,
                timeframe,
                tolerance_bars=1
            ):
                LAST_SIGNAL_DATA_SOURCE = "FRESH DATAFRAME"
                print(
                    f"🟢 SIGNAL DATA SOURCE: FRESH DATAFRAME {asset_code}",
                    flush=True
                )
                return df

            print(
                "🟡 DATAFRAME candles stale.",
                flush=True
            )

    # ---------------------------------------------------------
    # 4. SECOND FRESH RETRY
    # ---------------------------------------------------------

    await asyncio.sleep(1)

    df_method = getattr(
        client,
        "get_candles_dataframe",
        None
    )

    if callable(df_method):

        df = await call_method_flexible(
            df_method,
            variants,
            timeframe
        )

        if df is not None:

            if candle_is_current_or_recent(
                df,
                timeframe,
                tolerance_bars=1
            ):
                LAST_SIGNAL_DATA_SOURCE = "RETRY"
                print(
                    f"🟢 SIGNAL DATA SOURCE: RETRY {asset_code}",
                    flush=True
                )
                return df

    return None


def calculate_rsi(series, period=14):
    """
    Wilder RSI / RMA RSI.

    This is much closer to the RSI calculation commonly
    displayed by trading platforms than a simple rolling SMA RSI.
    """

    series = pd.to_numeric(
        series,
        errors="coerce"
    )

    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    # If loss is zero and gain exists, RSI is 100.
    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain > 0),
        100
    )

    # If both are zero, market is flat.
    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain == 0),
        50
    )

    return rsi


def calculate_accuracy(call_count, put_count):
    strongest = max(
        call_count,
        put_count
    )

    return {
        5: 90,
        4: 80,
        3: 60,
        2: 40,
        1: 20,
        0: 0
    }.get(
        strongest,
        0
    )


def sr_filter(df, price):

    lookback = min(
        50,
        len(df)
    )

    recent = df.tail(
        lookback
    )

    support = float(
        recent["low"].min()
    ) if "low" in recent.columns else float(
        recent["close"].min()
    )

    resistance = float(
        recent["high"].max()
    ) if "high" in recent.columns else float(
        recent["close"].max()
    )

    span = max(
        resistance - support,
        abs(price) * 0.001,
        1e-12
    )

    near_support = (
        abs(price - support)
        <= span * 0.08
    )

    near_resistance = (
        abs(resistance - price)
        <= span * 0.08
    )

    if near_support and not near_resistance:
        return True, support, resistance

    if near_resistance and not near_support:
        return False, support, resistance

    return True, support, resistance


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
        return "OFFLINE"

    try:

        recent = df.tail(
            20
        )[
            [
                "open",
                "high",
                "low",
                "close"
            ]
        ]

        rows = []

        for _, r in recent.iterrows():

            rows.append({
                "open": round(
                    float(r["open"]),
                    8
                ),
                "high": round(
                    float(r["high"]),
                    8
                ),
                "low": round(
                    float(r["low"]),
                    8
                ),
                "close": round(
                    float(r["close"]),
                    8
                )
            })

        direction = (
            "CALL"
            if call_count > put_count
            else "PUT"
            if put_count > call_count
            else "WAIT"
        )

        prompt = f"""
You are a conservative market-analysis confirmation engine.
You are NOT placing trades.
Analyze ONLY the supplied technical information.

Asset: {asset}
Timeframe: {timeframe}
Expiry: {expiry}
Technical direction: {direction}
CALL confirmations: {call_count}/5
PUT confirmations: {put_count}/5
Trend: {trend_signal}
RSI: {rsi_signal}
Current candle: {current_signal}
Previous candle: {previous_signal}
Higher timeframe: {higher_signal}
Price: {price}
Support: {support}
Resistance: {resistance}
Recent candles: {json.dumps(rows)}

Return exactly one word:
BUY
SELL
or
WAIT
"""

        def call_ai():

            url = (
                "https://generativelanguage.googleapis.com/"
                "v1beta/models/"
                f"{AI_MODEL}:generateContent"
            )

            response = requests.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": GEMINI_API_KEY
                },
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": prompt
                                }
                            ]
                        }
                    ]
                },
                timeout=10
            )

            if response.status_code != 200:

                print(
                    "GEMINI HTTP ERROR:",
                    response.status_code,
                    flush=True
                )

                return "OFFLINE"

            data = response.json()

            try:
                return (
                    data["candidates"][0]
                    ["content"]["parts"][0]["text"]
                )

            except Exception:
                return "OFFLINE"

        answer = (
            await asyncio.to_thread(
                call_ai
            )
        ).strip().upper()

        if re.search(
            r"\bBUY\b",
            answer
        ):
            return "BUY"

        if re.search(
            r"\bSELL\b",
            answer
        ):
            return "SELL"

        if re.search(
            r"\bWAIT\b",
            answer
        ):
            return "WAIT"

        return "OFFLINE"

    except Exception as e:

        print(
            "GEMINI AI ERROR:",
            repr(e),
            flush=True
        )

        return "OFFLINE"


def direction_text(value):
    return value if value else "NEUTRAL ⚪"


def build_signal_panel(
    asset,
    final_signal,
    technical,
    accuracy,
    timeframe,
    expiry,
    trend,
    rsi_signal,
    current_signal,
    previous_signal,
    higher_signal,
    call_count,
    put_count,
    price,
    ma10,
    ma50,
    rsi,
    sr_pass,
    support,
    resistance,
    gemini
):

    final_icon = (
        "🟢"
        if final_signal == "BUY"
        else "🔴"
        if final_signal == "SELL"
        else "⚪"
    )

    tech_icon = (
        "CALL"
        if call_count > put_count
        else "PUT"
        if put_count > call_count
        else "WAIT"
    )

    sr_text = (
        "PASS ✅"
        if sr_pass
        else "BLOCKED ❌"
    )

    ai_icon = (
        "🟢"
        if gemini == "BUY"
        else "🔴"
        if gemini == "SELL"
        else "🟡"
        if gemini == "OFFLINE"
        else "⚪"
    )

    technical_direction = (
        "BUY"
        if call_count > put_count
        else "SELL"
        if put_count > call_count
        else "WAIT"
    )

    if gemini == "OFFLINE":
        agreement = "UNAVAILABLE 🟡"
    elif gemini == technical_direction:
        agreement = "CONFIRMED ✅"
    elif gemini == "WAIT" or technical_direction == "WAIT":
        agreement = "NEUTRAL ⚪"
    else:
        agreement = "CONFLICT ⚠️"

    reason = ""

    if final_signal == "WAIT":

        reason = (
            "\n❌ Technical confirmation-ku "
            "4/5 ama 5/5 ma gaarin.\n"
        )

        if not sr_pass:
            reason = (
                "\n❌ S/R filter ayaa BLOCKED.\n"
            )

    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 NAASIRFX AI SIGNAL — LIVE DATA\n"
        f"📡 Data source: {LAST_SIGNAL_DATA_SOURCE}\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💱 {asset}\n\n"
        f"{final_icon} FINAL: {final_signal}\n"
        f"📊 Technical: {tech_icon} {technical}\n"
        f"🎯 Accuracy: {accuracy}%\n\n"
        f"⏱ Timeframe: {timeframe}\n"
        f"⌛ Expiry: {expiry}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 TECHNICAL ANALYSIS\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📈 Trend:       {trend}\n"
        f"📊 RSI:         {rsi_signal}\n"
        f"🕯 Current:     {current_signal}\n"
        f"🕯 Previous:    {previous_signal}\n"
        f"⏫ Higher TF:   {higher_signal}\n\n"
        f"🟢 CALL: {call_count}/5\n"
        f"🔴 PUT: {put_count}/5\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📐 MARKET DATA\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Price: {price:.8f}\n"
        f"📈 MA10:  {ma10:.8f}\n"
        f"📉 MA50:  {ma50:.8f}\n"
        f"📊 RSI:   {rsi:.2f}\n\n"
        f"🛡 S/R: {sr_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 GEMINI AI — HELPER\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"AI: {gemini} {ai_icon}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤝 TECHNICAL + GEMINI\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Technical: {technical_direction}\n"
        f"🤖 Gemini:    {gemini}\n"
        f"🔎 Agreement: {agreement}\n\n"
        "ℹ️ Gemini waa caawiye; ma beddelayo Technical signal-ka.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 FINAL SIGNAL\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{final_icon} {final_signal}\n"
        f"{reason}\n"
        "⚠️ SIGNAL ONLY\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


async def get_signal(
    asset_code,
    timeframe,
    timeframe_name,
    expiry_name,
    display_asset
):

    client = None

    try:

        client = await connect_client()

        # -----------------------------------------------------
        # GET FRESH MAIN TIMEFRAME DATA
        # -----------------------------------------------------

        df = await get_candles(
            client,
            asset_code,
            timeframe
        )

        if df is None or df.empty:

            return (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 NAASIRFX AI SIGNAL\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {display_asset}\n\n"
                "⚪ FINAL: WAIT\n\n"
                "❌ DATA LAMA HELIN\n\n"
                "Candles ku filan lama helin.\n\n"
                f"⏱ Timeframe: {timeframe_name}\n"
                f"⌛ Expiry: {expiry_name}\n\n"
                "⚠️ SIGNAL ONLY\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

        if len(df) < 55:

            return (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 NAASIRFX AI SIGNAL\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💱 {display_asset}\n\n"
                "⚪ FINAL: WAIT\n\n"
                "❌ DATA LAMA HELIN\n\n"
                "Candles ku filan lama helin.\n\n"
                f"⏱ Timeframe: {timeframe_name}\n"
                f"⌛ Expiry: {expiry_name}\n\n"
                "⚠️ SIGNAL ONLY\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

        # -----------------------------------------------------
        # SORT BY REAL CANDLE TIME
        # -----------------------------------------------------

        df = df.copy()

        if "_ts" in df.columns:

            df = df.sort_values(
                "_ts"
            ).reset_index(
                drop=True
            )

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

        # IMPORTANT:
        # Wilder RSI instead of simple rolling RSI.
        df["RSI"] = calculate_rsi(
            df["close"],
            14
        )

        # -----------------------------------------------------
        # CURRENT CANDLE
        # -----------------------------------------------------

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
        # TREND — CURRENT DATA
        # -----------------------------------------------------

        if (
            price > ma10
            and ma10 > ma50
        ):

            trend = "CALL 🟢"

        elif (
            price < ma10
            and ma10 < ma50
        ):

            trend = "PUT 🔴"

        else:

            trend = "NEUTRAL ⚪"

        # -----------------------------------------------------
        # RSI — CURRENT DATA
        # -----------------------------------------------------

        if (
            50 <= rsi <= 70
        ):

            rsi_signal = "CALL 🟢"

        elif (
            30 <= rsi < 50
        ):

            rsi_signal = "PUT 🔴"

        else:

            rsi_signal = "NEUTRAL ⚪"

        # -----------------------------------------------------
        # CURRENT CANDLE DIRECTION
        # -----------------------------------------------------

        current_close = float(
            latest["close"]
        )

        current_open = float(
            latest["open"]
        )

        previous_close = float(
            previous["close"]
        )

        previous_open = float(
            previous["open"]
        )

        if current_close > current_open:

            current_signal = "CALL 🟢"

        elif current_close < current_open:

            current_signal = "PUT 🔴"

        else:

            current_signal = "NEUTRAL ⚪"

        if previous_close > previous_open:

            previous_signal = "CALL 🟢"

        elif previous_close < previous_open:

            previous_signal = "PUT 🔴"

        else:

            previous_signal = "NEUTRAL ⚪"
             # -----------------------------------------------------
        # HIGHER TIMEFRAME — ALSO FRESH
        # -----------------------------------------------------

        higher_tf = HIGHER_TIMEFRAME[
            timeframe
        ]

        if higher_tf == timeframe:

            higher_signal = "NEUTRAL ⚪"

        else:

            higher_df = await get_candles(
                client,
                asset_code,
                higher_tf
            )

            if (
                higher_df is None
                or len(higher_df) < 1
            ):

                higher_signal = "NEUTRAL ⚪"

            else:

                if "_ts" in higher_df.columns:

                    higher_df = (
                        higher_df
                        .sort_values("_ts")
                        .reset_index(drop=True)
                    )

                h = higher_df.iloc[-1]

                h_open = float(
                    h["open"]
                )

                h_close = float(
                    h["close"]
                )

                if h_close > h_open:

                    higher_signal = "CALL 🟢"

                elif h_close < h_open:

                    higher_signal = "PUT 🔴"

                else:

                    higher_signal = "NEUTRAL ⚪"

        # -----------------------------------------------------
        # CONFIRMATIONS
        # -----------------------------------------------------

        call_count = 0
        put_count = 0

        for value in (
            trend,
            rsi_signal,
            current_signal,
            previous_signal,
            higher_signal
        ):

            if value.startswith("CALL"):
                call_count += 1

            elif value.startswith("PUT"):
                put_count += 1

        technical = (
            f"CALL {call_count}/5"
            if call_count > put_count
            else
            f"PUT {put_count}/5"
            if put_count > call_count
            else
            "WAIT"
        )

        accuracy = calculate_accuracy(
            call_count,
            put_count
        )

        # -----------------------------------------------------
        # SUPPORT / RESISTANCE
        # -----------------------------------------------------

        sr_pass, support, resistance = sr_filter(
            df,
            price
        )

        # -----------------------------------------------------
        # GEMINI — CONFIRMATION ONLY
        # -----------------------------------------------------

        gemini = await ask_gemini(
            display_asset,
            timeframe_name,
            expiry_name,
            df,
            higher_signal,
            trend,
            rsi_signal,
            current_signal,
            previous_signal,
            call_count,
            put_count,
            support,
            resistance,
            price
        )

        # -----------------------------------------------------
        # FINAL SIGNAL
        # -----------------------------------------------------

        final_signal = "WAIT"

        if (
            call_count >= 4
            and sr_pass
        ):

            final_signal = "BUY"

        elif (
            put_count >= 4
            and sr_pass
        ):

            final_signal = "SELL"

        # -----------------------------------------------------
        # FINAL PANEL
        # -----------------------------------------------------

        return build_signal_panel(
            display_asset,
            final_signal,
            technical,
            accuracy,
            timeframe_name,
            expiry_name,
            trend,
            rsi_signal,
            current_signal,
            previous_signal,
            higher_signal,
            call_count,
            put_count,
            price,
            ma10,
            ma50,
            rsi,
            sr_pass,
            support,
            resistance,
            gemini
        )

    except Exception as e:

        print(
            "SIGNAL ERROR:",
            repr(e),
            flush=True
        )

        return (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 NAASIRFX AI SIGNAL\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💱 {display_asset}\n\n"
            "⚪ FINAL: WAIT\n\n"
            "❌ SIGNAL ERROR\n\n"
            f"{type(e).__name__}: {e}\n\n"
            f"⏱ Timeframe: {timeframe_name}\n"
            f"⌛ Expiry: {expiry_name}\n\n"
            "⚠️ SIGNAL ONLY\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

    finally:

        if client is not None:

            try:
                await client.disconnect()
            except Exception:
                pass


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        ["📋 PAIRS"],
        ["⏱ TIMEFRAME", "⌛ EXPIRY"],
        ["ℹ️ STATUS"]
    ]

    await update.message.reply_text(
        "👋 Soo dhawoow NAASIRFX AI SIGNAL\n\n"
        "Dooro waxa aad rabto:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


async def show_pair_categories(update):

    keyboard = [
        ["💱 Forex", "💱 Forex OTC"],
        ["📈 Stocks", "📈 Stocks OTC"],
        ["🔙 BACK"]
    ]

    await update.message.reply_text(
        "📋 PAIRS\n\nDooro market-ka:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )


async def show_pairs(update, category):

    assets = CATEGORIES[category]

    rows = button_rows(
        list(assets.keys()),
        2
    )

    rows.append(
        ["🔙 BACK"]
    )

    await update.message.reply_text(
        f"{category}\n\n"
        f"📊 {len(assets)} assets\n\n"
        "Dooro Pair-ka:",
        reply_markup=ReplyKeyboardMarkup(
            rows,
            resize_keyboard=True
        )
    )


async def show_timeframes(update):

    rows = button_rows(
        list(TIMEFRAMES.keys()),
        2
    )

    rows.append(
        ["🔙 BACK"]
    )

    await update.message.reply_text(
        "⏱ TIMEFRAME\n\n"
        "Dooro Timeframe-ka:",
        reply_markup=ReplyKeyboardMarkup(
            rows,
            resize_keyboard=True
        )
    )


async def show_expiries(update):

    rows = button_rows(
        list(EXPIRIES.keys()),
        2
    )

    rows.append(
        ["🔙 BACK"]
    )

    await update.message.reply_text(
        "⌛ EXPIRY\n\n"
        "Dooro Expiry-ga:",
        reply_markup=ReplyKeyboardMarkup(
            rows,
            resize_keyboard=True
        )
    )


async def send_pair_signal(update):

    user_id = update.effective_user.id

    category = user_category.get(
        user_id
    )

    if not category:

        await update.message.reply_text(
            "❌ Marka hore 📋 PAIRS dooro."
        )

        return

    asset_name = update.message.text

    asset_code = CATEGORIES[
        category
    ].get(
        asset_name
    )

    if not asset_code:
        return

    timeframe_name = user_timeframe.get(
        user_id
    )

    expiry_name = user_expiry.get(
        user_id
    )

    if not timeframe_name:

        await update.message.reply_text(
            "❌ Marka hore ⏱ TIMEFRAME dooro."
        )

        return

    if not expiry_name:

        await update.message.reply_text(
            "❌ Marka hore ⌛ EXPIRY dooro."
        )

        return

    await update.message.reply_text(
        "⏳ Signal-ka waa la baarayaa..."
    )

    signal = await get_signal(
        asset_code,
        TIMEFRAMES[timeframe_name],
        timeframe_name,
        expiry_name,
        asset_name
    )

    await update.message.reply_text(
        signal
    )


async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text

    user_id = update.effective_user.id

    if text == "📋 PAIRS":

        await show_pair_categories(
            update
        )

        return

    if text == "⏱ TIMEFRAME":

        await show_timeframes(
            update
        )

        return

    if text == "⌛ EXPIRY":

        await show_expiries(
            update
        )

        return

    if text == "ℹ️ STATUS":

        await update.message.reply_text(
            "🟢 NAASIRFX AI SIGNAL\n\n"
            "🟢 Telegram: RUNNING\n"
            f"🟢 PO SSID: "
            f"{'FOUND' if PO_SSID else 'MISSING'}\n"
            f"🟢 Gemini: "
            f"{'FOUND' if GEMINI_API_KEY else 'MISSING'}\n"
            "📡 Signal Mode: ON-TIME / LIVE\n"
            "⚠️ Signal only"
        )

        return

    if text == "🔙 BACK":

        keyboard = [
            ["📋 PAIRS"],
            ["⏱ TIMEFRAME", "⌛ EXPIRY"],
            ["ℹ️ STATUS"]
        ]

        await update.message.reply_text(
            "🏠 Main Menu",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True
            )
        )

        return

    if text in CATEGORIES:

        user_category[
            user_id
        ] = text

        await show_pairs(
            update,
            text
        )

        return

    if text in TIMEFRAMES:

        user_timeframe[
            user_id
        ] = text

        await update.message.reply_text(
            f"✅ Timeframe: {text}\n\n"
            "⌛ Expiry-ga isma beddelin."
        )

        return

    if text in EXPIRIES:

        user_expiry[
            user_id
        ] = text

        await update.message.reply_text(
            f"✅ Expiry: {text}\n\n"
            "⏱ Timeframe-ka isma beddelin."
        )

        return

    category = user_category.get(
        user_id
    )

    if (
        category
        and text in CATEGORIES[category]
    ):

        await send_pair_signal(
            update
        )

        return

    await update.message.reply_text(
        "❌ Fadlan ka dooro menu-ga hoose."
    )


class HealthHandler(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        self.send_response(
            200
        )

        self.send_header(
            "Content-type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"NAASIRFX is running"
        )

    def log_message(
        self,
        format,
        *args
    ):
        return


def run_health_server():

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        (
            "0.0.0.0",
            port
        ),
        HealthHandler
    )

    print(
        f"🟢 HTTP SERVER RUNNING "
        f"ON 0.0.0.0:{port}",
        flush=True
    )

    server.serve_forever()


async def telegram_post_init(
    application
):

    try:

        await application.bot.delete_webhook(
            drop_pending_updates=True
        )

        print(
            "🧹 Telegram webhook cleaned.",
            flush=True
        )

    except Exception as e:

        print(
            "⚠️ Telegram cleanup:",
            e,
            flush=True
        )


def main():

    if not TOKEN:

        print(
            "❌ TELEGRAM_BOT_TOKEN lama helin.",
            flush=True
        )

        return

    if not PO_SSID:

        print(
            "⚠️ PO_SSID lama helin.",
            flush=True
        )

    Thread(
        target=run_health_server,
        daemon=True
    ).start()

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(
            telegram_post_init
        )
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler
        )
    )

    print(
        "🟢 NAASIRFX AI SIGNAL IS RUNNING",
        flush=True
    )

    app.run_polling(
        drop_pending_updates=True,
        bootstrap_retries=0
    )


if __name__ == "__main__":
    main()
