import os
import time
import json
import math
import yfinance
import requests
import schedule
import datetime
import threading
import http.server
import socketserver

XUI_USERNAME = os.environ.get("XUI_USERNAME")
XUI_PASSWORD = os.environ.get("XUI_PASSWORD")

XUI_LOGIN_URL = os.environ.get("XUI_LOGIN_URL")
XUI_STATUS_URL = os.environ.get("XUI_STATUS_URL")

if (
    XUI_USERNAME is None
    or XUI_PASSWORD is None
    or XUI_LOGIN_URL is None
    or XUI_STATUS_URL is None
):
    print("Environment variables not fulfilled")

xui_status = dict()
exchange_status = dict()
stock_status = dict()

xui_session = requests.Session()
tickers = yfinance.Tickers(
    "^IXIC ^GSPC 000001.SS AAPL GOOG NVDA TSLA GBPCNY=X CNY=X CADCNY=X BTC-USD"
)


class apiHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override the log_message method to do nothing
        pass

    def do_GET(self):
        if self.path == "/xui":
            global xui_status
            update_xui_status()
            response = json.dumps(xui_status)
        elif self.path == "/exchange":
            global exchange_status
            response = json.dumps(exchange_status)
        elif self.path == "/stock":
            global stock_status
            response = json.dumps(stock_status)
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


def update_xui_status():
    global xui_status
    xui_status = {
        "up": 0,
        "down": 0,
        "sent": 0,
        "recv": 0,
    }

    response = xui_session.post(XUI_STATUS_URL)
    if response.status_code == 404:
        xui_session.post(
            XUI_LOGIN_URL, data={"username": XUI_USERNAME, "password": XUI_PASSWORD}
        )
        response = xui_session.post(XUI_STATUS_URL)

    if response.status_code == 200:
        response = response.json()
        xui_status = {
            "up": bytes_to_speed(response["obj"]["netIO"]["up"]),
            "down": bytes_to_speed(response["obj"]["netIO"]["down"]),
            "sent": format_bytes(response["obj"]["netTraffic"]["sent"]),
            "recv": format_bytes(response["obj"]["netTraffic"]["recv"]),
        }


def get_ticker_prices(symbol):
    current_info = tickers.tickers[symbol].history(period="2d", interval="60m")
    current_price = current_info["Close"][current_info["Close"].keys().max()]

    old_info = tickers.tickers[symbol].history(period="7d", interval="1d")
    old_price = old_info["Close"][old_info["Close"].keys().min()]

    return (current_price, old_price)


def get_info_by_ticker(tickers):
    info = dict()
    tickers = tickers.split(" ")

    for ticker in tickers:
        price, old_price = get_ticker_prices(ticker)
        trend = ((price - old_price) / old_price) * 100
        info[ticker] = format_number(price)
        info[ticker + "_TREND"] = format_number(trend)

    return info


def update_exchange_status():
    global exchange_status

    try:
        info = get_info_by_ticker("GBPCNY=X CNY=X CADCNY=X BTC-USD")

        for ticker, value in info.items():
            exchange_status[ticker] = value

    except Exception as e:
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred when fetching exchange status",
        )


def update_stock_status():
    global stock_status

    try:
        info = get_info_by_ticker("^IXIC ^GSPC 000001.SS")

        for ticker, value in info.items():
            stock_status[ticker] = value

    except Exception as e:
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred when fetching stock status",
        )


def update_index_status():
    global stock_status

    try:
        info = get_info_by_ticker("AAPL GOOG NVDA TSLA")

        for ticker, value in info.items():
            stock_status[ticker] = value

    except Exception as e:
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred when fetching index status",
        )


if __name__ == "__main__":
    api_thread = threading.Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()

    schedule.every().hour.at(":10").do(update_exchange_status)
    schedule.every().hour.at(":30").do(update_stock_status)
    schedule.every().hour.at(":50").do(update_index_status)

    schedule.run_all()

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "API server started")

    while True:
        schedule.run_pending()
        time.sleep(10)
