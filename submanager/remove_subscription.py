import os
import shutil
import datetime

DIRECTORY_PATH = "/sub"


def remove_old_client_config():
    directory_path = os.path.join(DIRECTORY_PATH, "conf")
    if os.path.exists(directory_path):
        shutil.rmtree(directory_path)
        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Old client config files removed",
        )


if __name__ == "__main__":
    remove_old_client_config()
