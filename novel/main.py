import asyncio
import heapq
import json
import logging
import os
import platform
import signal
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import AsyncClient
from lxml import etree
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

proxy_url: str | None = os.getenv("PROXY_URL")
scraper_url: str | None = os.getenv("SCRAPER_URL")
telebot_token: str | None = os.getenv("TELEBOT_TOKEN")
telebot_user_id: str | None = os.getenv("TELEBOT_USER_ID")

if (
    proxy_url is None
    or scraper_url is None
    or telebot_token is None
    or telebot_user_id is None
):
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(1)
else:
    PROXY_URL: str = proxy_url
    SCRAPER_URL: str = scraper_url
    TELEBOT_TOKEN: str = telebot_token
    TELEBOT_USER_ID: str = telebot_user_id

KEY_PATH: str = "/config/keys.txt"
BOOK_PATH: str = "/config/book.txt"
IP_MAPPING_PATH: str = "/cache/ip_cache.json"
BOOK_CACHE_PATH: str = "/cache/book_cache.json"

FETCH_EVENT_ID: str = "fetch_book_event"

SCRAPER_RETRY: int = 5
IP_RECORD_MAX_AGE: int = 60 * 60 * 24 * 7  # 7 days
HEALTH_CHECK_TIMEOUT: int = 60 * 40  # 40 minutes


@dataclass(frozen=True)
class Proxy:
    ip: str
    port: str
    username: str
    password: str


@dataclass(frozen=True)
class Book:
    name: str
    url: str


scheduler = AsyncIOScheduler()

books: list[Book] = []
mapping: list[tuple[str, Proxy]] = []  # [(key, proxy)]
titles: dict[str, deque[tuple[str, str]]] = dict()  # {book: deque[title, date]}

book_index: int = 0
loop_index: int = 0
mapping_index: int = 0
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


def load_scraper_api_keys() -> list[str]:
    if not os.path.exists(KEY_PATH):
        logger.critical("Failed to load scraper API keys")
        raise SystemExit(1)

    try:
        scraper_api_keys: list[str] = []

        with open(KEY_PATH, "r") as file:
            lines = file.readlines()

        for line in lines:
            if line.strip():
                scraper_api_keys.append(line.strip())

    except Exception as e:
        logger.critical(f"Loading scraper API keys failed with {repr(e)}")
        raise SystemExit(1)

    logger.info(f"Found {len(scraper_api_keys)} scraper API keys")

    return scraper_api_keys


async def load_proxies() -> list[Proxy]:
    try:
        result: list[Proxy] = []
        async with AsyncClient() as client:
            response = await client.get(PROXY_URL)

        if response.status_code != 200:
            raise Exception("Proxy server not responding")

        file_content = response.text
        ip_list = file_content.strip().split("\n")

        for ip_entry in ip_list:
            ip, port, username, password = ip_entry.rstrip("\r").split(":")
            result.append(Proxy(ip, port, username, password))

    except Exception as e:
        logger.error(f"Loading proxies failed with {repr(e)}")
        await send_to_telebot(f"Loading proxies failed with {repr(e)}")
        return []

    logger.info(f"Found {len(result)} proxies")

    return result


def load_books() -> None:
    if not os.path.exists(BOOK_PATH):
        logger.critical("Loading books failed")
        raise SystemExit(1)

    try:
        result: list[Book] = []

        with open(BOOK_PATH, "r") as file:
            lines = file.readlines()

        for line in lines:
            if line.startswith("//"):
                continue

            name, url = line.strip().split("@")
            result.append(Book(name, url))

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
    if not os.path.exists(BOOK_CACHE_PATH):
        logger.info("No cache found for titles")
        return

    try:
        result: dict[str, deque[tuple[str, str]]] = dict()

        with open(BOOK_CACHE_PATH, "r") as file:
            cache: dict[str, list[list[str]]] = json.load(file)

        for name, info_list in cache.items():
            if name in [book.name for book in books]:
                result[name] = deque(
                    [(info[0], info[1]) for info in info_list], maxlen=5
                )

        for book in books:
            if book.name not in result:
                result[book.name] = deque(maxlen=5)

    except Exception as e:
        logger.error(
            f"Loading titles failed with {repr(e)}, defaulting to empty title list"
        )
        result = {book.name: deque(maxlen=5) for book in books}

    global titles
    titles = result

    logger.info("Cache loaded for titles")


def clean_up_and_save_mapping_record(
    keys: list[str], mapping_record: dict[str, dict[str, str]]
) -> None:
    threshold: str = str(int(time.time()) - IP_RECORD_MAX_AGE)

    for key, ip_records in mapping_record.items():
        if key not in keys:
            del mapping_record[key]
            continue

        for ip, t in list(ip_records.items()):
            if t < threshold:
                del ip_records[ip]

    save_mapping_record(mapping_record)


def save_mapping_record(mapping_record: dict[str, dict[str, str]]) -> None:
    with open(IP_MAPPING_PATH, "w") as file:
        json.dump(mapping_record, file)


