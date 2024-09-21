import os
import json
import random
import string
import requests

XUI_URL = os.environ.get("XUI_URL")
HOST_DOMAIN = os.environ.get("HOST_DOMAIN")
XUI_USERNAME = os.environ.get("XUI_USERNAME")
XUI_PASSWORD = os.environ.get("XUI_PASSWORD")

if XUI_URL is None or HOST_DOMAIN is None or XUI_USERNAME is None or XUI_PASSWORD is None:
    raise Exception("Environment variables not fulfilled")


def get_credentials():
    session = requests.Session()
    session.post(
        XUI_URL + "/login", data={"username": XUI_USERNAME, "password": XUI_PASSWORD}
    )
    response = session.post(XUI_URL + "/panel/inbound/list")

    if response.status_code != 200:
        raise Exception("No credentials available")

    results = []
    for inbound in response.json()["obj"]:
        remark = inbound["remark"]
        for client in json.loads(inbound["settings"])["clients"]:
            host = (
                "".join(
                    random.choice(string.ascii_lowercase)
                    for _ in range(random.randint(5, 10))
                )
                + "."
                + HOST_DOMAIN
            )

            info = {
                "host": host,
                "remark": remark,
                "uuid": client["id"],
                "name": client["email"],
                "port": str(inbound["port"]),
                "path": json.loads(inbound["streamSettings"])["wsSettings"]["path"][1:],
            }
            results.append(info)

    return results
