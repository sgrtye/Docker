import os
import requests
import datetime
from utilities import get_credentials
from config import AGENTS, DIRECTORY_PATH

MITCE_URL = os.environ.get("MITCE_URL")

if MITCE_URL is None:
    raise Exception("Environment variables not fulfilled")


def update_mitce_config(credentials):
    for user_agent, file_name in AGENTS:
        config_file = requests.get(MITCE_URL, headers={"User-agent": user_agent})

        if config_file.status_code != 200:
            raise Exception(f"Mitce file fetch error with agent {user_agent}")

        global_save_path = os.path.join(DIRECTORY_PATH, r"conf/mitce", file_name)
        os.makedirs(os.path.dirname(global_save_path), exist_ok=True)
        with open(global_save_path, "w", encoding="utf-8") as file:
            file.write(config_file.text)

        for client in credentials:
            name = client["name"]
            uuid = client["uuid"]

            save_path = os.path.join(
                DIRECTORY_PATH, "conf", rf"{name}-{uuid[0:13]}", file_name
            )

            if os.path.exists(save_path):
                os.remove(save_path)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            os.link(global_save_path, save_path)

    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "New mitce config files fetched",
    )


def update():
    try:
        credentials = get_credentials()
        update_mitce_config(credentials)

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e))
        print(f"Error occurred on line {e.__traceback__.tb_lineno}")


if __name__ == "__main__":
    update()
