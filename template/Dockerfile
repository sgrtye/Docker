FROM python:3.15-slim
ENV PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . /app

RUN uv sync --locked --no-dev && uv cache clean

# EXPOSE 80
# RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
# HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

# CMD ["uv", "run", "--no-sync", "template"]

RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

RUN chmod 755 ./entry.sh
RUN /usr/bin/crontab ./crontab.txt

CMD ["./entry.sh"]