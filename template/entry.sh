#!/bin/sh

# start cron
python /app/main.py
/usr/sbin/crond -f -l 8