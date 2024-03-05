FROM python:3.12-alpine

ENV TZ=Europe/London

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

RUN mkdir /sub
VOLUME /sub

RUN mkdir /conf.d
VOLUME /conf.d

COPY . /submanager

RUN apk update && apk add -y cron && rm -rf /var/cache/apk/*

RUN touch /var/log/cron.log

RUN /usr/local/bin/python -u /submanager/update_nginx_config.py >> /var/log/cron.log 2>&1
RUN /usr/local/bin/python -u /submanager/remove_subscription.py >> /var/log/cron.log 2>&1
RUN /usr/local/bin/python -u /submanager/update_subscription.py >> /var/log/cron.log 2>&1

RUN (crontab -l ; echo "0 6,18 * * * /usr/local/bin/python -u /submanager/main.py >> /var/log/cron.log 2>&1") | crontab

CMD cron && tail -f /var/log/cron.log