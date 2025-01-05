import os
import uvicorn
from xui import *
from functools import partial
from httpx import AsyncClient
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, Response


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
    raise SystemExit


app = FastAPI()


async def forward_request(
    request: Request,
    target_url: str,
    upgrade_connection: bool = False,
    timeout: int = None,
):
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ["host", "connection", "upgrade"]
    }
    headers.update(
        {
            "Host": request.headers.get("Host", ""),
            "X-Real-IP": request.client.host,
            "X-Forwarded-For": request.headers.get(
                "X-Forwarded-For", request.client.host
            ),
        }
    )
    if upgrade_connection:
        headers["Connection"] = "upgrade"
        headers["Upgrade"] = request.headers.get("Upgrade", "")

    try:
        async with AsyncClient(timeout=timeout) as client:
            body = await request.body()
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

            resp_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() != "transfer-encoding"
            }

            print(f"Response from {target_url}: {response.status_code}")
            print(f"Response headers: {resp_headers}")
            print(f"Response body: {response.text[:500]}")

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=resp_headers,
            )

    except Exception as e:
        print(f"Error while forwarding request to {target_url}: {e}")
        return JSONResponse(
            content={"error": f"Error while forwarding request: {str(e)}"},
            status_code=500,
        )


@app.api_route(
    f"{PROXY_PATH}/{{tail:path}}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
async def forward_to_xui(request: Request, tail: str):
    target_url = f"{PROXY_URL}:{PROXY_PORT}/{tail}"
    return await forward_request(request, target_url)


async def forward_to_proxy(request: Request, tail: str, port: str):
    target_url = f"{PROXY_URL}:{port}/{tail}"
    return await forward_request(
        request, target_url, upgrade_connection=True, timeout=300
    )


def create_inbound_routes(inbounds):
    for inbound in inbounds:
        app.add_api_route(
            path=f"{inbound['path']}/{{tail:path}}",
            endpoint=partial(forward_to_proxy, port=inbound["port"]),
            methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )


if __name__ == "__main__":
    inbounds = get_inbounds(
        f"{PROXY_URL}:{PROXY_PORT}{PROXY_PATH}", XUI_USERNAME, XUI_PASSWORD
    )
    print(f"Loaded inbounds: {inbounds}")

    create_inbound_routes(inbounds)

    uvicorn.run(app, host="0.0.0.0", port=80)
