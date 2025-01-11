import time
import asyncio
from functools import partial
from httpx import AsyncClient
from uvicorn import Config, Server
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request, Response, Depends, WebSocket, HTTPException


REQUEST_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
app = FastAPI()
client = AsyncClient()
last_updated_time: float = time.time()

NO_CACHE_HEADER = {
    "Content-Type": "application/json",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/health")
async def health_endpoint():
    if time.time() - last_updated_time <= 5:
        return JSONResponse(content={"message": "OK"}, headers=NO_CACHE_HEADER)
    else:
        return JSONResponse(
            content={"message": "ERROR"},
            status_code=500,
            headers=NO_CACHE_HEADER,
        )


def depends_checker(request: Request) -> None:
    if request.headers.get("host") != "":
        raise HTTPException(status_code=404, detail="Not Found")


async def http_route(request: Request, tail: str, arg: str) -> Response:
    forwarded_request = client.build_request(
        method=request.method,
        url="example.com",
        headers=dict(request.headers),
        content=await request.body(),
        params=request.query_params,
    )

    forwarded_response = await client.send(forwarded_request)

    return Response(
        content=await forwarded_response.aread(),
        status_code=forwarded_response.status_code,
        headers=dict(forwarded_response.headers),
    )


async def websocket_route(websocket: WebSocket, tail: str, arg: str) -> Response:
    await websocket.accept()
    await asyncio.sleep(5)
    await websocket.close(code=1001)


def add_api_routes() -> None:
    app.add_api_route(
        path=f"/http/{{tail:path}}",
        endpoint=partial(http_route, arg="arg1"),
        dependencies=[Depends(depends_checker)],
        methods=REQUEST_METHODS,
    )

    app.router.add_websocket_route(
        path=f"/ws/{{tail:path}}",
        endpoint=partial(websocket_route, arg="arg1"),
    )

    app.mount(
        "/",
        StaticFiles(directory="/website", html=True),
    )


async def start_api_server() -> None:
    config = Config(app=app, host="0.0.0.0", port=80, log_level="critical")
    await Server(config).serve()


async def main() -> None:
    add_api_routes()

    await start_api_server()


if __name__ == "__main__":
    asyncio.run(main())
