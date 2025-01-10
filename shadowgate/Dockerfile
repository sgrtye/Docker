FROM python:3.12-alpine

EXPOSE 80
ENV TZ=Europe/London

COPY . /app
RUN pip install --no-cache-dir -r /app/requirements.txt

VOLUME /conf
VOLUME /website

CMD ["python", "-u", "/app/main.py"]