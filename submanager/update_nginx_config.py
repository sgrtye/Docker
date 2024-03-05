import os
import json
import random
import string
import requests
import datetime

DIRECTORY_PATH = "/sub"
NGINX_PATH = "/conf.d"

XUI_USERNAME = os.environ.get("XUI_USERNAME")
XUI_PASSWORD = os.environ.get("XUI_PASSWORD")

XUI_URL = os.environ.get("XUI_URL")
HOST_URL = os.environ.get("HOST_URL")

if XUI_URL is None or HOST_URL is None or XUI_USERNAME is None or XUI_PASSWORD is None:
    print("Environment variables not fulfilled")


def get_credentials():
    session = requests.Session()
    session.post(
        XUI_URL + "/login", data={"username": XUI_USERNAME, "password": XUI_PASSWORD}
    )
    response = session.post(XUI_URL + "/panel/inbound/list")

    if response.status_code != 200:
        return None

    results = []
    for inbound in response.json()["obj"]:
        uuid = json.loads(inbound["settings"])["clients"][0]["id"]
        client = {
            "name": inbound["remark"],
            "uuid": uuid,
            "host": "".join(
                random.choice(string.ascii_lowercase)
                for _ in range(random.randint(10, 15))
            )
            + "."
            + HOST_URL,
            "port": str(inbound["port"]),
            "path": json.loads(inbound["streamSettings"])["wsSettings"]["path"][1:],
        }
        results.append(client)

    return results


def update_nginx_config(credentials):
    with open(
        os.path.join(DIRECTORY_PATH, "file", "inbound.conf"), "r", encoding="utf-8"
    ) as file:
        inbound_template = file.read()

    inbound = ""
    for client in credentials:
        port, path = client["port"], client["path"]
        tmp = inbound_template.replace("PATH", path)
        tmp = tmp.replace("PORT", port)
        inbound = inbound + "\n\n" + tmp

    with open(
        os.path.join(DIRECTORY_PATH, "file", "nginx.conf"), "r", encoding="utf-8"
    ) as file:
        nginx_template = file.read()

    config = nginx_template.replace("INBOUNDS", inbound)
    with open(os.path.join(NGINX_PATH, "nginx.conf"), "w", encoding="utf-8") as file:
        file.write(config)

    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Successfully generated new NGINX config",
    )


def update():
    credentials = get_credentials()

    if credentials is None:
        raise Exception("No credentials available")

    update_nginx_config(credentials)


if __name__ == "__main__":
    update()
