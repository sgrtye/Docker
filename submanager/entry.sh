#!/bin/sh

# start cron
python -u /submanager/update_nginx_config.py
python -u /submanager/remove_subscription.py
python -u /submanager/update_subscription.py
/usr/sbin/crond -f -l 8