import os
import json
import random
import string
import requests
from config import DIRECTORY_PATH

XUI_URL = os.environ.get("XUI_URL")
HOST_DOMAIN = os.environ.get("HOST_DOMAIN")
XUI_USERNAME = os.environ.get("XUI_USERNAME")
XUI_PASSWORD = os.environ.get("XUI_PASSWORD")

if (
    XUI_URL is None
    or HOST_DOMAIN is None
    or XUI_USERNAME is None
    or XUI_PASSWORD is None
):
    print("Environment variables not fulfilled")
    raise SystemExit


def get_credentials():
    session = requests.Session()
    session.post(
        XUI_URL + "/login", data={"username": XUI_USERNAME, "password": XUI_PASSWORD}
    )
    response = session.post(XUI_URL + "/xui/inbound/list")

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


def read_txt_file(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()

    content_dict = {}
    for line in lines:
        key, value = line.strip().split(":")
        content_dict[key.strip()] = value.strip()

    return content_dict


def get_provider_ip():
    headers = headers = {"Content-Type": "application/json"}
    data = {"key": "o1zrmHAF", "type": "v4"}

    response = requests.post(
        "https://api.hostmonit.com/get_optimization_ip", json=data, headers=headers
    )
    if response.status_code != 200:
        raise Exception("No provider information available")

    data = response.json()

    providers = {}
    providers["yidong"] = {
        f"移动节点{index + 1}_IP": value
        for index, value in enumerate([entry["ip"] for entry in data["info"]["CM"]])
    }
    providers["liantong"] = {
        f"联通节点{index + 1}_IP": value
        for index, value in enumerate([entry["ip"] for entry in data["info"]["CU"]])
    }
    providers["dianxin"] = {
        f"电信节点{index + 1}_IP": value
        for index, value in enumerate([entry["ip"] for entry in data["info"]["CT"]])
    }

    return providers


def get_selected_ip():
    response = requests.get("https://ip.164746.xyz/ipTop.html")

    if response.status_code != 200:
        return None

    selected_ips = response.text.split(",")
    ips = {
        "优选节点4_IP": selected_ips[0],
        "优选节点5_IP": selected_ips[1],
    }
    return ips


def get_location_ip():
    locations = {}

    for filename in os.listdir(os.path.join(DIRECTORY_PATH, "file")):
        if filename.endswith(".txt"):
            file_path = os.path.join(DIRECTORY_PATH, "file", filename)
            file_name = os.path.splitext(filename)[0]
            content = read_txt_file(file_path)
            locations[file_name] = content

    return locations
