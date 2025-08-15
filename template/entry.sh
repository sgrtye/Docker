#!/bin/sh

# A test run of main.py then start the cron job
uv run main.py
/usr/sbin/crond -f -l 8