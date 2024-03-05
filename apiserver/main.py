import os
import time
import json
import math
import pandas
import yfinance
import requests
import schedule
import datetime
import threading
import http.server
import socketserver

STOCK_CACHE_PATH = "/cache/stock_cache.json"
INDEX_CACHE_PATH = "/cache/index_cache.json"
CRYPTO_CACHE_PATH = "/cache/crypto_cache.json"
CURRENCY_CACHE_PATH = "/cache/currency_cache.json"

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

STOCKS = "AAPL GOOG NVDA TSLA"
INDICES = "^IXIC ^GSPC 000001.SS"
CRYPTOS = "BTC-USD ETH-USD"
CURRENCIES = "GBPCNY=X EURCNY=X CNY=X CADCNY=X"

xui_session = requests.Session()
tickers = yfinance.Tickers(" ".join([STOCKS, INDICES, CRYPTOS, CURRENCIES]))


class apiHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override the log_message method to do nothing
        pass

    def do_GET(self):
        if self.path == "/xui":
            global xui_status
            update_xui_status()
            response = json.dumps(xui_status)
        elif self.path == "/capital":
            global stock_status
            global index_status
            response = json.dumps({**stock_status, **index_status})
        elif self.path == "/exchange":
            global crypto_status
            global currency_status
            response = json.dumps({**crypto_status, **currency_status})
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
    global stock_status
    global index_status
    global crypto_status
    global currency_status

    stock_status.update(load_cache(STOCK_CACHE_PATH, STOCKS))
    index_status.update(load_cache(INDEX_CACHE_PATH, INDICES))
    crypto_status.update(load_cache(CRYPTO_CACHE_PATH, CRYPTOS))
    currency_status.update(load_cache(CURRENCY_CACHE_PATH, CURRENCIES))


def format_number(number):
    if number == 0:
        return "0"

    return f"{number:.2f}".rstrip("0").rstrip(".")


def format_bytes(bytes):
    if bytes == 0:
        return "0 Byte"

    k = 1024
    sizes = ["Byte", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    i = math.floor(math.log(bytes) / math.log(k))

    return format_number(bytes / math.pow(k, i)) + " " + sizes[i]


def bytes_to_speed(bytes):
    return format_bytes(bytes) + "/s"


def get_xui_status():
    if xui_session.post(XUI_URL + "/panel/inbound/onlines").status_code != 200:
        xui_session.post(
            XUI_URL + "/login",
            data={"username": XUI_USERNAME, "password": XUI_PASSWORD},
        )

    status = xui_session.post(XUI_URL + "/server/status")
    online = xui_session.post(XUI_URL + "/panel/inbound/onlines")

    status = status.json()
    online = online.json()

    info = {
        "up": bytes_to_speed(status["obj"]["netIO"]["up"]),
        "down": bytes_to_speed(status["obj"]["netIO"]["down"]),
        "usage": format_bytes(status["obj"]["netTraffic"]["recv"]),
        "online": len(online["obj"]) if online["obj"] else 0,
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
    history = tickers.tickers[symbol].history(period="3d", interval="60m")

    latest_time = history.index.max()
    current_price = history.loc[latest_time]["Close"]

    counter = 0
    previous_time = latest_time - pandas.Timedelta(days=1)

    while previous_time not in history.index and counter < 31:
        previous_time -= pandas.Timedelta(days=1)
        counter += 1

    if previous_time not in history.index:
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred when calculating time interval",
        )
        previous_time = history.index.min()

    old_price = history.loc[previous_time]["Close"]

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
    global stock_status
    global index_status
    global crypto_status
    global currency_status

    info = get_info_by_ticker(symbols)

    if symbols == STOCKS:
        stock_status.update(info)
        with open(STOCK_CACHE_PATH, "w") as file:
            json.dump(stock_status, file)
    elif symbols == INDICES:
        index_status.update(info)
        with open(INDEX_CACHE_PATH, "w") as file:
            json.dump(index_status, file)
    elif symbols == CRYPTOS:
        crypto_status.update(info)
        with open(CRYPTO_CACHE_PATH, "w") as file:
            json.dump(crypto_status, file)
    elif symbols == CURRENCIES:
        currency_status.update(info)
        with open(CURRENCY_CACHE_PATH, "w") as file:
            json.dump(currency_status, file)


if __name__ == "__main__":
    load_all_cache()

    api_thread = threading.Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()

    schedule.every().hour.at(":00").do(update_status, symbols=STOCKS)
    schedule.every().hour.at(":15").do(update_status, symbols=INDICES)
    schedule.every().hour.at(":30").do(update_status, symbols=CRYPTOS)
    schedule.every().hour.at(":45").do(update_status, symbols=CURRENCIES)

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "API server started")

    while True:
        schedule.run_pending()
        time.sleep(10)
