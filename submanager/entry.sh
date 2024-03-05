#!/bin/sh

# start cron
python -u /app/update_nginx_config.py
python -u /app/remove_subscription.py
python -u /app/update_subscription.py
/usr/sbin/crond -f -l 8