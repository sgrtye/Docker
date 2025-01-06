import os
import time
import json
import math
import httpx
import signal
import random
import pandas
import asyncio
import yfinance
import datetime
from fastapi import FastAPI
import aioschedule as schedule
from uvicorn import Config, Server
from fastapi.responses import JSONResponse

XUI_URL: str | None = os.environ.get("XUI_URL")
XUI_USERNAME: str | None = os.environ.get("XUI_USERNAME")
XUI_PASSWORD: str | None = os.environ.get("XUI_PASSWORD")

if XUI_URL is None or XUI_USERNAME is None or XUI_PASSWORD is None:
    print("Environment variables not fulfilled")
    raise SystemExit

xui_status: dict[str, str] = dict()
stock_status: dict[str, str] = dict()
index_status: dict[str, str] = dict()
crypto_status: dict[str, str] = dict()
currency_status: dict[str, str] = dict()
commodity_status: dict[str, str] = dict()

UPDATE_INTERVAL: int = 12
TREND_ENDING: str = "_TREND"

STOCKS: str = "AAPL GOOG NVDA TSLA"
INDICES: str = "^IXIC ^GSPC 000001.SS"
CRYPTOS: str = "BTC-USD ETH-USD"
CURRENCIES: str = "GBPCNY=X EURCNY=X CNY=X CADCNY=X"
COMMODITIES: str = "GC=F CL=F"

STOCK_CACHE_PATH: str = "/cache/stock_cache.json"
INDEX_CACHE_PATH: str = "/cache/index_cache.json"
CRYPTO_CACHE_PATH: str = "/cache/crypto_cache.json"
CURRENCY_CACHE_PATH: str = "/cache/currency_cache.json"
COMMODITY_CACHE_PATH: str = "/cache/commodity_cache.json"

MAPPING: dict[str, tuple[dict[str, str], str]] = {
    STOCKS: (stock_status, STOCK_CACHE_PATH),
    INDICES: (index_status, INDEX_CACHE_PATH),
    CRYPTOS: (crypto_status, CRYPTO_CACHE_PATH),
    CURRENCIES: (currency_status, CURRENCY_CACHE_PATH),
    COMMODITIES: (commodity_status, COMMODITY_CACHE_PATH),
}

xui_session: httpx.AsyncClient | None = None
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
    if time.time() - last_updated_time < (UPDATE_INTERVAL + 1) * 60:
        return JSONResponse(
            content={"message": "OK"}, status_code=200, headers=NO_CACHE_HEADER
        )
    else:
        return JSONResponse(
            content={"message": "Yahoo finance info not up to date"},
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


def load_cache(cache_path: str, symbols: str) -> dict[str, str]:
    result: dict[str, str] = dict()
    symbols: list[str] = symbols.split()

    if os.path.exists(cache_path):
        with open(cache_path, "r") as file:
            cache: dict[str, str] = json.load(file)

            for ticker, value in cache.items():
                if ticker.removesuffix(TREND_ENDING) in symbols:
                    result[ticker] = value

    return result


def load_all_cache() -> None:
    for symbol, (status, cache_path) in MAPPING.items():
        status.update(load_cache(cache_path, symbol))


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


async def create_session() -> None:
    global xui_session
    xui_session = httpx.AsyncClient()


async def post_request(url: str, data: dict | None = None) -> dict:
    if xui_session is None:
        await create_session()

    response = await xui_session.post(url, data=data)
    return response.json()


async def xui_login() -> None:
    global xui_rate_limit_time

    if (sleep_time := 5 - (time.time() - xui_rate_limit_time)) > 0:
        await asyncio.sleep(sleep_time)
    xui_rate_limit_time = time.time()

    await post_request(
        XUI_URL + "/login", {"username": XUI_USERNAME, "password": XUI_PASSWORD}
    )


async def get_xui_info(path_suffix: str) -> dict:
    while (info := await post_request(XUI_URL + path_suffix)).status_code != 200:
        await xui_login()

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
    except Exception:
        pass


def get_ticker_prices(symbol) -> tuple[float, float]:
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


def get_info_by_ticker(tickers) -> dict[str, str]:
    info: dict[str, str] = dict()
    tickers: list[str] = tickers.split(" ")

    for ticker in tickers:
        try:
            price, old_price = get_ticker_prices(ticker)
            trend = ((price - old_price) / old_price) * 100
            info[ticker] = format_number(price)
            info[ticker + TREND_ENDING] = format_number(trend)

        except Exception as e:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print(f"Error {repr(e)} occurred on line {e.__traceback__.tb_lineno}")

    if info:
        global last_updated_time
        last_updated_time = time.time()

    return info


def update_status(symbols) -> None:
    info = get_info_by_ticker(symbols)
    MAPPING[symbols][0].update(info)


def save_status() -> None:
    for symbols in MAPPING.keys():
        with open(MAPPING[symbols][1], "w") as file:
            json.dump(MAPPING[symbols][0], file)


async def start_api_server():
    config = Config(app=app, host="0.0.0.0", port=80)
    await Server(config).serve()


async def update_finance_status() -> None:
    schedule.every().hour.at(f":{str(UPDATE_INTERVAL * 0).zfill(2)}").do(
        update_status, symbols=STOCKS
    )
    schedule.every().hour.at(f":{str(UPDATE_INTERVAL * 1).zfill(2)}").do(
        update_status, symbols=INDICES
    )
    schedule.every().hour.at(f":{str(UPDATE_INTERVAL * 2).zfill(2)}").do(
        update_status, symbols=CRYPTOS
    )
    schedule.every().hour.at(f":{str(UPDATE_INTERVAL * 3).zfill(2)}").do(
        update_status, symbols=CURRENCIES
    )
    schedule.every().hour.at(f":{str(UPDATE_INTERVAL * 4).zfill(2)}").do(
        update_status, symbols=COMMODITIES
    )
    schedule.every().day.at("10:24").do(save_status)

    while True:
        await schedule.run_pending()
        await asyncio.sleep(60)


def handle_sigterm(signum, frame) -> None:
    save_status()
    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "All status saved before exiting",
    )
    raise SystemExit(0)


async def main() -> None:
    load_all_cache()
    signal.signal(signal.SIGTERM, handle_sigterm)

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "API server started")

    await asyncio.gather(start_api_server(), update_finance_status())


if __name__ == "__main__":
    asyncio.run(main())
