FROM python:3.12-slim

ENV TZ=Europe/London
ENV DISPLAY=:99

RUN apt-get update
RUN apt-get install -y gnupg curl ca-certificates --no-install-recommends

RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
RUN apt-get update
RUN apt-get install -y google-chrome-stable --no-install-recommends

RUN apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN seleniumbase get chromedriver --path
RUN pyarmor gen --output /app /app/main.py

HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

RUN mkdir /cache
VOLUME /cache

RUN mkdir /config
VOLUME /config

CMD ["python", "-u", "/app/main.py"]