import os
import json
import random
import string
import requests
import datetime

DIRECTORY_PATH = "/sub"

LOCATION_DICT = {
    "dalian": "大连",
    "foshan": "佛山",
    "default": "默认",
    "tianjin": "天津",
    "jinghai": "静海",
    "beijing": "北京",
    "dongguan": "东莞",
    "tangshan": "唐山",
    "guangzhou": "广州",
    "shijiazhuang": "石家庄",
}

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


def get_provider_ip():
    headers = headers = {"Content-Type": "application/json"}
    data = {"key": "o1zrmHAF", "type": "v4"}

    response = requests.post(
        "https://api.hostmonit.com/get_optimization_ip", json=data, headers=headers
    )
    if response.status_code != 200:
        return None

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


def read_txt_file(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()

    content_dict = {}
    for line in lines:
        key, value = line.strip().split(":")
        content_dict[key.strip()] = value.strip()

    return content_dict


def get_location_ip():
    locations = {}

    for filename in os.listdir(os.path.join(DIRECTORY_PATH, "file")):
        if filename.endswith(".txt"):
            file_path = os.path.join(DIRECTORY_PATH, "file", filename)
            file_name = os.path.splitext(filename)[0]
            content = read_txt_file(file_path)
            locations[file_name] = content

    return locations


def generate_config_line(name, server_ip):
    line = (
        "\n"
        + '  - {"name":"'
        + f"{name}"
        + '","type":"vless","server":"'
        + f"{server_ip}"
        + '","port":443,"uuid":"UUID_FULL","tls":true,"servername":"HOST_ADDRESS","network":"ws","ws-opts":{"path":"/CLIENT_PATH","headers":{"host":"HOST_ADDRESS"}},"client-fingerprint":"chrome"}'
    )
    return line


def generate_config(servers, uuid, host, path, config_path, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    with open(config_path, "r", encoding="utf-8") as file:
        config_content = file.read()

    for key, value in servers.items():
        config_content = config_content.replace(key, value)
    config_content = config_content.replace("UUID_FULL", uuid)
    config_content = config_content.replace("CLIENT_PATH", path)
    config_content = config_content.replace("HOST_ADDRESS", host)

    with open(save_path, "w", encoding="utf-8") as file:
        file.write(config_content)


def generate_check_config(locations, providers, uuid, host, path, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    config_content = "proxies:"

    for loc, loc_value in locations.items():
        for name, server_ip in loc_value.items():
            name = LOCATION_DICT.get(loc, loc) + name[0:2] + name[4:5]
            config_content = config_content + generate_config_line(name, server_ip)

    for pro, pro_value in providers.items():
        for name, server_ip in pro_value.items():
            config_content = config_content + generate_config_line(name[0:5], server_ip)

    config_content = config_content.replace("UUID_FULL", uuid)
    config_content = config_content.replace("CLIENT_PATH", path)
    config_content = config_content.replace("HOST_ADDRESS", host)

    with open(save_path, "w", encoding="utf-8") as file:
        file.write(config_content)


def update_client_config(locations, providers, credentials):
    for client in credentials:
        name, uuid, host, path = (
            client["name"],
            client["uuid"],
            client["host"],
            client["path"],
        )

        save_path = os.path.join(
            DIRECTORY_PATH, "conf", rf"{name}-{path}/china/config.yaml"
        )
        generate_check_config(locations, providers, uuid, host, path, save_path)

        selected_ips = get_selected_ip()

        if selected_ips is None:
            print("No selected ip available")
        else:
            for key, value in locations.items():
                value.update(selected_ips)

        for loc, loc_value in locations.items():
            for pro, pro_value in providers.items():
                servers = {
                    **{
                        f"实时节点{index + 1}_IP": value
                        for index, value in enumerate(pro_value.values())
                    },
                    **loc_value,
                }
                config_path = os.path.join(DIRECTORY_PATH, "file", "config.yaml")
                save_path = os.path.join(
                    DIRECTORY_PATH, "conf", rf"{name}-{path}/{loc}/{pro}/config.yaml"
                )
                generate_config(servers, uuid, host, path, config_path, save_path)

    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "New client config files generated",
    )


def update():
    try:
        locations = get_location_ip()
        providers = get_provider_ip()

        if providers is None:
            raise Exception("No provider data available")

        credentials = get_credentials()

        if credentials is None:
            raise Exception("No credentials available")

        update_client_config(locations, providers, credentials)

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(e))
        print(f"Error occurred on line {e.__traceback__.tb_lineno}")


if __name__ == "__main__":
    update()
