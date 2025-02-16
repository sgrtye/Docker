import os
import time
import json
import math
import random
import signal
import platform

import pandas
import yfinance

import httpx
import asyncio
from fastapi import FastAPI
from uvicorn import Config, Server
from fastapi.responses import JSONResponse

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import logging

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

XUI_URL: str | None = os.getenv("XUI_URL")
XUI_USERNAME: str | None = os.getenv("XUI_USERNAME")
XUI_PASSWORD: str | None = os.getenv("XUI_PASSWORD")

if XUI_URL is None or XUI_USERNAME is None or XUI_PASSWORD is None:
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(0)

xui_status: dict[str, str] = dict()
stock_status: dict[str, str] = dict()
index_status: dict[str, str] = dict()
crypto_status: dict[str, str] = dict()
currency_status: dict[str, str] = dict()
commodity_status: dict[str, str] = dict()

TREND_ENDING: str = "_TREND"

STOCKS: str = "AAPL GOOG NVDA TSLA"
INDICES: str = "^IXIC ^GSPC 000001.SS ^HSI"
CRYPTOS: str = "BTC-USD ETH-USD"
CURRENCIES: str = "GBPCNY=X EURCNY=X CNY=X CADCNY=X"
COMMODITIES: str = "GC=F CL=F"

CACHE_PATH: str = "/cache/cache.json"

MAPPING: dict[str, dict[str, str]] = {
    STOCKS: stock_status,
    INDICES: index_status,
    CRYPTOS: crypto_status,
    CURRENCIES: currency_status,
    COMMODITIES: commodity_status,
}

xui_session = httpx.AsyncClient()
tickers = yfinance.Tickers(
    " ".join([STOCKS, INDICES, CRYPTOS, CURRENCIES, COMMODITIES])
)

last_updated_time: float = time.time()
xui_rate_limit_time: float = time.time()

