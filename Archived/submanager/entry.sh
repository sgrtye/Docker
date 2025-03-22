#!/bin/sh

python -u /app/update_nginx_config.py
python -u /app/remove_subscription.py
python -u /app/update_xui_config.py
python -u /app/update_monitor_config.py
python -u /app/update_mitce_config.py
/usr/sbin/crond -f -l 8