import os
import json
import time
import shutil
import requests
import datetime
import schedule

DIRECTORY_PATH = "/sub"
NGINX_PATH = "/conf.d"

LOCATION_DICT = {
    "dalian": "大连",
    "foshan": "佛山",
    "tianjin": "天津",
    "jinghai": "静海",
    "beijing": "北京",
    "dongguan": "东莞",
    "tangshan": "唐山",
    "guangzhou": "广州",
}

USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")

HOST_URL = os.environ.get("HOST_URL")

LOGIN_URL = os.environ.get("LOGIN_URL")
INBOUND_URL = os.environ.get("INBOUND_URL")

if (
    USERNAME is None
    or PASSWORD is None
    or LOGIN_URL is None
    or INBOUND_URL is None
    or HOST_URL is None
):
    print("Environment variables not fulfilled")


def get_credentials():
    session = requests.Session()
    session.post(LOGIN_URL, data={"username": USERNAME, "password": PASSWORD})
    response = session.post(INBOUND_URL)

    if response.status_code != 200:
        return None

    results = []
    for inbound in response.json()["obj"]:
        uuid = json.loads(inbound["settings"])["clients"][0]["id"]
        client = {
            "name": inbound["remark"],
            "uuid": uuid,
            "host": uuid[0:5] + "." + HOST_URL,
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


def generate_check_config(locations, uuid, host, path, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    config_content = "proxies:"

    for loc, loc_value in locations.items():
        for key, value in loc_value.items():
            config_content = (
                config_content + "\n" + '    -   {"name":"'
                f"{LOCATION_DICT.get(loc, loc) + key[0:2] + key[4:5]}"
                + '","type":"vless","server":"'
                + f"{value}"
                + '","port":443,"uuid":"UUID_FULL","tls":true,"servername":"HOST_ADDRESS","network":"ws","ws-opts":{"path":"/CLIENT_PATH","headers":{"host":"HOST_ADDRESS"}},"client-fingerprint":"chrome"}'
            )

    config_content = config_content.replace("UUID_FULL", uuid)
    config_content = config_content.replace("CLIENT_PATH", path)
    config_content = config_content.replace("HOST_ADDRESS", host)

    with open(save_path, "w", encoding="utf-8") as file:
        file.write(config_content)


def update_client_config(locations, providers, credentials):
    directory_path = os.path.join(DIRECTORY_PATH, "conf")
    if os.path.exists(directory_path):
        shutil.rmtree(directory_path)
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Old client config files removed",
        )

    for client in credentials:
        name, uuid, host, path = (
            client["name"],
            client["uuid"],
            client["host"],
            client["path"],
        )

        servers = {
            key: value
            for provider in providers.values()
            for key, value in provider.items()
        }
        config_path = os.path.join(DIRECTORY_PATH, "file", "unruled.yaml")
        save_path = os.path.join(
            DIRECTORY_PATH, "conf", rf"{name}-{path}/china/config.yaml"
        )
        generate_config(servers, uuid, host, path, config_path, save_path)

        save_path = os.path.join(
            DIRECTORY_PATH, "conf", rf"{name}-{path}/check/config.yaml"
        )
        generate_check_config(locations, uuid, host, path, save_path)

        for loc, loc_value in locations.items():
            for pro, pro_value in providers.items():
                servers = {
                    **{
                        f"实时节点{index + 1}_IP": value
                        for index, value in enumerate(pro_value.values())
                    },
                    **loc_value,
                }
                config_path = os.path.join(DIRECTORY_PATH, "file", "ruled.yaml")
                save_path = os.path.join(
                    DIRECTORY_PATH, "conf", rf"{name}-{path}/{loc}/{pro}/config.yaml"
                )
                generate_config(servers, uuid, host, path, config_path, save_path)

    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "New client config files generaged",
    )


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
        "Successfully generaged new NGINX config",
    )


def update(nginx=False):
    try:
        locations = get_location_ip()
        providers = get_provider_ip()

        if providers is None:
            raise Exception("No provider data available")

        credentials = get_credentials()

        if credentials is None:
            raise Exception("No credentials available")

        if nginx:
            update_nginx_config(credentials)

        update_client_config(locations, providers, credentials)

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(e))
        print(f"Error occured on line {e.__traceback__.tb_lineno}")


if __name__ == "__main__":
    update(nginx=True)

    schedule.every().day.at("00:00").do(update)
    schedule.every().day.at("06:00").do(update)
    schedule.every().day.at("12:00").do(update)
    schedule.every().day.at("18:00").do(update)

    while True:
        schedule.run_pending()
        time.sleep(10)
