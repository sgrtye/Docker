import os
import json
import time
import sendgrid
import datetime

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

if SENDGRID_API_KEY is None or SENDER_EMAIL is None or RECIPIENT_EMAIL is None:
    print("Environment variables not fulfilled")

NOTIFICATION_INTERVAL_MINS = 20

sg = sendgrid.SendGridAPIClient(SENDGRID_API_KEY)

if __name__ == "__main__":
    while True:
        response = sg.client.mail.batch.post()
        batch_id = json.loads(response.body)["batch_id"]

        data = {
            "personalizations": [
                {"to": [{"email": RECIPIENT_EMAIL}], "subject": "Host is down!"}
            ],
            "from": {"email": SENDER_EMAIL},
            "content": [{"type": "text/plain", "value": f"Host is down!, email sent on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"}],
            "send_at": int(time.time()) + ((NOTIFICATION_INTERVAL_MINS + 15) * 60),
            "batch_id": batch_id,
        }

        response = sg.client.mail.send.post(request_body=data)

        # print(response.status_code) 202

        time.sleep(NOTIFICATION_INTERVAL_MINS * 60)

        data = {
            "batch_id": batch_id,
            "status": "cancel"
        }

        response = sg.client.user.scheduled_sends.post(
            request_body=data
        )

        # print(response.status_code) 201
        # print(response.body) batch_in + status