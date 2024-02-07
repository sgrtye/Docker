FROM python:3.12-alpine

ENV TZ=Europe/London

RUN apk add gcc musl-dev linux-headers

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY ./main.py /main.py
CMD ["python", "-u", "main.py"]