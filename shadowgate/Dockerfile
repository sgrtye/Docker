FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

EXPOSE 80

COPY . /app
WORKDIR /app
RUN uv sync --locked

VOLUME /logs
VOLUME /conf
VOLUME /website

CMD ["uv", "run", "python", "-u", "main.py"]