app = FastAPI()
NO_CACHE_HEADER = {
    "Content-Type": "application/json",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/health")
async def health_endpoint():
    time_delta = time.time() - last_updated_time
    if time_delta <= ((60 // max(len(MAPPING), 1)) + 1) * 60:
        return JSONResponse(
            content={"message": f"<OK> {time_delta} seconds since the last update."},
            headers=NO_CACHE_HEADER,
        )
    else:
        return JSONResponse(
            content={
                "message": f"<Delayed> {time_delta} seconds since the last update."
            },
            status_code=500,
            headers=NO_CACHE_HEADER,
        )


@app.get("/xui")
async def xui_endpoint():
    await update_xui_status()
    return JSONResponse(
        content=xui_status,
        headers=NO_CACHE_HEADER,
    )


@app.get("/capital")
async def capital_endpoint():
    return JSONResponse(
        content=stock_status | index_status,
        headers=NO_CACHE_HEADER,
    )


@app.get("/exchange")
async def exchange_endpoint():
    return JSONResponse(
        content=crypto_status | currency_status | commodity_status,
        headers=NO_CACHE_HEADER,
    )


def format_number(number: float, decimal_place: int = 2) -> str:
    if number == 0:
        return "0"

    return f"{number:.{decimal_place}f}".rstrip("0").rstrip(".")


def format_bytes(bytes: int, decimal_place: int = 2) -> str:
    if bytes == 0:
        return "0 Byte"

    k: int = 1024
    sizes: list[str] = ["Byte", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    i: int = math.floor(math.log(bytes) / math.log(k))

    return format_number(bytes / math.pow(k, i), decimal_place) + " " + sizes[i]


def bytes_to_speed(bytes: int, decimal_place: int = 2) -> str:
    return format_bytes(bytes, decimal_place) + "/s"


async def xui_login() -> None:
    global xui_rate_limit_time
    # Rate limit to every 5 seconds
    if time.time() - xui_rate_limit_time < 5:
        return

    await xui_session.post(
        XUI_URL + "/login", data={"username": XUI_USERNAME, "password": XUI_PASSWORD}
    )
    xui_rate_limit_time = time.time()


async def get_xui_info(path_suffix: str) -> dict:
    if (info := await xui_session.post(XUI_URL + path_suffix)).status_code != 200:
        await xui_login()
        info = await xui_session.post(XUI_URL + path_suffix)

    return info.json()


async def get_xui_status() -> dict[str, str]:
    status: dict = await get_xui_info("/server/status")
    online: dict[str] = await get_xui_info("/xui/inbound/onlines")

    online_count: int = len(online["obj"]) if online["obj"] else 0
    online_name: str = random.choice(online["obj"]) if online_count > 0 else "-"

    info: dict[str, str] = {
        "speed": bytes_to_speed(status["obj"]["netIO"]["up"]),
        "usage": format_bytes(status["obj"]["netTraffic"]["sent"]),
        "online": (
            f"{online_name} ({online_count})" if online_count > 1 else online_name
        ),
    }
    return info


async def update_xui_status() -> None:
    global xui_status
    xui_status = {
        "speed": -1,
        "usage": -1,
        "online": "-",
    }

    try:
        xui_status.update(await get_xui_status())

    # Exception handled by displaying the above default values
    except Exception:
        pass


def get_ticker_prices(symbol: str) -> tuple[float, float]:
    info = tickers.tickers[symbol].history(period="5d", interval="60m")

    latest_time: pandas.Timestamp = info.index.max()
    current_price: float = info.loc[latest_time]["Close"]

    counter: int = 0
    previous_time: pandas.Timestamp = latest_time - pandas.Timedelta(days=1)

    while previous_time.date() not in info.index.date and counter < 31:
        previous_time -= pandas.Timedelta(days=1)
        counter += 1

    old_price: float = info.loc[info[info.index >= previous_time].index.min()]["Close"]

    return (current_price, old_price)


def get_info_by_ticker(tickers: str) -> dict[str, str]:
    info: dict[str, str] = dict()
    tickers: list[str] = tickers.split(" ")

    for ticker in tickers:
        try:
            price, old_price = get_ticker_prices(ticker)
            trend = ((price - old_price) / old_price) * 100
            info[ticker] = format_number(price)
            info[ticker + TREND_ENDING] = format_number(trend)

        except Exception as e:
            logger.error(
                f"Error {repr(e)} occurred on line {e.__traceback__.tb_lineno}"
            )

    if info:
        global last_updated_time
        last_updated_time = time.time()

    return info


def load_cache() -> None:
    for all_symbol, status in MAPPING.items():
        symbols: list[str] = all_symbol.split()

        for symbol in symbols:
            status[symbol] = "0"
            status[symbol + TREND_ENDING] = "0"

    if not os.path.exists(CACHE_PATH):
        logger.info("No cache file found.")
        return

    with open(CACHE_PATH, "r") as file:
        cache: dict[str, str] = json.load(file)

    for all_symbol, status in MAPPING.items():
        symbols: list[str] = all_symbol.split()

        for ticker, value in cache.items():
            if ticker.removesuffix(TREND_ENDING) in symbols:
                status[ticker] = value

    logger.info("Cache file loaded successfully.")


def update_status(symbols: str) -> None:
    info = get_info_by_ticker(symbols)
    MAPPING[symbols].update(info)


def save_status() -> None:
    cache: dict[str, str] = dict()
    for symbols in MAPPING.keys():
        cache.update(MAPPING[symbols])

    with open(CACHE_PATH, "w") as file:
        json.dump(cache, file)


async def start_api_server() -> None:
    config = Config(app=app, host="0.0.0.0", port=80, log_level="critical")
    await Server(config).serve()


def schedule_yfinance_updates() -> None:
    scheduler = AsyncIOScheduler()
    interval = 60 // len(MAPPING)

    scheduler.add_job(
        save_status,
        "cron",
        hour=10,
        minute=24,
    )

    for i, symbol in enumerate(MAPPING.keys()):
        scheduler.add_job(
            update_status,
            "cron",
            minute=i * interval,
            kwargs={"symbols": symbol},
        )

    scheduler.start()


def handle_termination_signal() -> None:
    save_status()
    logger.info("All status saved before exiting")
    raise SystemExit(0)


async def main() -> None:
    load_cache()

    match platform.system():
        case "Linux":
            asyncio.get_running_loop().add_signal_handler(
                signal.SIGTERM, handle_termination_signal
            )
            logger.info("Signal handler for SIGTERM is registered.")

        case _:
            logger.info("Signal handler registration skipped.")
            pass

    logger.info("API server started")

    schedule_yfinance_updates()
    await start_api_server()


if __name__ == "__main__":
    asyncio.run(main())
