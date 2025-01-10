import os
import httpx
import datetime

MITCE_URL: str | None = os.environ.get("MITCE_URL")

if MITCE_URL is None:
    print("MITCE_URL not provided")
    raise SystemExit(0)


async def update_mitce_config():
    try:
        # Get Shadowrocket config string
        shadowrocket_response = await httpx.AsyncClient().get(
            MITCE_URL, headers={"User-agent": "shadowrocket"}
        )

        if shadowrocket_response.status_code != 200:
            print(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Shadowrocket config failed to update",
            )
            return

        os.makedirs(os.path.dirname("/conf/mitce/shadowrocket"), exist_ok=True)
        with open("/conf/mitce/shadowrocket", "w", encoding="utf-8") as file:
            file.write(shadowrocket_response.text)

        # Get Clash config file
        clash_response = await httpx.AsyncClient().get(
            MITCE_URL, headers={"User-agent": "clash"}
        )

        if clash_response.status_code != 200:
            print(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Clash config failed to update",
            )
            return

        os.makedirs(os.path.dirname("/conf/mitce/config.yaml"), exist_ok=True)
        with open("/conf/mitce/config.yaml", "w", encoding="utf-8") as file:
            file.write(clash_response.text)

        os.makedirs(os.path.dirname("/conf/mitce/userinfo.txt"), exist_ok=True)
        with open("/conf/mitce/userinfo.txt", "w", encoding="utf-8") as file:
            user_info = clash_response.headers.get("subscription-userinfo", "")
            file.write(user_info)

        print(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "New mitce config files fetched",
        )

    except Exception:
        pass


__ALL__ = ["update_mitce_config"]
