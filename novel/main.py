import os
import time
import json
import telebot
import requests
import datetime
import threading
import http.server
import socketserver
from lxml import etree

CACHE_PATH = "/novel/cache.json"

TELEBOT_TOKEN = os.environ.get("TELEBOT_TOKEN")
TELEBOT_USER_ID = os.environ.get("TELEBOT_USER_ID")
PROXY_URL = os.environ.get("PROXY_URL")

if TELEBOT_TOKEN is None or TELEBOT_USER_ID is None or PROXY_URL is None:
    print("Environment variables not fulfilled")

bot = telebot.TeleBot(TELEBOT_TOKEN)

checkedTime = time.time()


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override the log_message method to do nothing
        pass

    def do_GET(self):
        if self.path == "/update":
            global titles

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
        elif self.path == "/status":
            global checkedTime
            global loopTime

            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            if time.time() - checkedTime < loopTime:
                self.wfile.write(b"OK")
            else:
                self.wfile.write(b"Failed")
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def start_health_server():
    with socketserver.TCPServer(("0.0.0.0", 8008), HealthCheckHandler) as httpd:
        httpd.serve_forever()


health_thread = threading.Thread(target=start_health_server)
health_thread.daemon = True
health_thread.start()

proxies = []

try:
    response = requests.get(PROXY_URL)

    if response.status_code == 200:
        file_content = response.text
        ip_list = file_content.strip().split("\n")

        for ip_entry in ip_list:
            ip, port, username, password = ip_entry.rstrip("\r").split(":")
            if ip != "154.95.36.199":
                proxies.append((ip, port, username, password))

        if len(proxies) == 0:
            raise Exception("No available proxy")

    else:
        raise Exception("Proxy server not responding")

except Exception as e:
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(e))
    bot.send_message(TELEBOT_USER_ID, str(e))
    raise SystemExit

print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Novel monitor started")

books = [
    ("46527", "乱世书"),
    ("35463", "稳住别浪"),
    ("50012", "还说你不是仙人"),
    ("49986", "都重生了谁谈恋爱啊"),
    ("43660", "这一世，我再也不渣青梅竹马了"),
    ("50565", "我满级天师，你让我进规则怪谈？"),
]
i = 0
j = 0
loopTime = len(books) * 5 * 60
sleepInterval = loopTime / len(books)

titles = dict()
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r") as file:
        titles = json.load(file)
        booknames = set(name for _, name in books)
        booknames_previous = set(name + "previous" for _, name in books)
        dict_copy = titles.copy()
        for book in dict_copy.keys():
            if book not in booknames and book not in booknames_previous:
                del titles[book]

headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.8 Safari/537.36"
}

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
                url = f"https://www.69shuba.com/book/{books[i][0]}.htm"
                html = requests.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                )
                html.encoding = "gbk"
                tree = etree.HTML(html.text, parser=None)

                div_element = tree.xpath('//div[contains(@class, "qustime")]')[0]
                span_element = div_element.xpath("./ul/li[1]/a/span")[0]
                title = span_element.text

                if title != titles.get(books[i][1]):
                    if title == titles.get(books[i][1] + "previous"):
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
                    f"Error occured when checking {books[i][1]} with proxy {ip}:{port}"
                )
                print(
                    f"Error occured during iteration {index} on line {e.__traceback__.tb_lineno}"
                )
                time.sleep(sleepInterval)
                if index == len(proxies) - 1:
                    raise e

        checkedTime = time.time()
        time.sleep(sleepInterval)
        i = (i + 1) % len(books)

except Exception as e:
    bot.send_message(TELEBOT_USER_ID, "Novel monitor encountered unexpected exception")
    bot.send_message(
        TELEBOT_USER_ID,
        f"The exception occured when processing book {books[i][1]} with error message: {str(e)}",
    )
    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Error occured, program terminated",
    )
