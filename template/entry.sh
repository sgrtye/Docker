#!/bin/sh
set -e

# A test run of the template project then start the cron job
uv run --no-sync template
exec /usr/sbin/cron -f