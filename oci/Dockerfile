FROM composer:latest

COPY . /app
WORKDIR /app
RUN composer install

VOLUME /app/env

RUN chmod 755 /app/entry.sh
RUN /usr/bin/crontab /app/crontab.txt

CMD ["/app/entry.sh"]