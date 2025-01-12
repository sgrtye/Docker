import os
import time
import json
import random
import telebot
import asyncio

import signal
import platform

from lxml import etree
from curl_cffi.requests import AsyncSession

from fastapi import FastAPI
from uvicorn import Config, Server
from fastapi.responses import JSONResponse

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import logging

logger = logging.getLogger("my_app")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

BOOK_URL: str | None = os.environ.get("BOOK_URL")
PROXY_URL: str | None = os.environ.get("PROXY_URL")
TELEBOT_TOKEN: str | None = os.environ.get("TELEBOT_TOKEN")
TELEBOT_USER_ID: str | None = os.environ.get("TELEBOT_USER_ID")

if (
    TELEBOT_TOKEN is None
    or TELEBOT_USER_ID is None
    or BOOK_URL is None
    or PROXY_URL is None
):
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(0)

IP_PATH: str = "/config/ip.txt"
BOOK_PATH: str = "/config/book.txt"
CACHE_PATH: str = "/cache/cache.json"

BOOK_ID_INDEX = 0
BOOK_TITLE_INDEX = 1

bot = telebot.TeleBot(TELEBOT_TOKEN)
last_updated_time: float = time.time()

titles: dict[str, str] = dict()
books: list[tuple[str, str]] = []
proxies: list[tuple[str, str, str, str]] = []

book_index: int = 0
proxy_index: int = 0
loop_index: int = 0


