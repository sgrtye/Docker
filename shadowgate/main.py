import logging

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

import os
import asyncio
from functools import partial

import websockets
from httpx import AsyncClient
from uvicorn import Config, Server
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request, Response, Depends, WebSocket, HTTPException

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from xui import *
from mitce import *
from subscription import *

PROXY_HOST: str | None = os.getenv("PROXY_HOST")
PROXY_PORT: str | None = os.getenv("PROXY_PORT")
PROXY_PATH: str | None = os.getenv("PROXY_PATH")
HOST_DOMAIN: str | None = os.getenv("HOST_DOMAIN")
XUI_USERNAME: str | None = os.getenv("XUI_USERNAME")
XUI_PASSWORD: str | None = os.getenv("XUI_PASSWORD")

if HOST_DOMAIN is None:
    logger.critical("HOST_DOMAIN not provided")
    raise SystemExit(0)

REQUEST_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
app = FastAPI()
client = AsyncClient()


def check_for_host_domain(request: Request) -> None:
    if request.headers.get("host") != HOST_DOMAIN:
        raise HTTPException(status_code=404, detail="Not Found")


async def forward_to_dashboard(
    request: Request, tail: str, proxy_path: str
) -> Response:
    target_url = f"http://{PROXY_HOST}:{PROXY_PORT}{proxy_path}/{tail}"

    forwarded_request = client.build_request(
        method=request.method,
        url=target_url,
        headers=dict(request.headers),
        content=await request.body(),
        params=request.query_params,
    )

    forwarded_response = await client.send(forwarded_request)

    response_content = await forwarded_response.aread()
    response_headers = dict(forwarded_response.headers)
    response_headers.pop("content-length", None)
    response_headers.pop("content-encoding", None)

    return Response(
        content=response_content,
        status_code=forwarded_response.status_code,
        headers=response_headers,
    )


async def forward_to_proxy(websocket: WebSocket, port: str, path: str) -> None:
    target_url = f"ws://{PROXY_HOST}:{port}{path}"

    await websocket.accept()

    try:
        async with websockets.connect(target_url) as backend_ws:

            async def receive_messages(websocket: WebSocket):
                while True:
                    yield await websocket.receive()

            async def client_to_backend():
                try:
                    async for message in receive_messages(websocket):
                        if "text" in message:
                            await backend_ws.send(message["text"])
                        elif "bytes" in message:
                            await backend_ws.send(message["bytes"])
                        else:
                            raise Exception("Unknown message")

                except Exception:
                    raise

            async def backend_to_client():
                try:
                    async for message in backend_ws:
                        await websocket.send_text(message)

                except Exception:
                    raise

            await asyncio.gather(client_to_backend(), backend_to_client())

    except Exception:
        await websocket.close(code=1001)


async def get_config(request: Request, tail: str) -> Response:
    return await get_config_file(request, tail)


async def create_inbound_routes() -> None:
    inbounds = await get_inbounds()

    for inbound in inbounds:
        app.router.add_websocket_route(
            f"{inbound['path']}",
            partial(forward_to_proxy, port=inbound["port"], path=inbound["path"]),
        )


async def add_api_routes() -> None:
    # Forward all requests to the proxy
    if not PROXY_PATH.startswith("/"):
        app.add_api_route(
            path=f"/{{tail:path}}",
            endpoint=partial(forward_to_dashboard, proxy_path=""),
            methods=REQUEST_METHODS,
        )

    # Create api routes dynamically for all paths
    else:
        # Dashboard
        app.add_api_route(
            path=f"{PROXY_PATH}/{{tail:path}}",
            endpoint=partial(forward_to_dashboard, proxy_path=PROXY_PATH),
            dependencies=[Depends(check_for_host_domain)],
            methods=REQUEST_METHODS,
        )

        #  Config files
        app.add_api_route(
            path=f"/conf/{{tail:path}}",
            endpoint=get_config,
            dependencies=[Depends(check_for_host_domain)],
        )

        # Proxy connections
        await create_inbound_routes()

        # Static HTML page
        app.mount(
            "/",
            StaticFiles(directory="/website", html=True),
        )


def schedule_config_updates() -> None:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        update_mitce_config,
        "cron",
        hour="0,8,16",
        minute="24",
    )

    scheduler.start()


async def start_api_server() -> None:
    config = Config(app=app, host="0.0.0.0", port=80, log_level="critical")
    await Server(config).serve()


async def main() -> None:
    await add_api_routes()
    schedule_config_updates()

    logger.info("Starting API server")
    await start_api_server()


if __name__ == "__main__":
    asyncio.run(main())
