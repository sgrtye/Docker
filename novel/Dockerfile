FROM python:3.15-alpine
ENV PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . /app

RUN uv sync --locked --no-dev && uv cache clean

EXPOSE 80
RUN apk --update --no-cache add curl
HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

VOLUME /cache
VOLUME /config

CMD ["uv", "run", "--no-sync", "novel"]