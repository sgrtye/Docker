FROM mcr.microsoft.com/playwright/python:jammy

ENV TZ=Europe/London

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN playwright install chromium

RUN pyarmor gen --output /app /app/main.py

HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

RUN mkdir /cache
VOLUME /cache

RUN mkdir /config
VOLUME /config

CMD ["python", "-u", "/app/main.py"]