import logging

import httpx

logger = logging.getLogger("my_app")


sui_session = httpx.AsyncClient()

SUI_URL: str = ""
SUI_TOKEN: str = ""


def set_credentials(
    sui_token: str,
    proxy_host: str,
    proxy_port: str,
    proxy_path: str,
) -> None:
    global SUI_URL, SUI_TOKEN

    SUI_TOKEN = sui_token
    SUI_URL = f"http://{proxy_host}:{proxy_port}{proxy_path}"


async def get_load_json() -> dict:
    response = await httpx.AsyncClient().get(
        f"{SUI_URL}/apiv2/load", headers={"token": SUI_TOKEN}
    )
    return response.json()


async def get_inbounds_json(ids: list[int]) -> dict:
    response = await httpx.AsyncClient().get(
        f"{SUI_URL}/apiv2/inbounds?id={','.join(map(str, ids))}",
        headers={"token": SUI_TOKEN},
    )
    return response.json()


async def get_clients_json(ids: list[int]) -> dict:
    response = await httpx.AsyncClient().get(
        f"{SUI_URL}/apiv2/clients?id={','.join(map(str, ids))}",
        headers={"token": SUI_TOKEN},
    )
    return response.json()


async def get_vless_inbounds() -> list[dict[str, str]]:
    try:
        load_response = await get_load_json()

        id_list: list[int] = [
            client["id"] for client in load_response.get("obj", {}).get("inbounds", [])
        ]
        inbounds_response = await get_inbounds_json(id_list)

        results: list[dict[str, str]] = []
        for inbound in inbounds_response.get("obj", {}).get("inbounds", []):
            # Add inbounds with valid vless config
            try:
                assert inbound["tag"] == "VLESS"

                info: dict[str, str] = {
                    "port": str(inbound["listen_port"]),
                    "path": inbound["transport"]["path"],
                }
                results.append(info)
            except Exception:
                logger.warning("Failed to parse an inbound, skipping")
                continue

        return results

    except Exception:
        logger.critical("Failed to parse inbounds")
        return []


async def get_clients() -> list[dict[str, str]]:
    try:
        load_response = await get_load_json()

        id_list: list[int] = [
            client["id"] for client in load_response.get("obj", {}).get("clients", [])
        ]
        clients_response = await get_clients_json(id_list)

        results: list[dict[str, str]] = []
        for client in clients_response.get("obj", {}).get("clients", []):
            # Add clients with valid vless config
            try:
                assert "vless" in client["config"]

                info: dict[str, str] = {
                    "name": client["config"]["vless"]["name"],
                    "uuid": client["config"]["vless"]["uuid"],
                }
                results.append(info)
            except Exception:
                logger.warning("Failed to parse a client, skipping")
                continue

        return results

    except Exception:
        logger.error("Failed to parse clients")
        return []
