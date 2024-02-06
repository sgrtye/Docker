FROM python:3.12-alpine

ENV TZ=Europe/London

RUN apk update --no-cache
RUN apk upgrade --no-cache

COPY ./requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

COPY ./main.py /main.py
CMD ["python", "-u", "main.py"]