import os
import datetime
from submanager.config import LOCATION_DICT, DIRECTORY_PATH
from submanager.utilities import get_credentials, get_provider_ip, get_location_ip


def generate_ip_config_line(name, server_ip):
    line = (
        '\n  - {"name":"'
        + f"{name}"
        + '","type":"vless","server":"'
        + f"{server_ip}"
        + '","port":443,"uuid":"UUID_FULL","tls":true,"servername":"HOST_ADDRESS","network":"ws","ws-opts":{"path":"/CLIENT_PATH","headers":{"host":"HOST_ADDRESS"}},"client-fingerprint":"chrome"}'
    )
    return line


def generate_hostname_config_line(name):
    line = (
        '\n  - {"name":"'
        + f"{name}"
        + '","type":"vless","server":"HOST_ADDRESS","port":443,"uuid":"UUID_FULL","tls":true,"network":"ws","ws-opts":{"path":"/CLIENT_PATH"},"client-fingerprint":"chrome"}'
    )
    return line


def generate_monitor_config(locations, providers, uuid, host, path, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    config_content = "proxies:"

    for loc, loc_value in locations.items():
        for name, server_ip in loc_value.items():
            name = LOCATION_DICT.get(loc, loc) + name[0:2] + name[4:5]
            config_content = config_content + generate_ip_config_line(name, server_ip)

    for pro, pro_value in providers.items():
        for name, server_ip in pro_value.items():
            config_content = config_content + generate_ip_config_line(
                name[0:5], server_ip
            )

    config_content = config_content + generate_hostname_config_line("Beelink")

    config_content = config_content.replace("UUID_FULL", uuid)
    config_content = config_content.replace("CLIENT_PATH", path)
    config_content = config_content.replace("HOST_ADDRESS", host)

    with open(save_path, "w", encoding="utf-8") as file:
        file.write(config_content)


def update_config(locations, providers, credentials):
    for client in credentials:
        name, uuid, host, path = (
            client["name"],
            client["uuid"],
            client["host"],
            client["path"],
        )

        save_path = os.path.join(
            DIRECTORY_PATH, "conf", rf"{name}-{uuid[0:13]}/china/clash.yaml"
        )
        generate_monitor_config(locations, providers, uuid, host, path, save_path)

    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "New client config files generated",
    )


def update():
    try:
        locations = get_location_ip()
        providers = get_provider_ip()
        credentials = get_credentials()
        update_config(locations, providers, credentials)

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e))
        print(f"Error occurred on line {e.__traceback__.tb_lineno}")


if __name__ == "__main__":
    update()
