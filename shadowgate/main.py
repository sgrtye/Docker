import os
import asyncio
import datetime
from xui import *
from functools import partial
from httpx import AsyncClient
from uvicorn import Config, Server
from fastapi import FastAPI, Request, Response
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler


PROXY_URL: str | None = os.environ.get("PROXY_URL")
PROXY_PORT: str | None = os.environ.get("PROXY_PORT")
PROXY_PATH: str | None = os.environ.get("PROXY_PATH")
HOST_DOMAIN: str | None = os.environ.get("HOST_DOMAIN")
XUI_USERNAME: str | None = os.environ.get("XUI_USERNAME")
XUI_PASSWORD: str | None = os.environ.get("XUI_PASSWORD")

if (
    PROXY_URL is None
    or PROXY_PORT is None
    or PROXY_PATH is None
    or HOST_DOMAIN is None
    or XUI_USERNAME is None
    or XUI_PASSWORD is None
):
    print("Environment variables not fulfilled")
    raise SystemExit(0)


REQUEST_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
app = FastAPI()
client = AsyncClient(timeout=300.0)


async def forward_to_dashboard(
    request: Request, tail: str, proxy_path: str
) -> Response:
    target_url = f"{PROXY_URL}:{PROXY_PORT}{proxy_path}{tail}"
    print(f"Request to {target_url} forwarded to dashboard")

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


async def forward_to_proxy(request: Request, tail: str, port: str) -> Response:
    target_url = f"{PROXY_URL}:{port}/{tail}"
    print(f"Request to {target_url} forwarded to proxy")
    return Response(content="Hello World", status_code=200)


def create_inbound_routes() -> None:
    inbounds = get_inbounds(
        f"{PROXY_URL}:{PROXY_PORT}{PROXY_PATH}", XUI_USERNAME, XUI_PASSWORD
    )

    for inbound in inbounds:
        app.add_api_route(
            path=f"{inbound['path']}/{{tail:path}}",
            endpoint=partial(forward_to_proxy, port=inbound["port"]),
            methods=REQUEST_METHODS,
        )


def add_api_routes() -> None:
    # Forward all requests to the proxy
    if not PROXY_PATH.startswith("/"):
        app.add_api_route(
            path=f"{{tail:path}}",
            endpoint=partial(forward_to_dashboard, proxy_path=""),
            methods=REQUEST_METHODS,
        )

        return

    # Create api routes to forward requests
    app.add_api_route(
        path=f"{PROXY_PATH}/{{tail:path}}",
        endpoint=partial(forward_to_dashboard, proxy_path=PROXY_PATH),
        methods=REQUEST_METHODS,
    )

    create_inbound_routes()


def update_config(num: int) -> None:
    pass


def schedule_config_updates() -> None:
    scheduler = AsyncIOScheduler()
    now = datetime.datetime.now()

    start_time = now.replace(minute=0, second=0, microsecond=0)
    scheduler.add_job(
        update_config,
        IntervalTrigger(hours=1, start_date=start_time),
        args=[0],
    )

    scheduler.start()


async def start_api_server() -> None:
    config = Config(app=app, host="0.0.0.0", port=8888, log_level="critical")
    await Server(config).serve()


async def main() -> None:
    add_api_routes()
    schedule_config_updates()

    print("Starting API server")
    await start_api_server()


if __name__ == "__main__":
    asyncio.run(main())
