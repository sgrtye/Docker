import os
import httpx
import logging

from constants import *

MITCE_URL: str | None = os.environ.get("MITCE_URL")


async def update_mitce_config():
    if MITCE_URL is None:
        logging.error("MITCE_URL not provided")
        return

    try:
        # Get Shadowrocket config string
        shadowrocket_response = await httpx.AsyncClient().get(
            MITCE_URL, headers={"User-agent": "shadowrocket"}
        )

        if shadowrocket_response.status_code != 200:
            logging.error("Shadowrocket config failed to update")
            return

        os.makedirs(os.path.dirname(MITCE_SHADOWROCKET_PATH), exist_ok=True)
        with open(MITCE_SHADOWROCKET_PATH, "w", encoding="utf-8") as file:
            file.write(shadowrocket_response.text)

        # Get Clash config file
        clash_response = await httpx.AsyncClient().get(
            MITCE_URL, headers={"User-agent": "clash"}
        )

        if clash_response.status_code != 200:
            logging.error("Clash config failed to update")
            return

        os.makedirs(os.path.dirname(MITCE_CLASH_PATH), exist_ok=True)
        with open(MITCE_CLASH_PATH, "w", encoding="utf-8") as file:
            file.write(clash_response.text)

        os.makedirs(os.path.dirname(MITCE_CLASH_USERINFO_PATH), exist_ok=True)
        with open(MITCE_CLASH_USERINFO_PATH, "w", encoding="utf-8") as file:
            user_info = clash_response.headers.get("subscription-userinfo", "")
            file.write(user_info)

        logging.info("New mitce config files fetched")

    except Exception:
        pass


__ALL__ = ["update_mitce_config"]
