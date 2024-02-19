FROM python:3.12-alpine

ENV TZ=Europe/London

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY ./main.py /main.py
CMD ["python", "-u", "main.py"]

# RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# RUN touch /var/log/cron.log

# RUN (crontab -l ; echo "*/30 * * * * /usr/local/bin/python /app/main.py >> /var/log/cron.log 2>&1") | crontab

# CMD cron && tail -f /var/log/cron.log