import os
from datetime import datetime, timezone, timedelta
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from loguru import logger

# Load env
load_dotenv()

# Logger
logger.remove()
logger.add(lambda msg: print(msg, end=""))

app = Flask(__name__)

# Twilio client
twilio_client = Client(
    os.getenv("TWILIO_SID"),
    os.getenv("TWILIO_TOKEN")
)

# In-memory storage (temporary)
reminders = []

logger.info("[SERVER] Bot starting...")

# ---------------------------
# SAFE WEBHOOK (NO CRASHES)
# ---------------------------

@app.route("/webhook", methods=["POST"])
def webhook():

    try:
        logger.info("🚨 WEBHOOK HIT")

        user_message = request.form.get("Body")
        from_number = request.form.get("From")

        logger.info(f"[WEBHOOK] Message: {user_message}")
        logger.info(f"[WEBHOOK] From: {from_number}")

        if not user_message:
            return "OK", 200

        # ---------------------------
        # SIMPLE TEST PARSER (SAFE)
        # ---------------------------

        # Always treat message as reminder for now
        reminder = {
            "task": user_message,
            "datetime": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
            "to": from_number,
            "sent": False
        }

        reminders.append(reminder)

        logger.info(f"[REMINDER_STORAGE] Saved: {reminder}")

        reply_text = f"✅ תזכורת נשמרה: {user_message}"

        resp = MessagingResponse()
        resp.message(reply_text)

        logger.info("[WEBHOOK] Response sent successfully")

        return str(resp)

    except Exception as e:
        logger.error(f"[WEBHOOK CRASH SAFE HANDLED] {e}")
        return "OK", 200


# ---------------------------
# REMINDER CHECKER
# ---------------------------

def check_reminders():

    now = datetime.now(timezone.utc)

    logger.info(f"[REMINDER_CHECKER] Running at {now}")
    logger.info(f"[REMINDER_CHECKER] Total reminders: {len(reminders)}")

    for reminder in reminders:

        try:
            if reminder["sent"]:
                continue

            reminder_time = datetime.fromisoformat(
                reminder["datetime"].replace("Z", "+00:00")
            )

            if reminder_time <= now:

                logger.info(f"[TWILIO] Sending: {reminder['task']}")

                twilio_client.messages.create(
                    from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                    to=reminder["to"],
                    body=f"⏰ תזכורת: {reminder['task']}"
                )

                reminder["sent"] = True

                logger.success("[TWILIO] Sent successfully")

        except Exception as e:
            logger.error(f"[CHECKER ERROR] {e}")


# ---------------------------
# SCHEDULER
# ---------------------------

scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", seconds=30)
scheduler.start()

logger.info("[SCHEDULER] Started")

# ---------------------------
# SERVER START
# ---------------------------

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8080))

    logger.info(f"[SERVER] Running on port {port}")

    app.run(host="0.0.0.0", port=port)