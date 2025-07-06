import asyncio
import logging
import os
from functools import partial

import websockets
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.staticfiles import StaticFiles
from httpx import AsyncClient
from uvicorn import Config, Server

from mitce import update_mitce_config
from subscription import get_config_file
from xui import get_inbounds, set_credentials

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

mitce_url: str | None = os.getenv("MITCE_URL")
proxy_host: str | None = os.getenv("PROXY_HOST")
proxy_port: str | None = os.getenv("PROXY_PORT")
proxy_path: str | None = os.getenv("PROXY_PATH")
host_domain: str | None = os.getenv("HOST_DOMAIN")
xui_username: str | None = os.getenv("XUI_USERNAME")
xui_password: str | None = os.getenv("XUI_PASSWORD")

if (
    mitce_url is None
    or proxy_host is None
    or proxy_port is None
    or proxy_path is None
    or host_domain is None
    or xui_username is None
    or xui_password is None
):
    logger.critical("Environment variables not fulfilled")
    raise SystemExit(1)
else:
    MITCE_URL: str = mitce_url
    PROXY_HOST: str = proxy_host
    PROXY_PORT: str = proxy_port
    PROXY_PATH: str = proxy_path
    HOST_DOMAIN: str = host_domain
    XUI_USERNAME: str = xui_username
    XUI_PASSWORD: str = xui_password

REQUEST_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
app = FastAPI()
client = AsyncClient()


def check_for_host_domain(request: Request) -> None:
    if request.headers.get("host") != HOST_DOMAIN:
        raise HTTPException(status_code=404, detail="Not Found")


async def forward_to_dashboard(
    request: Request, tail: str, proxy_path: str
) -> Response:
    target_url: str = f"http://{PROXY_HOST}:{PROXY_PORT}{proxy_path}/{tail}"

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
    target_url: str = f"ws://{PROXY_HOST}:{port}{path}"

    await websocket.accept()

    try:
        async with websockets.connect(target_url) as backend_ws:

            async def receive_messages(websocket: WebSocket):
                while True:
                    yield await websocket.receive()

            async def client_to_backend() -> None:
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

            async def backend_to_client() -> None:
                try:
                    async for message in backend_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        elif isinstance(message, str):
                            await websocket.send_text(message)
                        else:
                            await websocket.send_text(bytes(message).decode("utf-8"))

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
    # Forward all requests to the proxy (Used for setting up new dashboard)
    if not PROXY_PATH.startswith("/"):
        app.add_api_route(
            path="/{tail:path}",
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

        # Config files
        app.add_api_route(
            path="/conf/{tail:path}",
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
        partial(update_mitce_config, MITCE_URL),
        "cron",
        hour="0,8,16",
        minute="24",
    )

    scheduler.start()


async def start_api_server() -> None:
    config = Config(app=app, host="0.0.0.0", port=80, log_level="critical")
    await Server(config).serve()


async def main() -> None:
    set_credentials(
        PROXY_HOST,
        PROXY_PORT,
        PROXY_PATH,
        XUI_USERNAME,
        XUI_PASSWORD,
    )

    await add_api_routes()
    schedule_config_updates()

    logger.info("Starting API server")
    await start_api_server()


if __name__ == "__main__":
    asyncio.run(main())
