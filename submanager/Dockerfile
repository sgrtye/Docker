FROM python:3.12-alpine

ENV TZ=Europe/London

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

RUN mkdir /sub
VOLUME /sub

RUN mkdir /conf.d
VOLUME /conf.d

COPY ./main.py /main.py
CMD ["python", "-u", "main.py"]