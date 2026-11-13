MITCE_SHADOWROCKET_PATH: str = "/conf/mitce/shadowrocket"
MITCE_CLASH_PATH: str = "/conf/mitce/clash.yaml"
MITCE_CLASH_USERINFO_PATH: str = "/conf/mitce/userinfo.txt"
MITCE_SING_BOX_PATH: str = "/conf/mitce/singbox.json"

CONFIG_ACCESS_LOG_PATH: str = "/logs/config_access.log"

USER_AGENT: dict[str, str] = {
    "shadowrocket": "Shadowrocket/3488 CFNetwork/3896.200.61 Darwin/27.2.0 iPhone17,1",
    "clashverge": "clash-verge/v2.5.10",
    "sb_114": "SFI (sing-box 1.14.4; language en_US)"
}