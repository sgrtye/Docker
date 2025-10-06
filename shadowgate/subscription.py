import logging
import os
from logging.handlers import TimedRotatingFileHandler

from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse

from constants import (
    CONFIG_ACCESS_LOG_PATH,
    MITCE_CLASH_PATH,
    MITCE_CLASH_USERINFO_PATH,
    MITCE_SHADOWROCKET_PATH,
)
from sui import get_clients

logger = logging.getLogger("config_access")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler(CONFIG_ACCESS_LOG_PATH, when="W0", backupCount=2)
formatter = logging.Formatter("%(asctime)s - %(message)s", "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False


def get_static_config(file_name: str, client: dict[str, str]) -> FileResponse | None:
    if os.path.exists(f"/conf/{file_name}"):
        logger.info(f"{client['name']} accessed {file_name}")
        return FileResponse(f"/conf/{file_name}")

    return None


def get_mitce_config(request: Request, client: dict[str, str]) -> FileResponse | None:
    user_agent = request.headers.get("user-agent", "Unknown").lower()

    if "shadowrocket" in user_agent and os.path.exists(MITCE_SHADOWROCKET_PATH):
        logger.info(f"{client['name']} accessed config.yaml using Shadowrocket")
        return FileResponse(
            MITCE_SHADOWROCKET_PATH,
            media_type="application/octet-stream",
            filename="shadowrocket",
        )

    if "clash" in user_agent and os.path.exists(MITCE_CLASH_PATH):
        user_info: str = ""
        if os.path.exists(MITCE_CLASH_USERINFO_PATH):
            with open(MITCE_CLASH_USERINFO_PATH, "r") as file:
                user_info = file.read()

        logger.info(f"{client['name']} accessed config.yaml using Clash")
        return FileResponse(
            MITCE_CLASH_PATH,
            media_type="application/x-yaml",
            filename="config.yaml",
            headers={"subscription-userinfo": user_info},
        )

    return None


async def get_config_file(request: Request, tail: str) -> Response:
    path_parts = tail.split("/")
    clients = await get_clients()
    user_agent = request.headers.get("user-agent", "Unknown").lower()

    if any(agent in user_agent for agent in ["shadowrocket", "clash"]):
        for client in clients:
            if path_parts[0] != f"{client['name']}-{client['uuid'][0:13]}":
                continue

            # Provide static files only for the main user
            if (
                client["name"] == "SGRTYE"
                and (response := get_static_config("/".join(path_parts[1:]), client))
                is not None
            ):
                return response

            # Return mitce config by default
            if (
                len(path_parts) == 4
                and path_parts[2] in ["yidong", "liantong", "dianxin"]
                and path_parts[3] == "config.yaml"
                and (response := get_mitce_config(request, client)) is not None
            ):
                return response

    raise HTTPException(status_code=404, detail="Not Found")
