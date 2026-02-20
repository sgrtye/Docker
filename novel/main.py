import asyncio
import json
import logging
import os
import platform
import re
import signal
import time
import tomllib
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import AsyncClient
from selectolax.parser import HTMLParser
from uvicorn import Config, Server

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

scraper_key: str | None = os.getenv("SCRAPER_KEY")
telebot_token: str | None = os.getenv("TELEBOT_TOKEN")
telebot_user_id: str | None = os.getenv("TELEBOT_USER_ID")

if scraper_key is None or telebot_token is None or telebot_user_id is None:
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(1)
else:
    SCRAPER_KEY: str = scraper_key
    TELEBOT_TOKEN: str = telebot_token
    TELEBOT_USER_ID: str = telebot_user_id

BOOK_PATH: str = "/config/book.toml"
BOOK_CACHE_PATH: str = "/cache/book_cache.json"

TARGETING_SITE: str = "oop"
HEALTH_CHECK_TIMEOUT: int = 60 * 60 * 3  # 3 hours


@dataclass(frozen=True)
class Book:
    name: str
    url: str


scheduler = AsyncIOScheduler()

books: list[Book] = []
titles: dict[str, deque[tuple[str, str]]] = dict()  # {book: deque[title, date]}

book_index: int = 0
loop_index: int = 0
last_updated_time: float = time.time()


