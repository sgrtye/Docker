FROM python:3.12-alpine
ENV PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

EXPOSE 80

COPY . /app
WORKDIR /app
RUN uv sync --locked && uv cache clean

VOLUME /logs
VOLUME /conf
VOLUME /website

CMD ["uv", "run", "main.py"]