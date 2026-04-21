import os
import json
from datetime import datetime
from flask import Flask, request
from twilio.rest import Client
from anthropic import Anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

app = Flask(__name__)

logger.add("bot.log", rotation="10 MB", retention="7 days", level="DEBUG")

claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))

reminders = []

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    user_message = request.form.get("Body", "")
    from_number = request.form.get("From", "")

    logger.info(f"📩 Incoming message from {from_number}: {user_message}")

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Today is {datetime.now().isoformat()}. Extract reminder info from this message and return JSON only, no extra text:
                {{"task": "...", "datetime": "ISO8601 datetime or null", "isReminder": true/false}}
                Message: "{user_message}" """
            }]
        )

        raw = response.content[0].text
        logger.debug(f"🤖 Claude response: {raw}")
        parsed = json.loads(raw)

        if parsed.get("isReminder") and parsed.get("datetime"):
            reminders.append({**parsed, "to": from_number, "sent": False})
            reply = f"✅ הבנתי! אזכיר לך: {parsed['task']}"
            logger.success(f"✅ Reminder set: {parsed['task']} at {parsed['datetime']}")
        else:
            reply = "לא הצלחתי להבין את התזכורת. נסה לכתוב למשל: 'תזכיר לי להתקשר לאמא בשעה 6'"
            logger.warning(f"⚠️ Could not parse reminder from: {user_message}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        reply = "אירעה שגיאה, נסה שוב"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response><Message>{reply}</Message></Response>"""

def check_reminders():
    now = datetime.now()
    for reminder in reminders:
        if not reminder["sent"] and datetime.fromisoformat(reminder["datetime"]) <= now:
            try:
                twilio_client.messages.create(
                    from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                    to=reminder["to"],
                    body=f"⏰ תזכורת: {reminder['task']}"
                )
                reminder["sent"] = True
                logger.success(f"📤 Sent reminder: {reminder['task']}")
            except Exception as e:
                logger.error(f"❌ Failed to send reminder: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", minutes=1)
scheduler.start()
logger.info("⏰ Scheduler started")

if __name__ == "__main__":
    logger.info("🤖 Bot starting...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))