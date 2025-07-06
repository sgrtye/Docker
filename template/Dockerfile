FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

EXPOSE 80
ENV TZ=Europe/London

COPY . /app
WORKDIR /app
RUN uv sync --locked

RUN apk --update --no-cache add curl
HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

CMD ["python", "-u", "main.py"]

# RUN chmod 755 ./entry.sh
# RUN /usr/bin/crontab ./crontab.txt

# CMD ["./entry.sh"]
