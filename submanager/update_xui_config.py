import os
import datetime
from submanager.config import AGENTS, DIRECTORY_PATH
from submanager.utilities import (
    get_credentials,
    get_provider_ip,
    get_location_ip,
    get_selected_ip,
)


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


def update_config(locations, providers, credentials):
    for client in credentials:
        name, uuid, host, path = (
            client["name"],
            client["uuid"],
            client["host"],
            client["path"],
        )

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
                    DIRECTORY_PATH,
                    "conf",
                    rf"{name}-{uuid[0:13]}/{loc}/{pro}/clash.yaml",
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
        credentials = get_credentials()
        update_config(locations, providers, credentials)

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e))
        print(f"Error occurred on line {e.__traceback__.tb_lineno}")


if __name__ == "__main__":
    update()
