import logging
import os
from logging.handlers import TimedRotatingFileHandler

from fastapi import Request, Response
from fastapi.responses import FileResponse, JSONResponse

from constants import (
    CONFIG_ACCESS_LOG_PATH,
    MITCE_CLASH_PATH,
    MITCE_CLASH_USERINFO_PATH,
    MITCE_SHADOWROCKET_PATH,
    MITCE_SING_BOX_PATH,
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
    if os.path.exists(f"/conf/{client['name']}/{file_name}"):
        logger.info(f"{client['name']} accessed {file_name}")
        return FileResponse(f"/conf/{client['name']}/{file_name}")

    return None


def get_mitce_config(request: Request, client: dict[str, str]) -> FileResponse | None:
    user_agent = request.headers.get("user-agent", "Unknown").lower()
    ip_address = request.headers.get(
        "x-forwarded-for", request.client.host if request.client else "Unknown"
    )

    if "shadowrocket" in user_agent and os.path.exists(MITCE_SHADOWROCKET_PATH):
        logger.info(
            f"{client['name']} accessed config.yaml using Shadowrocket from {ip_address}"
        )

        return FileResponse(
            MITCE_SHADOWROCKET_PATH,
            media_type="application/octet-stream",
            filename="Mitce",
        )

    if "clash" in user_agent and os.path.exists(MITCE_CLASH_PATH):
        user_info: str = ""
        if os.path.exists(MITCE_CLASH_USERINFO_PATH):
            with open(MITCE_CLASH_USERINFO_PATH, "r") as file:
                user_info = file.read()

        logger.info(
            f"{client['name']} accessed config.yaml using Clash from {ip_address}"
        )

        return FileResponse(
            MITCE_CLASH_PATH,
            media_type="application/x-yaml",
            filename="config.yaml",
            headers={
                "profile-update-interval": "24",
                "subscription-userinfo": user_info,
                "content-disposition": "attachment; filename=Mitce.yaml",
            },
        )

    if "sing-box" in user_agent and os.path.exists(MITCE_SING_BOX_PATH):
        logger.info(
            f"{client['name']} accessed config.yaml using Sing-Box from {ip_address}"
        )

        return FileResponse(
            MITCE_SING_BOX_PATH,
            media_type="application/json",
            filename="Mitce",
        )

    logger.info(
        f"{client['name']} accessed config.yaml using unknown client ({user_agent}) from {ip_address}"
    )

    return None


def validate_config(
    request: Request, clients: list[dict[str, str]]
) -> FileResponse | None:
    query_params = dict(request.query_params)

    for client in clients:
        if (
            query_params.get("name") != client["name"]
            or query_params.get("uuid") != client["uuid"][:13]
        ):
            continue

        # Provide static files if exists in the named client's folder
        if (
            response := get_static_config(query_params.get("file", ""), client)
        ) is not None:
            return response

        # Return mitce config by default for config.yaml requests
        if (
            query_params.get("file") == "config.yaml"
            and query_params.get("location") is not None
            and query_params.get("provider") in ["yidong", "liantong", "dianxin"]
            and (response := get_mitce_config(request, client)) is not None
        ):
            return response

        return None


async def get_config_file(request: Request, tail: str) -> Response:
    clients = await get_clients()
    if (response := validate_config(request, clients)) is not None:
        return response

    return JSONResponse({"detail": "Not Found"}, status_code=404)
