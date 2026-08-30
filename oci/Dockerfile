FROM php:8.3-cli

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        cron \
        unzip \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

COPY oci-arm-host-capacity/. /app
COPY index.php crontab.txt entry.sh /app
WORKDIR /app

RUN composer install

VOLUME /app/env

RUN chmod 755 /app/entry.sh
RUN crontab /app/crontab.txt

CMD ["/app/entry.sh"]