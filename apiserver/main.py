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

XUI_URL = os.environ.get("XUI_URL")
XUI_USERNAME = os.environ.get("XUI_USERNAME")
XUI_PASSWORD = os.environ.get("XUI_PASSWORD")

if XUI_URL is None or XUI_USERNAME is None or XUI_PASSWORD is None:
    print("Environment variables not fulfilled")

xui_status = dict()
stock_status = dict()
index_status = dict()
crypto_status = dict()
currency_status = dict()
commodity_status = dict()

STOCKS = "AAPL GOOG NVDA TSLA"
INDICES = "^IXIC ^GSPC 000001.SS"
CRYPTOS = "BTC-USD ETH-USD"
CURRENCIES = "GBPCNY=X EURCNY=X CNY=X CADCNY=X"
COMMODITIES = "GC=F CL=F"

STOCK_CACHE_PATH = "/cache/stock_cache.json"
INDEX_CACHE_PATH = "/cache/index_cache.json"
CRYPTO_CACHE_PATH = "/cache/crypto_cache.json"
CURRENCY_CACHE_PATH = "/cache/currency_cache.json"
COMMODITY_CACHE_PATH = "/cache/commodity_cache.json"

MAPPING = {
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

lastUpdatedTime = time.time()


class apiHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override the log_message method to do nothing
        pass

    def do_GET(self):
        if self.path == "/xui":
            update_xui_status()
            response = json.dumps(xui_status)
        elif self.path == "/capital":
            response = json.dumps({**stock_status, **index_status})
        elif self.path == "/exchange":
            response = json.dumps(
                {**crypto_status, **currency_status, **commodity_status}
            )
        elif self.path == "/health":
            if time.time() - lastUpdatedTime > 1200:
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


def start_api_server():
    with socketserver.TCPServer(("0.0.0.0", 8888), apiHandler) as httpd:
        httpd.serve_forever()


def load_cache(CACHE_PATH, symbols):
    result = dict()
    symbols = symbols.split()
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r") as file:
            cache = json.load(file)

            for ticker, value in cache.items():
                symbol = ticker
                if symbol.endswith("_TREND"):
                    symbol = symbol[:-6]

                if symbol in symbols:
                    result[ticker] = value

    return result


def load_all_cache():
    for symbol, (status, cache_path) in MAPPING.items():
        status.update(load_cache(cache_path, symbol))


def format_number(number, decimal_place=2):
    if number == 0:
        return "0"

    return f"{number:.{decimal_place}f}".rstrip("0").rstrip(".")


def format_bytes(bytes, decimal_place=2):
    if bytes == 0:
        return "0 Byte"

    k = 1024
    sizes = ["Byte", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    i = math.floor(math.log(bytes) / math.log(k))

    return format_number(bytes / math.pow(k, i), decimal_place) + " " + sizes[i]


def bytes_to_speed(bytes, decimal_place=2):
    return format_bytes(bytes, decimal_place) + "/s"


def xui_login():
    if xui_session.post(XUI_URL + "/panel/inbound/onlines").status_code != 200:
        xui_session.post(
            XUI_URL + "/login",
            data={"username": XUI_USERNAME, "password": XUI_PASSWORD},
        )


def get_xui_status():
    xui_login()

    status = xui_session.post(XUI_URL + "/server/status")
    online = xui_session.post(XUI_URL + "/panel/inbound/onlines")

    status = status.json()
    online = online.json()

    info = {
        "up": bytes_to_speed(status["obj"]["netIO"]["up"]),
        "down": bytes_to_speed(status["obj"]["netIO"]["down"]),
        "usage": format_bytes(status["obj"]["netTraffic"]["recv"]),
        "online": random.choice(online["obj"]) if online["obj"] else "-",
    }
    return info


def update_xui_status():
    global xui_status
    xui_status = {
        "up": 0,
        "down": 0,
        "usage": 0,
        "online": 0,
    }

    xui_status.update(get_xui_status())


def get_ticker_prices(symbol):
    info = tickers.tickers[symbol].history(period="3d", interval="60m")

    latest_time = info.index.max()
    current_price = info.loc[latest_time]["Close"]

    counter = 0
    previous_time = latest_time - pandas.Timedelta(days=1)

    while previous_time.date() not in info.index.date and counter < 31:
        previous_time -= pandas.Timedelta(days=1)
        counter += 1

    old_price = info.loc[info[info.index >= previous_time].index.min()]["Close"]

    return (current_price, old_price)


def get_info_by_ticker(tickers):
    info = dict()
    tickers = tickers.split(" ")

    try:
        for ticker in tickers:
            price, old_price = get_ticker_prices(ticker)
            trend = ((price - old_price) / old_price) * 100
            info[ticker] = format_number(price)
            info[ticker + "_TREND"] = format_number(trend)
    except Exception as e:
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred when fetching information",
        )

    return info


def update_status(symbols):
    info = get_info_by_ticker(symbols)

    MAPPING[symbols][0].update(info)
    with open(MAPPING[symbols][1], "w") as file:
        json.dump(MAPPING[symbols][0], file)

    global lastUpdatedTime
    lastUpdatedTime = time.time()


if __name__ == "__main__":
    load_all_cache()

    api_thread = threading.Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()

    schedule.every().hour.at(":00").do(update_status, symbols=STOCKS)
    schedule.every().hour.at(":12").do(update_status, symbols=INDICES)
    schedule.every().hour.at(":24").do(update_status, symbols=CRYPTOS)
    schedule.every().hour.at(":36").do(update_status, symbols=CURRENCIES)
    schedule.every().hour.at(":48").do(update_status, symbols=COMMODITIES)

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "API server started")

    while True:
        schedule.run_pending()
        time.sleep(10)
