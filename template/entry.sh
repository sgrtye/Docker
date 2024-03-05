#!/bin/sh

# start cron
python -u /app/main.py
/usr/sbin/crond -f -l 8