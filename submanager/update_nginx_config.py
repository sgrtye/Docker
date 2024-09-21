import os
import datetime
from xui_credentials import get_credentials

DIRECTORY_PATH = "/sub"
NGINX_PATH = "/conf.d"


def update_nginx_config(credentials):
    with open(
        os.path.join(DIRECTORY_PATH, "file", "nginx.conf"), "r", encoding="utf-8"
    ) as file:
        config = file.read()

    for client in credentials:
        port, path, remark = client["port"], client["path"], client["remark"]
        config = config.replace(f"{remark}_PORT", port)
        config = config.replace(f"{remark}_PATH", path)

    with open(os.path.join(NGINX_PATH, "nginx.conf"), "w", encoding="utf-8") as file:
        file.write(config)

    print(
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Successfully generated new NGINX config",
    )


def update():
    try:
        credentials = get_credentials()
        update_nginx_config(credentials)

    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), repr(e))
        print(f"Error occurred on line {e.__traceback__.tb_lineno}")


if __name__ == "__main__":
    update()
