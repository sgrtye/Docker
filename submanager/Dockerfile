FROM python:3.12-alpine

ENV TZ=Europe/London

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

RUN mkdir -p /sub /conf.d
VOLUME /sub /conf.d

COPY . /submanager

RUN apk --no-cache add dcron at
RUN touch /var/log/cron.log

RUN echo -e "python -u /submanager/update_nginx_config.py >> /var/log/cron.log 2>&1" | at now + 1 minute \
    && echo -e "python -u /submanager/remove_subscription.py >> /var/log/cron.log 2>&1" | at now + 1 minute \
    && echo -e "python -u /submanager/update_subscription.py >> /var/log/cron.log 2>&1" | at now + 1 minute

RUN echo -e "0 6,18 * * * python -u /submanager/update_subscription.py >> /var/log/cron.log 2>&1\n" > /etc/crontabs/root

CMD crond -f && tail -f /var/log/cron.log
