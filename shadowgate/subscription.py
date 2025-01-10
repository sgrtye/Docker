import os
from xui import *
from fastapi.responses import FileResponse
from fastapi import Request, Response, HTTPException


def get_static_config(file_name: str) -> FileResponse | None:
    if os.path.exists(f"/conf/{file_name}"):
        return FileResponse(f"/conf/{file_name}")

    return None


def get_mitce_config(request: Request) -> FileResponse | None:
    user_agent = request.headers.get("user-agent", "Unknown")

    if "shadowrocket" in user_agent and os.path.exists(f"/conf/mitce/shadowrocket"):
        return FileResponse(
            "/conf/mitce/shadowrocket",
            media_type="application/octet-stream",
            filename="shadowrocket",
        )

    if "clash" in user_agent and os.path.exists(f"/conf/mitce/config.yaml"):
        user_info = ""
        if os.path.exists("/conf/mitce/userinfo.txt"):
            with open("/conf/mitce/userinfo.txt", "r") as file:
                user_info = file.read()

        return FileResponse(
            "/conf/mitce/config.yaml",
            media_type="application/x-yaml",
            filename="config.yaml",
            headers={"subscription-userinfo": user_info},
        )

    return None


async def get_config_file(request: Request, tail: str) -> Response:
    path_parts = tail.split("/")
    clients = await get_clients()

    for client in clients:
        if path_parts[0] != client["prefix"]:
            continue

        # Provide static files only for the main user
        if (
            client["name"] == "SGRTYE"
            and len(path_parts) == 2
            and (response := get_static_config(path_parts[1])) is not None
        ):
            return response

        # Return mitce config by default
        if (
            len(path_parts) == 4
            and path_parts[2] in ["yidong", "liantong", "dianxin"]
            and path_parts[3] == "config.yaml"
            and (response := get_mitce_config(request)) is not None
        ):
            return response

    raise HTTPException(status_code=404, detail="Not Found")


__ALL__ = ["get_config_file"]
