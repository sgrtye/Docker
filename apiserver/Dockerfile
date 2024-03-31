FROM python:3.12-alpine

ENV TZ=Europe/London

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN pyarmor gen --output /app /app/main.py

RUN apk --update --no-cache add curl

HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:8888/health || exit 1

RUN mkdir /cache
VOLUME /cache

CMD ["python", "-u", "/app/main.py"]