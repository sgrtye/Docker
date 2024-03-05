FROM python:3.12-alpine

ENV TZ=Europe/London

RUN mkdir /cache
VOLUME /cache

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

CMD ["python", "-u", "/app/main.py"]