def load_mapping_record() -> dict[str, dict[str, str]]:
    if not os.path.exists(IP_MAPPING_PATH):
        logger.info("No cache found for IP mapping")
        return dict()

    try:
        result: dict[str, dict[str, str]] = dict()

        with open(IP_MAPPING_PATH, "r") as file:
            result = json.load(file)

    except Exception as e:
        logger.error(
            f"Loading IP mapping failed with {repr(e)}, defaulting to empty mapping"
        )
        result = dict()

    logger.info("Cache loaded for IP mapping")

    return result


async def refresh_mapping() -> None:
    try:
        keys = load_scraper_api_keys()
        proxies = await load_proxies()

        if not keys:
            logger.error("No scraper API keys found")
            return

        if not proxies:
            logger.error("No proxies found")
            return

        proxy_dict: dict[str, Proxy] = {proxy.ip: proxy for proxy in proxies}

        key_set: set[str] = set(keys)
        proxy_set: set[str] = set(proxy_dict.keys())
        mapping_history: list[tuple[int, tuple[str, str]]] = []

        mapping_record = load_mapping_record()
        for key, ip_records in mapping_record.items():
            if key not in key_set:
                continue

            for ip, timestamp in ip_records.items():
                if ip not in proxy_set:
                    continue

                heapq.heappush(mapping_history, (-int(timestamp), (key, ip)))

        global mapping
        mapping = []
        current_time: int = int(time.time())

        while key_set and proxy_set:
            if mapping_history:
                _, (key, ip) = heapq.heappop(mapping_history)
                if key in key_set and ip in proxy_set:
                    mapping.append((key, proxy_dict[ip]))
                    mapping_record.setdefault(key, {})[ip] = str(current_time)
                    key_set.remove(key)
                    proxy_set.remove(ip)
            else:
                key = key_set.pop()
                ip = proxy_set.pop()
                mapping.append((key, proxy_dict[ip]))
                mapping_record.setdefault(key, {})[ip] = str(current_time)

        clean_up_and_save_mapping_record(keys, mapping_record)

        if scheduler.get_job(FETCH_EVENT_ID):
            scheduler.remove_job(FETCH_EVENT_ID)

        scheduler.add_job(
            update_book,
            "interval",
            minutes=60 // len(mapping),
            id=FETCH_EVENT_ID,
            max_instances=1,
            coalesce=True,
        )

    except Exception as e:
        logger.error(f"Refreshing mapping failed with {repr(e)}")
        await send_to_telebot(f"Refreshing mapping failed with {repr(e)}")
        raise e

    logger.info(f"Set {len(mapping)} valid proxy mappings")


async def get_url_html(url, key: str, proxy: Proxy) -> str:
    for count in range(SCRAPER_RETRY):
        try:
            async with AsyncClient(
                proxy=f"http://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}"
            ) as client:
                payload: dict[str, str] = {"api_key": key, "url": url, "max_cost": "1"}
                response = await client.get(SCRAPER_URL, params=payload, timeout=120.0)

            match response.status_code:
                case 200:
                    return response.text
                case 403:
                    raise Exception("Reached credit limit")
                case 500:
                    raise Exception("Failed to fetch within 70s")
                case _:
                    raise Exception(
                        f"Unexpected status code {response.status_code} from scraper with message: {response.text}"
                    )

        except Exception:
            if count == SCRAPER_RETRY - 1:
                raise

    raise Exception("Wrong execution flow, should never reach here")


def extract_book_title(html: str) -> str:
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
    global mapping_index
    global last_updated_time

    loop_index = 0
    book_index = (book_index + 1) % len(books)
    mapping_index = (mapping_index + 1) % len(mapping)
    last_updated_time = time.time()

    logger.debug(f"Book fetched successfully for {books[book_index].name}")


async def failed_fetch(e: Exception) -> None:
    global loop_index
    global mapping_index

    loop_index += 1
    mapping_index = (mapping_index + 1) % len(mapping)
    logger.debug(f"Failed to fetch for {books[book_index].name}")

    if loop_index == len(mapping):
        save_titles()
        await send_to_telebot(f"Novel monitor terminating from error {repr(e)}")
        logger.critical(f"Program terminating from error {repr(e)}")
        raise e


async def update_book() -> None:
    try:
        book_name = books[book_index].name
        logger.debug(f"Try to fetch updates for {book_name}")

        url = books[book_index].url
        key, proxy = mapping[mapping_index]
        html = await get_url_html(url, key, proxy)
        title = extract_book_title(html)

        if title is None:
            raise Exception("Should never happen with a valid proxy")

        if not any(t == title for t, _ in titles[book_name]):
            if titles[book_name]:
                await send_to_telebot(
                    f"{book_name}\n'{titles[book_name][-1][0]}'\n->'{title}'\n{url}",
                )

            titles[book_name].append((title, datetime.now().isoformat()))

        successful_fetch()

    except Exception as e:
        logger.error(
            f"Error {repr(e)} occurred when checking {book_name} with proxy {proxy.ip} using key {key}"
        )
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
        refresh_mapping,
        "cron",
        hour=20,
        minute=48,
    )

    scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    scheduler.start()


async def main() -> None:
    load_books()
    load_titles()
    await refresh_mapping()

    if not mapping:
        logger.critical("No proxy available")
        raise SystemExit(1)

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
