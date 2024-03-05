FROM python:3.12-alpine

ENV TZ=Europe/London

COPY . /submanager
RUN pip install --no-cache-dir -r /submanager/requirements.txt

RUN mkdir -p /sub /conf.d /submanager \
    && apk --no-cache add dcron at \
    && echo -e "python -u /submanager/update_nginx_config.py 2>&1" | at now + 1 minute \
    && echo -e "python -u /submanager/remove_subscription.py 2>&1" | at now + 1 minute \
    && echo -e "python -u /submanager/update_subscription.py 2>&1" | at now + 1 minute \
    && echo -e "0 6,18 * * * python -u /submanager/update_subscription.py 2>&1\n" > /etc/crontabs/root

VOLUME /sub
VOLUME /conf.d

ENTRYPOINT /usr/sbin/crond -f
