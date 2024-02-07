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


def update_exchange_status():
    global exchange_status

    try:
        USD = tickers.tickers["CNY=X"].history(period="2d", interval="60m")
        GBP = tickers.tickers["GBPCNY=X"].history(period="2d", interval="60m")
        EUR = tickers.tickers["EURCNY=X"].history(period="2d", interval="60m")
        CAD = tickers.tickers["CADCNY=X"].history(period="2d", interval="60m")

        exchange_status = {
            "GBP": format_number(GBP["Close"][GBP["Close"].keys().max()]),
            "EUR": format_number(EUR["Close"][EUR["Close"].keys().max()]),
            "USD": format_number(USD["Close"][USD["Close"].keys().max()]),
            "CAD": format_number(CAD["Close"][CAD["Close"].keys().max()]),
        }
    except Exception as e:
        pass


def update_stock_status():
    global stock_status

    try:
        HSI = tickers.tickers["^HSI"].history(period="2d", interval="60m")
        IXIC = tickers.tickers["^IXIC"].history(period="2d", interval="60m")
        GSPC = tickers.tickers["^GSPC"].history(period="2d", interval="60m")
        SS = tickers.tickers["000001.SS"].history(period="2d", interval="60m")

        stock_status = {
            "SS": format_number(SS["Close"][SS["Close"].keys().max()]),
            "HSI": format_number(HSI["Close"][HSI["Close"].keys().max()]),
            "IXIC": format_number(IXIC["Close"][IXIC["Close"].keys().max()]),
            "GSPC": format_number(GSPC["Close"][GSPC["Close"].keys().max()]),
        }
    except Exception as e:
        pass


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
