FROM python:3.12-alpine

ENV TZ=Europe/London

COPY ./requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /requirements.txt

RUN mkdir /novel
VOLUME /novel

COPY ./main.py /main.py
CMD ["python", "-u", "main.py"]