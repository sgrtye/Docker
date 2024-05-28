import os
import shutil
import requests
import datetime

DIRECTORY_PATH = "/sub"

XUI_URL = os.environ.get("XUI_URL")
XUI_USERNAME = os.environ.get("XUI_USERNAME")
XUI_PASSWORD = os.environ.get("XUI_PASSWORD")


if XUI_URL is None is None or XUI_USERNAME is None or XUI_PASSWORD is None:
    print("Environment variables not fulfilled")


def check_credentials():
    session = requests.Session()
    session.post(
        XUI_URL + "/login", data={"username": XUI_USERNAME, "password": XUI_PASSWORD}
    )
    response = session.post(XUI_URL + "/panel/inbound/list")

    if response.status_code != 200:
        raise Exception("No credentials available")


def remove_old_client_config():
    try:
        check_credentials()

        directory_path = os.path.join(DIRECTORY_PATH, "conf")
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
            print(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Old client config files removed",
            )
    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e))
        print(f"Error occurred on line {e.__traceback__.tb_lineno}")


if __name__ == "__main__":
    remove_old_client_config()
