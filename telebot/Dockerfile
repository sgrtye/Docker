FROM python:3.15-alpine
ENV PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . /app

RUN uv sync --locked --no-dev && uv cache clean


CMD ["uv", "run", "--no-sync", "telebot"]