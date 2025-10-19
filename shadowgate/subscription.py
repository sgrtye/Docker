import logging
import os
from logging.handlers import TimedRotatingFileHandler

from fastapi import Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

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
    if os.path.exists(f"/conf/{client['name']}/{file_name}"):
        logger.info(f"{client['name']} accessed {file_name}")
        return FileResponse(f"/conf/{client['name']}/{file_name}")

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

        # Return mitce config by default
        if (
            query_params.get("provider") in ["yidong", "liantong", "dianxin"]
            and query_params.get("file") == "config.yaml"
            and (response := get_mitce_config(request, client)) is not None
        ):
            return response


def reconstruct_request(request: Request, tail: str) -> RedirectResponse | None:
    path_parts = tail.split("/")

    if len(path_parts) != 4 or len(path_parts[0].split("-")) != 3:
        return None

    new_parameters: dict[str, str] = {
        "name": path_parts[0].split("-")[0],
        "uuid": "-".join(path_parts[0].split("-")[1:]),
        "location": path_parts[1],
        "provider": path_parts[2],
        "file": path_parts[3],
    }

    query_params = dict(request.query_params) | new_parameters
    new_url = str(request.url.include_query_params(**query_params)).replace(tail, "")
    return RedirectResponse(url=new_url)


async def get_config_file(request: Request, tail: str) -> Response:
    if (response := reconstruct_request(request, tail)) is not None:
        return response

    clients = await get_clients()
    if (response := validate_config(request, clients)) is not None:
        return response

    return JSONResponse({"detail": "Not Found"}, status_code=404)
