FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app
WORKDIR /app
RUN uv sync --locked

CMD ["uv", "run", "python", "-u", "main.py"]