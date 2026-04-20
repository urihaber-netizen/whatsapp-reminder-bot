import os
import json
from datetime import datetime, timezone
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from anthropic import Anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Configure loguru
logger.remove()
logger.add("bot.log", rotation="10 MB")
logger.add(lambda msg: print(msg, end=""))

app = Flask(__name__)

# Clients
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))

# In-memory reminders
reminders = []

logger.info("[SERVER] Bot starting...")

# ---------------------------
# WEBHOOK
# ---------------------------

@app.route("/webhook", methods=["POST"])
def webhook():

    logger.info("[WEBHOOK] Incoming request")

    user_message = request.form.get("Body")
    from_number = request.form.get("From")

    logger.info(f"[WEBHOOK] Message received: {user_message}")
    logger.info(f"[WEBHOOK] From number: {from_number}")

    if not user_message:
        logger.warning("[WEBHOOK] No message body received")
        return "OK", 200

    # ---------------------------
    # ANTHROPIC
    # ---------------------------

    try:

        logger.info("[ANTHROPIC] Sending message to Claude")

        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""
Today is {datetime.now().isoformat()}.

Extract reminder info from this message.

Return JSON ONLY:
{{"task":"...","datetime":"ISO8601 or null","isReminder":true/false}}

Message: {user_message}
"""
            }]
        )

        raw_text = response.content[0].text

        logger.info(f"[ANTHROPIC] Raw response: {raw_text}")

        try:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            parsed = json.loads(raw_text[start:end])

            logger.info(f"[ANTHROPIC] Parsed JSON: {parsed}")

        except Exception as e:
            logger.error(f"[ANTHROPIC] JSON parse error: {e}")
            parsed = {"isReminder": False}

    except Exception as e:
        logger.error(f"[ANTHROPIC] Claude request failed: {e}")
        parsed = {"isReminder": False}

    # ---------------------------
    # REMINDER STORAGE
    # ---------------------------

    if parsed.get("isReminder") and parsed.get("datetime"):

        reminder = {
            "task": parsed.get("task"),
            "datetime": parsed.get("datetime"),
            "to": from_number,
            "sent": False
        }

        reminders.append(reminder)

        logger.info(f"[REMINDER_STORAGE] Reminder stored: {reminder}")

        reply = f"✅ הבנתי! אזכיר לך: {parsed.get('task')}"

    else:

        logger.warning("[REMINDER_STORAGE] Not a valid reminder")

        reply = "לא הצלחתי להבין את התזכורת."

    resp = MessagingResponse()
    resp.message(reply)

    logger.info("[WEBHOOK] Response sent to user")

    return str(resp)

# ---------------------------
# REMINDER CHECKER
# ---------------------------

def check_reminders():

    now = datetime.now(timezone.utc)

    logger.info(f"[REMINDER_CHECKER] Checking reminders at {now}")

    logger.info(f"[REMINDER_CHECKER] Current reminders: {reminders}")

    for reminder in reminders:

        try:

            if reminder["sent"]:
                continue

            reminder_time = datetime.fromisoformat(
                reminder["datetime"].replace("Z", "+00:00")
            )

            logger.info(
                f"[REMINDER_CHECKER] Comparing {reminder_time} with {now}"
            )

            if reminder_time <= now:

                logger.info(
                    f"[TWILIO_SEND] Sending reminder: {reminder['task']}"
                )

                twilio_client.messages.create(
                    from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                    to=reminder["to"],
                    body=f"⏰ תזכורת: {reminder['task']}"
                )

                reminder["sent"] = True

                logger.success("[TWILIO_SEND] Reminder sent successfully")

        except Exception as e:

            logger.error(f"[REMINDER_CHECKER] Reminder error: {e}")

# ---------------------------
# SCHEDULER
# ---------------------------

scheduler = BackgroundScheduler()

scheduler.add_job(check_reminders, "interval", seconds=30)

scheduler.start()

logger.info("[SCHEDULER] Reminder scheduler started")

# ---------------------------
# SERVER START
# ---------------------------

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    logger.info(f"[SERVER] Starting Flask server on port {port}")

    app.run(host="0.0.0.0", port=port)