FROM python:3.12-alpine

ENV TZ=Europe/London

RUN apk update && apk add --no-cache curl chromium chromium-chromedriver

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN pyarmor gen --output /app /app/main.py

HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

RUN mkdir /cache
VOLUME /cache

RUN mkdir /config
VOLUME /config

CMD ["python", "-u", "/app/main.py"]