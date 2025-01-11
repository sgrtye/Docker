import os
import json
import time
import httpx
import asyncio
import logging

logger = logging.getLogger("my_app")

PROXY_HOST: str | None = os.environ.get("PROXY_HOST")
PROXY_PORT: str | None = os.environ.get("PROXY_PORT")
PROXY_PATH: str | None = os.environ.get("PROXY_PATH")
XUI_USERNAME: str | None = os.environ.get("XUI_USERNAME")
XUI_PASSWORD: str | None = os.environ.get("XUI_PASSWORD")

if (
    PROXY_HOST is None
    or PROXY_PORT is None
    or PROXY_PATH is None
    or XUI_USERNAME is None
    or XUI_PASSWORD is None
):
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(0)

xui_session = httpx.AsyncClient()
xui_rate_limit_time: float = time.time()

XUI_URL: str = f"http://{PROXY_HOST}:{PROXY_PORT}{PROXY_PATH}"
CREDENTIAL: dict[str, str] = {"username": XUI_USERNAME, "password": XUI_PASSWORD}


async def xui_login() -> None:
    global xui_rate_limit_time
    # Rate limit to every 5 seconds
    if time.time() - xui_rate_limit_time < 5:
        await asyncio.sleep(1)
        return

    await xui_session.post(XUI_URL + "/login", data=CREDENTIAL)
    xui_rate_limit_time = time.time()


async def get_inbounds_json() -> dict:
    # Keep trying to get the info until it works
    while (
        info := await xui_session.post(XUI_URL + "/xui/inbound/list")
    ).status_code != 200:
        await xui_login()

    return info.json()


async def get_inbounds() -> list[dict[str, str]]:
    try:
        response = await get_inbounds_json()

        results = []
        for inbound in response["obj"]:
            info = {
                "port": str(inbound["port"]),
                "path": json.loads(inbound["streamSettings"])["wsSettings"]["path"],
            }
            results.append(info)

        return results

    except Exception:
        logger.critical("Failed to parse inbounds")
        return []


async def get_clients() -> list[dict[str, str]]:
    try:
        response = await get_inbounds_json()

        results = []
        for inbound in response["obj"]:
            for client in json.loads(inbound["settings"])["clients"]:
                info = {
                    "uuid": client["id"],
                    "name": client["email"],
                    "port": str(inbound["port"]),
                    "path": json.loads(inbound["streamSettings"])["wsSettings"]["path"],
                    "prefix": f"{client["email"]}-{client["id"][0:13]}",
                }
                results.append(info)

        return results

    except Exception:
        logger.error("Failed to parse clients")
        return []


__all__ = ["get_inbounds", "get_clients"]
