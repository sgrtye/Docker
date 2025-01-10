import os
from xui import *
from fastapi.responses import FileResponse
from fastapi import Request, Response, HTTPException


async def get_config_file(request: Request, tail: str) -> Response:
    path_parts = tail.split("/")
    clients = await get_clients()

    try:
        for client in clients:
            if path_parts[0] != client["prefix"]:
                continue

            # Other subscription usage
            if client["name"] == "SGRTYE":
                try:
                    return FileResponse(f"/conf/{path_parts[-1]}")
                except Exception:
                    pass

            if path_parts[2] not in ["yidong", "liantong", "dianxin"]:
                continue

            # Default usage, currently using mitce subscription
            if path_parts[3] == "config.yaml":
                continue

            user_agent = request.headers.get("user-agent", "Unknown")
            if "shadowrocket" in user_agent:
                return FileResponse(
                    "/conf/mitce/shadowrocket",
                    media_type="application/octet-stream",
                    filename="shadowrocket",
                )

            if "clash" in user_agent:
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

    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Not Found")


__ALL__ = ["get_config_file"]