app = FastAPI()
NO_CACHE_HEADER: dict[str, str] = {
    "Content-Type": "application/json",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/health")
async def health_endpoint() -> JSONResponse:
    if (time_delta := time.time() - last_updated_time) < HEALTH_CHECK_TIMEOUT:
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
    payload: dict[str, tuple[str, str, str]] = {
        book.name: (
            titles[book.name][-1][0] if titles[book.name] else "Unknown",
            titles[book.name][-1][1]
            if titles[book.name]
            else datetime(2000, 1, 1).isoformat(),
            book.url,
        )
        for book in books
    }
    return JSONResponse(content=payload, headers=NO_CACHE_HEADER)


async def send_to_telebot(message: str) -> None:
    url: str = f"https://api.telegram.org/bot{TELEBOT_TOKEN}/sendMessage"
    payload: dict[str, str] = {"chat_id": TELEBOT_USER_ID, "text": message}

    try:
        async with AsyncClient() as client:
            await client.post(url, json=payload)

    except Exception as e:
        logger.error(f"Error occurred when sending message to telegram: {repr(e)}")


def load_books() -> None:
    if not os.path.exists(BOOK_PATH):
        logger.critical("Loading books failed")
        raise SystemExit(1)

    try:
        result: list[Book] = []

        with open(BOOK_PATH, "rb") as file:
            data = tomllib.load(file)
            for novel in data["novels"]:
                if not novel["monitored"]:
                    continue

                for site in novel["websites"]:
                    if site["name"] != TARGETING_SITE:
                        continue

                    result.append(Book(novel["name"], site["url"]))

    except Exception as e:
        logger.critical(f"Loading books failed with {repr(e)}")
        raise SystemExit(1)

    global books
    books = result

    logger.info(f"Found {len(books)} books")


def save_titles() -> None:
    with open(BOOK_CACHE_PATH, "w") as file:
        content: dict[str, list[list[str]]] = {
            k: list(map(list, v)) for k, v in titles.items()
        }
        json.dump(content, file)


def load_titles() -> None:
    result: dict[str, deque[tuple[str, str]]] = dict()

    if not os.path.exists(BOOK_CACHE_PATH):
        logger.info("No cache found for titles")

    else:
        logger.info("Loading cache for titles")

        try:
            with open(BOOK_CACHE_PATH, "r") as file:
                cache: dict[str, list[list[str]]] = json.load(file)

            for name, info_list in cache.items():
                if name in [book.name for book in books]:
                    result[name] = deque(
                        [(info[0], info[1]) for info in info_list], maxlen=5
                    )

        except Exception as e:
            logger.error(f"Loading titles failed with {repr(e)}")

    for book in books:
        if book.name not in result:
            result[book.name] = deque(maxlen=5)

    global titles
    titles = result


async def get_html_via_scrape_do(url: str) -> str:
    async with AsyncClient() as client:
        response = await client.get(
            f"http://api.scrape.do/?url={url}&token={SCRAPER_KEY}"
        )
        return response.text


def extract_book_title(html: str) -> str:
    tree = HTMLParser(html)
    a_node = tree.css_first("div.latest-chapter a")

    if a_node is not None:
        return a_node.text(strip=True)
    else:
        logger.error("The following error occurred when extracting book title")
        raise Exception("Failed to extract book title from HTML")


def successful_fetch() -> None:
    global loop_index
    global book_index
    global last_updated_time

    loop_index = 0
    book_index = (book_index + 1) % len(books)
    last_updated_time = time.time()

    logger.debug(f"Book fetched successfully for {books[book_index].name}")


async def failed_fetch(e: Exception) -> None:
    global loop_index

    loop_index += 1
    logger.debug(f"Failed to fetch for {books[book_index].name}")

    if loop_index == len(books):
        save_titles()
        await send_to_telebot(f"Novel monitor terminating from error {repr(e)}")
        logger.critical(f"Program terminating from error {repr(e)}")
        raise e


def get_first_number(string: str) -> int:
    match = re.search(r"\d+", string)
    return int(match.group(0)) if match else 0


async def update_book() -> None:
    try:
        book_name = books[book_index].name
        logger.debug(f"Try to fetch updates for {book_name}")

        url = books[book_index].url
        html = await get_html_via_scrape_do(url)
        title = extract_book_title(html)

        if title is None:
            raise Exception("Should never happen with a valid proxy")

        if not any(t == title for t, _ in titles[book_name]):
            if titles[book_name]:
                last_title = titles[book_name][-1][0]

                updated_count = get_first_number(title) - get_first_number(last_title)

                if not (1 <= updated_count <= 100):
                    updated_count = -1

                await send_to_telebot(
                    f"{book_name}\n本次更新{updated_count}章\n{last_title:.15}\n->{title:<.13}\n{url}",
                )

            titles[book_name].append((title, datetime.now().isoformat()))

        successful_fetch()

    except Exception as e:
        logger.error(f"Error {repr(e)} occurred when checking {book_name}")
        logger.error(
            f"Error occurred during iteration {loop_index} on line {e.__traceback__.tb_lineno if e.__traceback__ else '-1'}"
        )
        await failed_fetch(e)


async def start_api_server() -> None:
    config = Config(app=app, host="0.0.0.0", port=80, log_level="critical")
    await Server(config).serve()


def handle_termination_signal() -> None:
    save_titles()
    logger.info("Title saved before exiting")
    raise SystemExit(0)


def job_listener(event: JobExecutionEvent) -> None:
    if event.exception:
        logger.error(f"Job raised an exception: {event.exception}")
        asyncio.get_running_loop().stop()
        handle_termination_signal()
    else:
        logger.debug("Job executed successfully")


def schedule_refreshes() -> None:
    scheduler.add_job(
        save_titles,
        "cron",
        hour=10,
        minute=24,
    )

    scheduler.add_job(
        update_book,
        "cron",
        minute=12,
    )

    scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    scheduler.start()


async def main() -> None:
    load_books()
    load_titles()

    match platform.system():
        case "Linux":
            asyncio.get_running_loop().add_signal_handler(
                signal.SIGTERM, handle_termination_signal
            )
            logger.info("Signal handler for SIGTERM is registered.")

        case _:
            logger.info("Signal handler registration skipped.")
            pass

    schedule_refreshes()
    logger.info("Novel monitor started")

    await start_api_server()


if __name__ == "__main__":
    asyncio.run(main())
