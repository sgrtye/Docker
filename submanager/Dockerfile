FROM python:3.12-alpine

ENV TZ=Europe/London

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN chmod 755 /app/entry.sh
RUN /usr/bin/crontab /app/crontab.txt

VOLUME /sub
VOLUME /conf.d

CMD ["/app/entry.sh"]