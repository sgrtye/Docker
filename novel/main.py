import os
import time
import json
import random
import asyncio
from collections import deque

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
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

BOOK_URL: str | None = os.getenv("BOOK_URL")
PROXY_URL: str | None = os.getenv("PROXY_URL")
TELEBOT_TOKEN: str | None = os.getenv("TELEBOT_TOKEN")
TELEBOT_USER_ID: str | None = os.getenv("TELEBOT_USER_ID")

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

titles: dict[str, deque[str]] = dict()
books: list[tuple[str, str]] = []
proxies: list[tuple[str, str, str, str]] = []

book_index: int = 0
proxy_index: int = 0
loop_index: int = 0
last_updated_time: float = time.time()


app = FastAPI()
NO_CACHE_HEADER = {
    "Content-Type": "application/json",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/health")
async def health_endpoint() -> JSONResponse:
    if (time_delta := time.time() - last_updated_time) < 1200:
        return JSONResponse(
            content={"message": f"<OK> {time_delta} seconds since the last update."},
            headers=NO_CACHE_HEADER,
        )
    else:
        return JSONResponse(
            content={
                "message": f"<Delayed> {time_delta} seconds since the last update."
            },
            status_code=500,
            headers=NO_CACHE_HEADER,
        )


@app.get("/update")
async def update_endpoint() -> JSONResponse:
    payload = {
        name: (
            titles[name][-1] if titles[name] else "Unknown",
            BOOK_URL.replace("BOOK_ID", id),
        )
        for id, name in books
    }
    return JSONResponse(content=payload, headers=NO_CACHE_HEADER)


async def send_to_telebot(message: str):
    url = f"https://api.telegram.org/bot{TELEBOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEBOT_USER_ID, "text": message}

    try:
        async with AsyncSession() as session:
            await session.post(url, json=payload)

    except Exception as e:
        logger.error(f"Error occurred when sending message to telegram: {repr(e)}")


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

    except Exception as e:
        logger.error(f"Loading proxies failed with {repr(e)}")
        await send_to_telebot(f"Loading proxies failed with {repr(e)}")
        return

    global proxies
    proxies = result

    logger.info(f"Found {len(proxies)} proxies")


def load_books() -> None:
    if not os.path.exists(BOOK_PATH):
        logger.critical("Loading books failed")
        raise SystemExit(0)

    try:
        result = []

        with open(BOOK_PATH, "r") as file:
            lines = file.readlines()

        for line in lines:
            if line.startswith("//"):
                continue

            number, name = line.strip().split(":")
            result.append((number, name))

    except Exception as e:
        logger.critical(f"Loading books failed with {repr(e)}")
        raise SystemExit(0)

    global books
    books = result

    logger.info(f"Found {len(books)} books")


def load_titles() -> None:
    if not os.path.exists(CACHE_PATH):
        logger.info(f"No cache found for titles")
        return

    try:
        result = {name: deque(maxlen=5) for _, name in books}

        with open(CACHE_PATH, "r") as file:
            cache = json.load(file)

        for k, v in cache.items():
            if k in result:
                result[k].extend(v)

    except Exception as e:
        logger.error(f"Loading titles failed with {repr(e)}")
        result = {name: deque(maxlen=5) for _, name in books}

    global titles
    titles = result

    logger.info(f"Cache loaded for titles")


async def get_url_html(url, proxy=None) -> str | None:
    try:
        async with AsyncSession() as session:
            response = await session.get(url, impersonate="chrome", proxies=proxy)

        response.encoding = "gbk"
        return response.text

    except Exception:
        if proxy is None:
            logger.error("Error occurred when using native ip")
            return None

        raise


def extract_book_title(html) -> str | None:
    if html is None:
        return None

    try:
        logger.debug(html[:100])
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


async def failed_fetch(e: Exception) -> None:
    global loop_index
    global proxy_index

    loop_index += 1
    proxy_index = (proxy_index + 1) % len(proxies)
    logger.debug(f"Failed to fetch for {books[book_index][BOOK_TITLE_INDEX]}")

    if loop_index == len(proxies):
        save_titles()
        await send_to_telebot(f"Novel monitor terminating from error {repr(e)}")
        logger.critical("Program terminated with all titles saved")
        raise e


async def update_book() -> None:
    try:
        logger.debug(f"Try to fetch updates for {books[book_index][BOOK_TITLE_INDEX]}")

        ip, port, username, password = proxies[proxy_index]
        proxy: dict[str, str] = {
            "http": f"http://{username}:{password}@{ip}:{port}",
            "https": f"http://{username}:{password}@{ip}:{port}",
        }

        url = BOOK_URL.replace("BOOK_ID", books[book_index][BOOK_ID_INDEX])
        html = await get_url_html(url, proxy)
        title = extract_book_title(html)

        if title not in titles[books[book_index][BOOK_TITLE_INDEX]]:
            verified_title = extract_book_title(await get_url_html(url))
            if verified_title is not None and title != verified_title:
                successful_fetch()
                return

            if titles[books[book_index][BOOK_TITLE_INDEX]]:
                await send_to_telebot(
                    f"{books[book_index][BOOK_TITLE_INDEX]}\n'{titles[books[book_index][BOOK_TITLE_INDEX]][-1]}'\n->'{title}'\n{url}",
                )

            titles[books[book_index][BOOK_TITLE_INDEX]].append(title)

        successful_fetch()

    except Exception as e:
        logger.error(
            f"Error {repr(e)} occurred when checking {books[book_index][BOOK_TITLE_INDEX]} with proxy {ip}:{port}"
        )
        logger.error(
            f"Error occurred during iteration {loop_index} on line {e.__traceback__.tb_lineno}"
        )
        await failed_fetch(e)


def save_titles() -> None:
    with open(CACHE_PATH, "w") as file:
        content = {k: list(v) for k, v in titles.items()}
        json.dump(content, file)


def handle_termination_signal() -> None:
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
                signal.SIGTERM, handle_termination_signal
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
