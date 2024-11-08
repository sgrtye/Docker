FROM composer:latest

COPY oci-arm-host-capacity /app
COPY index.php crontab.txt entry.sh /app
WORKDIR /app
RUN composer install

VOLUME /app/env

RUN chmod 755 /app/entry.sh
RUN /usr/bin/crontab /app/crontab.txt

CMD ["/app/entry.sh"]