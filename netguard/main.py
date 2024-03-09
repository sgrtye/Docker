import os
import json
import time
import schedule
import datetime
import sendgrid

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")
HOST_NAME = os.environ.get("HOST_NAME")

if SENDGRID_API_KEY is None or SENDER_EMAIL is None or RECIPIENT_EMAIL is None or HOST_NAME is None:
    print("Environment variables not fulfilled")

NOTIFICATION_INTERVAL_MINS = 20
batch_id = None

sg = sendgrid.SendGridAPIClient(SENDGRID_API_KEY)

def send_notification():
    try:
        global batch_id

        response = sg.client.user.scheduled_sends.get()

        for item in json.loads(response.body):
            try:
                response = sg.client.user.scheduled_sends._(item['batch_id']).delete()
            except Exception as e:
                pass

        if batch_id is not None:
            data = {
                "batch_id": batch_id,
                "status": "cancel"
            }

            for _ in range(5):
                try:
                    response = sg.client.user.scheduled_sends.post(
                        request_body=data
                    )

                    if response.status_code == 201 or json.loads(response.body)["status"] == 'cancel':
                        break
                    else:
                        time.sleep(5)
                        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Failed to cancel scheduled email")
                
                except Exception as e:
                    pass

        batch_id = json.loads(sg.client.mail.batch.post().body)["batch_id"]

        data = {
            "personalizations": [
                {"to": [{"email": RECIPIENT_EMAIL}], "subject": "Host is down!"}
            ],
            "from": {"email": SENDER_EMAIL},
            "content": [{"type": "text/plain", "value": f"Host *{HOST_NAME}* is down! Email alert sent on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"}],
            "send_at": int(time.time()) + ((NOTIFICATION_INTERVAL_MINS + 15) * 60),
            "batch_id": batch_id,
        }

        response = sg.client.mail.send.post(request_body = data)

        if response.status_code != 202:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Failed to send scheduled email")
            batch_id = None
    
    except Exception as e:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(e))
        print(f"Error occurred on line {e.__traceback__.tb_lineno}")

if __name__ == "__main__":
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Net Guard started")
    schedule.every(NOTIFICATION_INTERVAL_MINS).minutes.do(send_notification)

    while True:
        schedule.run_pending()
        time.sleep(10)
