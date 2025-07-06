import logging
import os

import httpx

from constants import (
    MITCE_CLASH_PATH,
    MITCE_CLASH_USERINFO_PATH,
    MITCE_SHADOWROCKET_PATH,
)

logger = logging.getLogger("my_app")


async def update_clash_config(MITCE_URL: str) -> bool:
    clash_response = await httpx.AsyncClient().get(
        MITCE_URL, headers={"User-agent": "clash"}
    )

    if clash_response.status_code != 200:
        logger.error("Clash config failed to update")
        return False

    os.makedirs(os.path.dirname(MITCE_CLASH_PATH), exist_ok=True)
    with open(MITCE_CLASH_PATH, "w", encoding="utf-8") as file:
        file.write(clash_response.text)

    os.makedirs(os.path.dirname(MITCE_CLASH_USERINFO_PATH), exist_ok=True)
    with open(MITCE_CLASH_USERINFO_PATH, "w", encoding="utf-8") as file:
        user_info = clash_response.headers.get("subscription-userinfo", "")
        file.write(user_info)

    return True


async def update_shadowrocket_config(MITCE_URL: str) -> bool:
    shadowrocket_response = await httpx.AsyncClient().get(
        MITCE_URL, headers={"User-agent": "shadowrocket"}
    )

    if shadowrocket_response.status_code != 200:
        logger.error("Shadowrocket config failed to update")
        return False

    os.makedirs(os.path.dirname(MITCE_SHADOWROCKET_PATH), exist_ok=True)
    with open(MITCE_SHADOWROCKET_PATH, "w", encoding="utf-8") as file:
        file.write(shadowrocket_response.text)

    return True


async def update_mitce_config(MITCE_URL: str) -> None:
    try:
        # Get Shadowrocket config string
        clash_result = await update_clash_config(MITCE_URL)
        # Get Clash config file
        shadowrocket_result = await update_shadowrocket_config(MITCE_URL)

        if all((clash_result, shadowrocket_result)):
            logger.info("New mitce config files fetched")

    except Exception:
        pass
