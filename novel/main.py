import os
import time
import json
import random
import telebot
import datetime
import threading
import http.server
import socketserver
from lxml import etree
from curl_cffi import requests

IP_PATH = "/config/ip.txt"
BOOK_PATH = "/config/book.txt"
CACHE_PATH = "/cache/cache.json"

BOOK_URL = os.environ.get("BOOK_URL")
PROXY_URL = os.environ.get("PROXY_URL")
TELEBOT_TOKEN = os.environ.get("TELEBOT_TOKEN")
TELEBOT_USER_ID = os.environ.get("TELEBOT_USER_ID")

if (
    TELEBOT_TOKEN is None
    or TELEBOT_USER_ID is None
    or BOOK_URL is None
    or PROXY_URL is None
):
    print("Environment variables not fulfilled")

titles, last_updated_time, loop_time = None, None, None


def load_unavailable_ips():
    unavailable_ips = []

    with open(IP_PATH, "r") as file:
        lines = file.readlines()

    for line in lines:
        unavailable_ips.append(line.strip())

    return unavailable_ips


def load_proxies():
    try:
        proxies = []
        response = requests.get(PROXY_URL)

        if response.status_code == 200:
            file_content = response.text
            ip_list = file_content.strip().split("\n")

            for ip_entry in ip_list:
                ip, port, username, password = ip_entry.rstrip("\r").split(":")
                if ip not in load_unavailable_ips():
                    proxies.append((ip, port, username, password))

            if len(proxies) == 0:
                raise Exception("No available proxy")

            random.shuffle(proxies)

        else:
            raise Exception("Proxy server not responding")

        return proxies

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e))
        bot.send_message(TELEBOT_USER_ID, repr(e))
        raise SystemExit


def load_books():
    books = []
    with open(BOOK_PATH, "r") as file:
        lines = file.readlines()
    for line in lines:
        if line.startswith("//"):
            continue
        number, name = line.strip().split(":")
        books.append((number, name))
    return books


def load_cache():
    titles = dict()

    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r") as file:
            titles = json.load(file)
            book_name = set(name for _, name in books)
            book_name_previous = set(name + "previous" for _, name in books)
            dict_copy = titles.copy()
            for book in dict_copy.keys():
                if book not in book_name and book not in book_name_previous:
                    del titles[book]

    return titles


def get_url_html(url, proxy=None):
    try:
        request = requests.get(url, impersonate="chrome", proxies=proxy)
        return request.text

    except Exception as e:
        if proxy is None:
            print("The following error occurred when using native ip")
        raise e


def extract_book_title(html):
    try:
        html.encoding = "gbk"
        tree = etree.HTML(html, parser=None)
        div_element = tree.xpath('//div[contains(@class, "qustime")]')[0]
        span_element = div_element.xpath("./ul/li[1]/a/span")[0]
        return span_element.text

    except Exception as e:
        print("The following error occurred when extracting book title")
        raise e


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override the log_message method to do nothing
        pass

    def do_GET(self):
        if self.path == "/update":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            payload = {
                name: (titles.get(name, 'Unknown'), BOOK_URL.replace("BOOK_ID", id))
                for id, name in books
            }
            response = json.dumps(payload)
            self.wfile.write(response.encode("utf-8"))
        elif self.path == "/health":
            if time.time() - last_updated_time > loop_time:
                self.send_response(500)
                response = json.dumps({"status": "delayed"})
            else:
                self.send_response(200)
                response = json.dumps({"status": "ok"})
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(response.encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def start_api_server():
    with socketserver.TCPServer(("0.0.0.0", 80), HealthCheckHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    bot = telebot.TeleBot(TELEBOT_TOKEN)

    proxies = load_proxies()

    books = load_books()
    i = 0
    j = 0
    last_updated_time = time.time()
    loop_time = len(books) * 5 * 60
    sleep_interval = loop_time / len(books)

    titles = load_cache()

    api_thread = threading.Thread(target=start_api_server)
    api_thread.daemon = True
    api_thread.start()

    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Novel monitor started"
    )

    try:
        while True:
            for index in range(len(proxies)):
                j = (j + 1) % len(proxies)

                ip, port, username, password = proxies[j]
                # proxy = f"{username}:{password}@{ip}:{port}"
                proxy = {
                    "http": f"http://{username}:{password}@{ip}:{port}",
                    "https": f"http://{username}:{password}@{ip}:{port}",
                }

                try:
                    url = BOOK_URL.replace("BOOK_ID", books[i][0])
                    html = get_url_html(url, proxy)
                    title = extract_book_title(html)

                    if title != titles.get(books[i][1]):
                        if title == titles.get(books[i][1] + "previous"):
                            break

                        if title != extract_book_title(get_url_html(url)):
                            break

                        if titles.get(books[i][1]) is not None:
                            bot.send_message(
                                TELEBOT_USER_ID,
                                f"{books[i][1]}\n'{titles.get(books[i][1])}'\n->'{title}'\n{url}",
                            )

                        titles[books[i][1] + "previous"] = titles.get(books[i][1])
                        titles[books[i][1]] = title

                        with open(CACHE_PATH, "w") as file:
                            json.dump(titles, file)

                    break

                except Exception as e:
                    print(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e)
                    )
                    print(
                        f"Error occurred when checking {books[i][1]} with proxy {ip}:{port}"
                    )
                    print(
                        f"Error occurred during iteration {index} on line {e.__traceback__.tb_lineno}"
                    )
                    time.sleep(sleep_interval)
                    if index == len(proxies) - 1:
                        raise e

            last_updated_time = time.time()
            time.sleep(sleep_interval)
            i = (i + 1) % len(books)

    except Exception as e:
        bot.send_message(
            TELEBOT_USER_ID, "Novel monitor encountered unexpected exception"
        )
        bot.send_message(
            TELEBOT_USER_ID,
            f"The exception occurred when processing book {books[i][1]} with error message: {repr(e)}",
        )
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred, program terminated",
        )
