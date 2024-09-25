FROM python:3.12

ENV TZ=Europe/London

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
RUN apt-get -y update
RUN apt-get install -y google-chrome-stable curl

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN pyarmor gen --output /app /app/main.py

HEALTHCHECK --start-period=10s --interval=60s --timeout=3s CMD curl -f http://localhost:80/health || exit 1

RUN mkdir /cache
VOLUME /cache

RUN mkdir /config
VOLUME /config

CMD ["python", "-u", "/app/main.py"]