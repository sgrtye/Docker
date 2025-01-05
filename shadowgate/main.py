import os
import aiohttp
from aiohttp import web
from functools import partial
from xui import *


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


async def forward_to_xui(request):
    target_url = f"{PROXY_URL}:{PROXY_PORT}{request.path_qs}"
    return await forward_request(request, target_url)


async def forward_to_proxy(request, port: str):
    target_url = f"{PROXY_URL}:{port}{request.path_qs}"
    return await forward_request(
        request, target_url, upgrade_connection=True, timeout=300
    )


async def forward_request(request, target_url, upgrade_connection=False, timeout=None):
    async with aiohttp.ClientSession() as session:
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in ["host", "connection", "upgrade"]
        }
        headers.update(
            {
                "Host": request.headers.get("Host", ""),
                "X-Real-IP": request.remote,
                "X-Forwarded-For": request.headers.get(
                    "X-Forwarded-For", request.remote
                ),
            }
        )
        if upgrade_connection:
            headers["Connection"] = "upgrade"
            headers["Upgrade"] = request.headers.get("Upgrade", "")

        try:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=await request.read(),
                timeout=timeout,
            ) as response:

                resp_headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() != "transfer-encoding"
                }
                body = await response.read()

                print(f"Response from {target_url}: {response.status}")
                print(f"Response headers: {resp_headers}")
                print(f"Response body: {body[:500]}")

                return web.Response(
                    status=response.status, headers=resp_headers, body=body
                )

        except Exception as e:
            print(f"Error while forwarding request to {target_url}: {e}")
            return web.Response(
                status=500, text=f"Error while forwarding request: {str(e)}"
            )


async def start_proxy(inbounds: list[dict[str, str]]):
    app = web.Application()
    app.router.add_route("*", PROXY_PATH + "{tail:.*}", forward_to_xui)

    for inbound in inbounds:
        app.router.add_route(
            "*",
            inbound["path"] + "{tail:.*}",
            partial(forward_to_proxy, port=inbound["port"]),
        )

    return app


if __name__ == "__main__":
    inbounds = get_inbounds(
        f"{PROXY_URL}:{PROXY_PORT}{PROXY_PATH}", XUI_USERNAME, XUI_PASSWORD
    )
    print(inbounds)
    web.run_app(start_proxy(inbounds), host="0.0.0.0", port=80)
