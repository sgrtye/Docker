FROM python:3.12-alpine

ENV TZ=Europe/London

COPY . /submanager
RUN pip install --no-cache-dir -r /submanager/requirements.txt

RUN chmod 755 /submanager/entry.sh
RUN /usr/bin/crontab /submanager/crontab.txt

VOLUME /sub
VOLUME /conf.d

CMD ["/submanager/entry.sh"]
