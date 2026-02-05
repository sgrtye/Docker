import asyncio
import json
import logging
import math
import os
import platform
import random
import signal
import time

import httpx
import numpy
import pandas
import yfinance
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from uvicorn import Config, Server

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

sui_url: str | None = os.getenv("SUI_URL")
sui_token: str | None = os.getenv("SUI_TOKEN")

if sui_url is None or sui_token is None:
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(1)
else:
    SUI_URL: str = sui_url
    SUI_TOKEN: str = sui_token


sui_status: dict[str, str] = dict()
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

sui_session = httpx.AsyncClient()
tickers = yfinance.Tickers(
    " ".join([STOCKS, INDICES, CRYPTOS, CURRENCIES, COMMODITIES])
)

last_updated_time: float = time.time()

app = FastAPI()
NO_CACHE_HEADER: dict[str, str] = {
    "Content-Type": "application/json",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/health")
async def health_endpoint() -> JSONResponse:
    time_delta: float = time.time() - last_updated_time
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


@app.get("/sui")
async def sui_endpoint() -> JSONResponse:
    await update_sui_status()
    return JSONResponse(
        content=sui_status,
        headers=NO_CACHE_HEADER,
    )


@app.get("/capital")
async def capital_endpoint() -> JSONResponse:
    return JSONResponse(
        content=stock_status | index_status,
        headers=NO_CACHE_HEADER,
    )


@app.get("/exchange")
async def exchange_endpoint() -> JSONResponse:
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


async def get_sui_json_response(path_suffix: str) -> dict:
    return (
        await sui_session.get(SUI_URL + path_suffix, headers={"token": SUI_TOKEN})
    ).json()


async def get_sui_status() -> dict[str, str]:
    online: dict = await get_sui_json_response("/apiv2/onlines")
    assert online["success"]
    status: dict = await get_sui_json_response("/apiv2/status?r=net")
    assert status["success"]

    online_users: list[str] = online["obj"].get("user", [])
    online_name: str = random.choice(online_users) if len(online_users) > 0 else "-"

    info: dict[str, str] = {
        # "speed": format_bytes(status["obj"]["net"]["up"])  + "/s",
        "usage": format_bytes(status["obj"]["net"]["recv"]),
        "online": (
            f"{online_name} ({len(online_users)})"
            if len(online_users) > 1
            else online_name
        ),
    }
    return info


async def update_sui_status() -> None:
    global sui_status
    sui_status = {
        # "speed": "-",
        "usage": "-",
        "online": "-",
    }

    try:
        sui_status.update(await get_sui_status())

    # Exception handled by displaying the above default values
    except Exception:
        pass


def get_ticker_prices(symbol: str) -> tuple[float, float]:
    info = tickers.tickers[symbol].history(period="5d", interval="60m")

    latest_time: pandas.Timestamp = info.index.max()
    close_value = info.at[latest_time, "Close"]

    assert isinstance(close_value, numpy.integer | numpy.floating)
    current_price = float(close_value)

    counter: int = 0
    previous_time: pandas.Timestamp = latest_time - pandas.Timedelta(days=1)

    while previous_time.date() not in [d.date() for d in info.index] and counter < 31:
        previous_time -= pandas.Timedelta(days=1)
        counter += 1

    old_price = info.loc[info[info.index >= previous_time].index.min()]["Close"]
    assert isinstance(old_price, numpy.integer | numpy.floating)
    old_price = float(old_price)

    return (current_price, old_price)


def get_info_by_ticker(tickers: str) -> dict[str, str]:
    info: dict[str, str] = dict()
    ticker_list: list[str] = tickers.split(" ")

    for ticker in ticker_list:
        try:
            price, old_price = get_ticker_prices(ticker)
            trend: float = ((price - old_price) / old_price) * 100
            info[ticker] = format_number(price)
            info[ticker + TREND_ENDING] = format_number(trend)

        except Exception as e:
            logger.error(
                f"Error {repr(e)} occurred on line {e.__traceback__.tb_lineno if e.__traceback__ else '-1'}"
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
