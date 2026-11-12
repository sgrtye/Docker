#!/bin/sh

# A test run of the template project then start the cron job
uv run template
/usr/sbin/crond -f -l 8