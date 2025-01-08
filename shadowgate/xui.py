import json
import time
import httpx


def get_inbounds_json(url: str, username: str, password: str) -> dict:
    with httpx.Client() as session:
        # Keep trying to get the info until it works
        while (info := session.post(url + "/xui/inbound/list")).status_code != 200:
            time.sleep(5)
            session.post(
                url + "/login",
                data={"username": username, "password": password},
            )

    return info.json()


def get_inbounds(url: str, username: str, password: str) -> list[dict[str, str]]:
    try:
        response = get_inbounds_json(url, username, password)

        results = []
        for inbound in response["obj"]:
            info = {
                "port": str(inbound["port"]),
                "path": json.loads(inbound["streamSettings"])["wsSettings"]["path"],
            }
            results.append(info)

        print(f"Loaded inbounds: {results}")
        return results

    except Exception:
        print("Failed to parse inbounds")
        return []


__ALL__ = ["get_inbounds"]
