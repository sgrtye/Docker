FROM python:3.12-alpine

ENV TZ=Europe/London

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN mkdir /conf
VOLUME /conf

RUN mkdir /website
VOLUME /website

CMD ["python", "-u", "/app/main.py"]