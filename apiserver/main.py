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

EXCHANGE_RATE_URL = os.environ.get("EXCHANGE_RATE_URL")

if (
    XUI_USERNAME is None
    or XUI_PASSWORD is None
    or XUI_LOGIN_URL is None
    or XUI_STATUS_URL is None
    or EXCHANGE_RATE_URL is None
):
    print("Environment variables not fulfilled")

xui_status = None
exchange_status = None
stock_status = None

xui_session = requests.Session()
tickers = yfinance.Tickers("^IXIC ^GSPC ^HSI 000001.SS")


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


def formatBytes(bytes):
    if bytes == 0:
        return "0 Byte"

    k = 1024
    sizes = ["Byte", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]

    i = math.floor(math.log(bytes) / math.log(k))

    return f"{bytes / math.pow(k, i):.2f}".rstrip("0").rstrip(".") + " " + sizes[i]


def bytesToSpeed(bytes):
    return formatBytes(bytes) + "/s"


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
        xui_status["up"] = bytesToSpeed(response["obj"]["netIO"]["up"])
        xui_status["down"] = bytesToSpeed(response["obj"]["netIO"]["down"])
        xui_status["sent"] = formatBytes(response["obj"]["netTraffic"]["sent"])
        xui_status["recv"] = formatBytes(response["obj"]["netTraffic"]["recv"])


def convert_exchange_rate(rate):
    if rate == 0:
        return "0"

    return f"{1 / rate:.2f}".rstrip("0").rstrip(".")


def update_exchange_status():
    global exchange_status

    response = requests.get(EXCHANGE_RATE_URL)

    if response.status_code == 200:
        response = response.json()
        exchange_status = {
            "GBP": convert_exchange_rate(response["rates"]["GBP"]),
            "EUR": convert_exchange_rate(response["rates"]["EUR"]),
            "USD": convert_exchange_rate(response["rates"]["USD"]),
            "CAD": convert_exchange_rate(response["rates"]["CAD"]),
        }


def convert_stock_price(price):
    return f"{price:.2f}".rstrip("0").rstrip(".")


def update_stock_status():
    global stock_status

    IXIC = tickers.tickers["^IXIC"].history(period="2d", interval="60m")
    GSPC = tickers.tickers["^GSPC"].history(period="2d", interval="60m")
    HSI = tickers.tickers["^HSI"].history(period="2d", interval="60m")
    SS = tickers.tickers["000001.SS"].history(period="2d", interval="60m")

    stock_status = {
        "IXIC": convert_stock_price(IXIC["Close"][IXIC["Close"].keys().max()]),
        "GSPC": convert_stock_price(GSPC["Close"][GSPC["Close"].keys().max()]),
        "HSI": convert_stock_price(HSI["Close"][HSI["Close"].keys().max()]),
        "SS": convert_stock_price(SS["Close"][SS["Close"].keys().max()]),
    }


if __name__ == "__main__":
    api_thread = threading.Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()

    schedule.every().hour.do(update_exchange_status)
    schedule.every(30).minutes.do(update_stock_status)

    schedule.run_all()

    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "API server started")

    while True:
        schedule.run_pending()
        time.sleep(10)
