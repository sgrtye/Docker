import json
import time
import requests

xui_session = requests.Session()
xui_rate_limit_time: float = time.time()


def xui_login(url: str, username: str, password: str) -> None:
    global xui_rate_limit_time

    if (sleep_time := 5 - (time.time() - xui_rate_limit_time)) > 0:
        time.sleep(sleep_time)
    xui_rate_limit_time = time.time()

    xui_session.post(
        url + "/login",
        data={"username": username, "password": password},
    )


def get_xui_info(url: str, path_suffix: str, username: str, password: str) -> dict:
    while (info := xui_session.post(url + path_suffix)).status_code != 200:
        xui_login(url, username, password)

    return info.json()


def get_inbounds(url: str, username: str, password: str) -> list[dict[str, str]]:
    response = get_xui_info(url, "/xui/inbound/list", username, password)

    results = []
    for inbound in response["obj"]:
        info = {
            "port": str(inbound["port"]),
            "path": json.loads(inbound["streamSettings"])["wsSettings"]["path"],
        }
        results.append(info)

    return results


__ALL__ = ["get_inbounds"]
