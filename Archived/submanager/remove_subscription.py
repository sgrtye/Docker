import os
import shutil
import datetime
from config import DIRECTORY_PATH
from utilities import get_credentials


def remove_old_client_config():
    try:
        credentials = get_credentials()

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
