import os
import time
import json
import telebot
import datetime
import requests
import threading
import http.server
import socketserver
from lxml import etree

IP_PATH = "/config/ip.txt"
BOOK_PATH = "/config/book.txt"
CACHE_PATH = "/cache/cache.json"

PROXY_URL = os.environ.get("PROXY_URL")
TELEBOT_TOKEN = os.environ.get("TELEBOT_TOKEN")
TELEBOT_USER_ID = os.environ.get("TELEBOT_USER_ID")

if TELEBOT_TOKEN is None or TELEBOT_USER_ID is None or PROXY_URL is None:
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

        else:
            raise Exception("Proxy server not responding")

        return proxies

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(e))
        bot.send_message(TELEBOT_USER_ID, str(e))
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


def get_book_title(url, proxy=None):
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.8 Safari/537.36"
        }
        html = requests.get(
            url,
            headers=headers,
            proxies=proxy,
        )
        html.encoding = "gbk"
        tree = etree.HTML(html.text, parser=None)

        div_element = tree.xpath('//div[contains(@class, "qustime")]')[0]
        span_element = div_element.xpath("./ul/li[1]/a/span")[0]
        return span_element.text

    except Exception as e:
        if proxy is None:
            print("The following error occurred when using native ip")
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

            filtered_titles = {
                key: value
                for key, value in titles.items()
                if not key.endswith("previous")
            }
            response = json.dumps(filtered_titles)
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

    print(books)
    print(proxies)
    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Novel monitor started"
    )

    try:
        while True:
            for index in range(len(proxies)):
                j = (j + 1) % len(proxies)

                ip, port, username, password = proxies[j]
                proxy = {
                    "http": f"http://{username}:{password}@{ip}:{port}",
                    "https": f"http://{username}:{password}@{ip}:{port}",
                }

                try:
                    url = f"https://www.69shu.pro/book/{books[i][0]}.htm"
                    title = get_book_title(url, proxy)

                    if title != titles.get(books[i][1]):
                        if title == titles.get(books[i][1] + "previous"):
                            break

                        if title != get_book_title(url):
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
                    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(e))
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
            f"The exception occurred when processing book {books[i][1]} with error message: {str(e)}",
        )
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error occurred, program terminated",
        )
