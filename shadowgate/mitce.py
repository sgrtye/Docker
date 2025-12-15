import logging
import os

from httpx import AsyncClient, Response

from constants import (
    MITCE_CLASH_PATH,
    MITCE_CLASH_USERINFO_PATH,
    MITCE_SHADOWROCKET_PATH,
    MITCE_SING_BOX_PATH,
)

logger = logging.getLogger("my_app")


async def fetch_mitce_config(mitce_url: str, suffix: str) -> Response:
    async with AsyncClient() as client:
        return await client.get(f"{mitce_url}&app={suffix}")


def write_config_file(file_path: str, content: str) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)


async def update_shadowrocket_config(MITCE_URL: str) -> bool:
    shadowrocket_response = await fetch_mitce_config(MITCE_URL, "shadowrocket")

    if shadowrocket_response.status_code != 200:
        logger.error("Shadowrocket config failed to update")
        return False

    write_config_file(MITCE_SHADOWROCKET_PATH, shadowrocket_response.text)

    return True


async def update_clash_config(MITCE_URL: str) -> bool:
    clash_response = await fetch_mitce_config(MITCE_URL, "clashverge")

    if clash_response.status_code != 200:
        logger.error("Clash config failed to update")
        return False

    write_config_file(MITCE_CLASH_PATH, clash_response.text)
    write_config_file(
        MITCE_CLASH_USERINFO_PATH,
        clash_response.headers.get("subscription-userinfo", ""),
    )

    return True


async def update_sing_box_config(MITCE_URL: str) -> bool:
    sing_box_response = await fetch_mitce_config(MITCE_URL, "sb_111")

    if sing_box_response.status_code != 200:
        logger.error("Sing box config failed to update")
        return False

    write_config_file(MITCE_SING_BOX_PATH, sing_box_response.text)

    return True


async def update_mitce_config(MITCE_URL: str) -> None:
    try:
        # Get Clash config file
        shadowrocket_result = await update_shadowrocket_config(MITCE_URL)
        # Get Shadowrocket config string
        clash_result = await update_clash_config(MITCE_URL)
        # Get Sing-Box config file
        sing_box_result = await update_sing_box_config(MITCE_URL)

        if all((clash_result, shadowrocket_result, sing_box_result)):
            logger.info("New mitce config files fetched")

    except Exception:
        pass
