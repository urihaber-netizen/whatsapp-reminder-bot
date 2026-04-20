import os
import json
from datetime import datetime, timezone, timedelta
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

# In-memory reminders (OK for single instance)
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

    logger.info(f"[WEBHOOK] Message: {user_message}")
    logger.info(f"[WEBHOOK] From: {from_number}")

    if not user_message:
        logger.warning("[WEBHOOK] Empty message received")
        return "OK", 200

    # ---------------------------
    # ANTHROPIC
    # ---------------------------

    try:
        logger.info("[ANTHROPIC] Sending request to Claude")

        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""
Today is {datetime.now(timezone.utc).isoformat()}.

Extract reminder info.

Return JSON ONLY:
{{
  "task": "...",
  "datetime": "ISO8601 or null",
  "isReminder": true/false
}}

Message: {user_message}
"""
            }]
        )

        raw_text = response.content[0].text
        logger.info(f"[ANTHROPIC] Raw: {raw_text}")

        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1

        parsed = json.loads(raw_text[start:end])
        logger.info(f"[ANTHROPIC] Parsed: {parsed}")

    except Exception as e:
        logger.error(f"[ANTHROPIC] Error: {e}")
        parsed = {"isReminder": False}

    # ---------------------------
    # REMINDER STORAGE
    # ---------------------------

    reply = "לא הצלחתי להבין את הבקשה."

    if parsed.get("isReminder"):

        task = parsed.get("task", "תזכורת")

        # SAFE fallback if datetime is missing or null
        reminder_time = parsed.get("datetime")

        if not reminder_time:
            reminder_time = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
            logger.warning("[REMINDER_STORAGE] Missing datetime → defaulting to +1 minute")

        reminder = {
            "task": task,
            "datetime": reminder_time,
            "to": from_number,
            "sent": False
        }

        reminders.append(reminder)

        logger.info(f"[REMINDER_STORAGE] Saved: {reminder}")

        reply = f"✅ הבנתי! אזכיר לך: {task}"

    else:
        logger.warning("[REMINDER_STORAGE] Not a reminder")

    resp = MessagingResponse()
    resp.message(reply)

    logger.info("[WEBHOOK] Response sent")

    return str(resp)

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

            logger.info(f"[REMINDER_CHECKER] Checking {reminder_time} vs {now}")

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
            logger.error(f"[REMINDER_CHECKER] Error: {e}")

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

    port = int(os.environ.get("PORT", 5000))

    logger.info(f"[SERVER] Running on port {port}")

    app.run(host="0.0.0.0", port=port)