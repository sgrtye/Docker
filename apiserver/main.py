import os
import time
import json
import math
import random
import pandas
import yfinance
import requests
import schedule
import datetime
import threading
import http.server
import socketserver

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

xui_session = requests.Session()
tickers = yfinance.Tickers(
    " ".join([STOCKS, INDICES, CRYPTOS, CURRENCIES, COMMODITIES])
)

last_updated_time: float = time.time()


class apiHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args) -> None:
        # Override the log_message method to do nothing
        pass

    def do_GET(self) -> None:
        if self.path == "/xui":
            update_xui_status()
            response = json.dumps(xui_status)
        elif self.path == "/capital":
            response = json.dumps(stock_status | index_status)
        elif self.path == "/exchange":
            response = json.dumps(crypto_status | currency_status | commodity_status)
        elif self.path == "/health":
            if time.time() - last_updated_time > (UPDATE_INTERVAL + 1) * 60:
                self.send_response(500)
            else:
                self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            return
        else:
            message = {"message": "Not Found"}
            response = json.dumps(message)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        self.wfile.write(response.encode("utf-8"))


def start_api_server() -> None:
    with socketserver.TCPServer(("0.0.0.0", 80), apiHandler) as httpd:
        httpd.serve_forever()


def load_cache(cache_path: str, symbols: str) -> dict[str, str]:
    result: dict[str, str] = dict()
    symbols: list[str] = symbols.split()

    if os.path.exists(cache_path):
        with open(cache_path, "r") as file:
            cache: dict[str, str] = json.load(file)

            for ticker, value in cache.items():
                if ticker.removesuffix("_TREAD") in symbols:
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


def xui_login() -> None:
    if xui_session.post(XUI_URL + "/server/status").status_code != 200:
        xui_session.post(
            XUI_URL + "/login",
            data={"username": XUI_USERNAME, "password": XUI_PASSWORD},
        )


def get_xui_status() -> dict[str, str]:
    xui_login()

    status = xui_session.post(XUI_URL + "/server/status")
    online = xui_session.post(XUI_URL + "/xui/inbound/onlines")

    status: dict = status.json()
    online: dict[str] = online.json()

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


def update_xui_status() -> None:
    global xui_status
    xui_status: dict[str, str] = {
        "speed": 0,
        "usage": 0,
        "online": "-",
    }

    xui_status.update(get_xui_status())


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
            info[ticker + "_TREND"] = format_number(trend)

        except Exception as e:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e))

    if info:
        global last_updated_time
        last_updated_time = time.time()

    return info


def update_status(symbols) -> None:
    info = get_info_by_ticker(symbols)

    MAPPING[symbols][0].update(info)
    with open(MAPPING[symbols][1], "w") as file:
        json.dump(MAPPING[symbols][0], file)


def main() -> None:
    load_all_cache()

    api_thread = threading.Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()

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

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "API server started")

    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
