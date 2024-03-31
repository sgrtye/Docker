FROM python:3.12-alpine

ENV TZ=Europe/London

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN pyarmor gen --output /app /app/main.py

RUN apk --update --no-cache add curl

HEALTHCHECK --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

CMD ["python", "-u", "/app/main.py"]

# RUN chmod 755 /app/entry.sh
# RUN /usr/bin/crontab /app/crontab.txt

# CMD ["/app/entry.sh"]