app = FastAPI()
NO_CACHE_HEADER = {
    "Content-Type": "application/json",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/health")
async def health_endpoint() -> JSONResponse:
    if time.time() - last_updated_time < 1200:
        return JSONResponse(content={"message": "OK"}, headers=NO_CACHE_HEADER)
    else:
        return JSONResponse(
            content={"message": "DELAYED"},
            status_code=500,
            headers=NO_CACHE_HEADER,
        )


@app.get("/update")
async def update_endpoint() -> JSONResponse:
    payload = {
        name: (titles.get(name, "Unknown"), BOOK_URL.replace("BOOK_ID", id))
        for id, name in books
    }
    return JSONResponse(content=payload, headers=NO_CACHE_HEADER)


def load_unavailable_ips() -> list[str]:
    if not os.path.exists(IP_PATH):
        return []

    unavailable_ips = []

    with open(IP_PATH, "r") as file:
        lines = file.readlines()

    for line in lines:
        unavailable_ips.append(line.strip())

    return unavailable_ips


async def load_proxies() -> None:
    try:
        result = []
        async with AsyncSession() as session:
            response = await session.get(PROXY_URL)

        if response.status_code != 200:
            raise Exception("Proxy server not responding")

        file_content = response.text
        ip_list = file_content.strip().split("\n")

        for ip_entry in ip_list:
            ip, port, username, password = ip_entry.rstrip("\r").split(":")
            if ip not in load_unavailable_ips():
                result.append((ip, port, username, password))

        random.shuffle(result)

        global proxies
        proxies = result

    except Exception as e:
        logger.error(f"When loading proxies: {repr(e)}")
        bot.send_message(TELEBOT_USER_ID, f"When loading proxies: {repr(e)}")


def load_books() -> None:
    if not os.path.exists(BOOK_PATH):
        logger.critical("Loading books failed")
        raise SystemExit(0)

    result = []

    with open(BOOK_PATH, "r") as file:
        lines = file.readlines()

    for line in lines:
        if line.startswith("//"):
            continue

        number, name = line.strip().split(":")
        result.append((number, name))

    global books
    books = result


def load_titles() -> None:
    if not os.path.exists(CACHE_PATH):
        return

    result = dict()

    with open(CACHE_PATH, "r") as file:
        result = json.load(file)
        book_name = set(name for _, name in books)
        book_name_previous = set(name + "previous" for _, name in books)
        dict_copy = result.copy()

        for book in dict_copy.keys():
            if book not in book_name and book not in book_name_previous:
                del result[book]

    global titles
    titles = result


async def get_url_html(url, proxy=None) -> str | None:
    try:
        async with AsyncSession() as session:
            response = await session.get(url, impersonate="chrome", proxies=proxy)

        response.encoding = "gbk"
        return response.text

    except Exception:
        if proxy is None:
            logger.error("The following error occurred when using native ip")
            return None

        raise


def extract_book_title(html) -> str | None:
    if html is None:
        return None

    try:
        tree = etree.HTML(html, parser=None)
        div_element = tree.xpath('//div[contains(@class, "qustime")]')[0]
        span_element = div_element.xpath("./ul/li[1]/a/span")[0]
        return span_element.text

    except Exception:
        logger.error("The following error occurred when extracting book title")
        raise


def successful_fetch() -> None:
    global loop_index
    global book_index
    global proxy_index
    global last_updated_time

    loop_index = 0
    book_index = (book_index + 1) % len(books)
    proxy_index = (proxy_index + 1) % len(proxies)
    last_updated_time = time.time()

    logger.debug(f"Book fetched successfully for {books[book_index][BOOK_TITLE_INDEX]}")


def failed_fetch(e: Exception) -> None:
    global loop_index
    global proxy_index

    loop_index += 1
    proxy_index = (proxy_index + 1) % len(proxies)
    logger.debug(f"Failed to fetch for {books[book_index][BOOK_TITLE_INDEX]}")

    if loop_index == len(proxies):
        save_titles()
        bot.send_message(
            TELEBOT_USER_ID, f"Novel monitor terminating from error {repr(e)}"
        )
        logging.critical("Program terminated with all titles saved")
        raise SystemExit(0)


async def update_book() -> None:
    logger.debug(f"Try to fetch updates for {books[book_index][BOOK_TITLE_INDEX]}")
    ip, port, username, password = proxies[proxy_index]
    proxy: dict[str, str] = {
        "http": f"http://{username}:{password}@{ip}:{port}",
        "https": f"http://{username}:{password}@{ip}:{port}",
    }

    try:
        url = BOOK_URL.replace("BOOK_ID", books[book_index][BOOK_ID_INDEX])
        html = await get_url_html(url, proxy)
        title = extract_book_title(html)

        if title != titles.get(books[book_index][BOOK_TITLE_INDEX]):
            if title == titles.get(books[book_index][BOOK_TITLE_INDEX] + "previous"):
                successful_fetch()
                return

            verified_title = extract_book_title(await get_url_html(url))
            if verified_title is not None and title != verified_title:
                successful_fetch()
                return

            if titles.get(books[book_index][BOOK_TITLE_INDEX]) is not None:
                bot.send_message(
                    TELEBOT_USER_ID,
                    f"{books[book_index][BOOK_TITLE_INDEX]}\n'{titles.get(books[book_index][BOOK_TITLE_INDEX])}'\n->'{title}'\n{url}",
                )

            titles[books[book_index][BOOK_TITLE_INDEX] + "previous"] = titles.get(
                books[book_index][BOOK_TITLE_INDEX]
            )
            titles[books[book_index][BOOK_TITLE_INDEX]] = title
            successful_fetch()

    except Exception as e:
        logger.error(
            f"Error occurred when checking {books[book_index][BOOK_TITLE_INDEX]} with proxy {ip}:{port}"
        )
        logger.error(
            f"Error occurred during iteration {loop_index} on line {e.__traceback__.tb_lineno}"
        )
        failed_fetch(e)


def save_titles() -> None:
    with open(CACHE_PATH, "w") as file:
        json.dump(titles, file)


def handle_sigterm(signum, frame) -> None:
    save_titles()
    logger.info("Title saved before exiting")
    raise SystemExit(0)


async def start_api_server() -> None:
    config = Config(app=app, host="0.0.0.0", port=80, log_level="critical")
    await Server(config).serve()


def schedule_tasks() -> None:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        update_book,
        "interval",
        minutes=60 // len(proxies),
    )

    scheduler.add_job(
        save_titles,
        "cron",
        hour=10,
        minute=24,
    )

    scheduler.add_job(
        load_proxies,
        "cron",
        hour=20,
        minute=48,
    )

    scheduler.start()


async def main() -> None:
    load_books()
    load_titles()
    await load_proxies()

    if not proxies:
        logger.critical("No proxy available")
        raise SystemExit(0)

    match platform.system():
        case "Linux":
            asyncio.get_running_loop().add_signal_handler(
                signal.SIGTERM, handle_sigterm
            )
            logger.info("Signal handler for SIGTERM is registered.")

        case _:
            logger.info("Signal handler registration skipped.")
            pass

    schedule_tasks()
    logger.info("Novel monitor started")

    await start_api_server()


if __name__ == "__main__":
    asyncio.run(main())
