FROM python:3.12-alpine

ENV TZ=Europe/London

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

RUN mkdir -p /sub /conf.d
VOLUME /sub /conf.d

COPY . /submanager

RUN apk --no-cache add dcron \
    && touch /var/log/cron.log \
    && echo -e "sleep 5 && python -u /submanager/update_nginx_config.py >> /var/log/cron.log 2>&1\n\
sleep 5 && python -u /submanager/remove_subscription.py >> /var/log/cron.log 2>&1\n\
sleep 5 && python -u /submanager/update_subscription.py >> /var/log/cron.log 2>&1\n\
0 6,18 * * * python -u /submanager/update_subscription.py >> /var/log/cron.log 2>&1\n" > /etc/crontabs/root

CMD crond -f && tail -f /var/log/cron.log
