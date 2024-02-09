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

import warnings
warnings.simplefilter(action="ignore", category=FutureWarning)

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

xui_status = None
exchange_status = None
stock_status = None

xui_session = requests.Session()
tickers = yfinance.Tickers(
    "^IXIC ^GSPC 000001.SS ^HSI GBPCNY=X EURCNY=X CNY=X CADCNY=X"
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
        xui_status["up"] = bytes_to_speed(response["obj"]["netIO"]["up"])
        xui_status["down"] = bytes_to_speed(response["obj"]["netIO"]["down"])
        xui_status["sent"] = format_bytes(response["obj"]["netTraffic"]["sent"])
        xui_status["recv"] = format_bytes(response["obj"]["netTraffic"]["recv"])


def get_ticker_info(symbol, trend=False):
    current_info = tickers.tickers[symbol].history(period="7d", interval="1d")
    current_price = current_info["Close"][current_info["Close"].keys().min()]

    if not trend:
        return current_price

    old_info = tickers.tickers[symbol].history(period="2d", interval="60m")
    old_price = old_info["Close"][old_info["Close"].keys().max()]

    return ((old_price - current_price) / current_price) * 100


def update_exchange_status():
    global exchange_status

    try:
        exchange_status = {
            "USD": format_number(get_ticker_info("CNY=X")),
            "GBP": format_number(get_ticker_info("GBPCNY=X")),
            "EUR": format_number(get_ticker_info("EURCNY=X")),
            "CAD": format_number(get_ticker_info("CADCNY=X")),
            "USD_TREND": format_number(get_ticker_info("CNY=X", trend=True)),
            "GBP_TREND": format_number(get_ticker_info("GBPCNY=X", trend=True)),
            "EUR_TREND": format_number(get_ticker_info("EURCNY=X", trend=True)),
            "CAD_TREND": format_number(get_ticker_info("CADCNY=X", trend=True)),
        }
    except Exception as e:
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred when fetching exchange status",
        )


def update_stock_status():
    global stock_status

    try:
        stock_status = {
            "HSI": "HK$" + format_number(get_ticker_info("^HSI")),
            "IXIC": "$" + format_number(get_ticker_info("^IXIC")),
            "GSPC": "$" + format_number(get_ticker_info("^GSPC")),
            "SS": "¥" + format_number(get_ticker_info("000001.SS")),
            "HSI_TREND": format_number(get_ticker_info("^HSI", trend=True)),
            "IXIC_TREND": format_number(get_ticker_info("^IXIC", trend=True)),
            "GSPC_TREND": format_number(get_ticker_info("^GSPC", trend=True)),
            "SS_TREND": format_number(get_ticker_info("000001.SS", trend=True)),
        }
    except Exception as e:
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred when fetching stock status",
        )


if __name__ == "__main__":
    api_thread = threading.Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()

    schedule.every(30).minutes.do(update_exchange_status)
    schedule.every(30).minutes.do(update_stock_status)

    schedule.run_all()

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "API server started")

    while True:
        schedule.run_pending()
        time.sleep(10)
