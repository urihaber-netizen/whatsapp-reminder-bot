import os
import json
from datetime import datetime
from flask import Flask, request
from twilio.rest import Client
from anthropic import Anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))

reminders = []

@app.route("/webhook", methods=["POST"])
def webhook():
    user_message = request.form.get("Body")
    from_number = request.form.get("From")

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

    parsed = json.loads(response.content[0].text)

    if parsed.get("isReminder") and parsed.get("datetime"):
        reminders.append({**parsed, "to": from_number, "sent": False})
        reply = f"✅ הבנתי! אזכיר לך: {parsed['task']}"
    else:
        reply = "לא הצלחתי להבין את התזכורת. נסה לכתוב למשל: 'תזכיר לי להתקשר לאמא בשעה 6'"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response><Message>{reply}</Message></Response>"""

def check_reminders():
    now = datetime.now()
    for reminder in reminders:
        if not reminder["sent"] and datetime.fromisoformat(reminder["datetime"]) <= now:
            twilio_client.messages.create(
                from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                to=reminder["to"],
                body=f"⏰ תזכורת: {reminder['task']}"
            )
            reminder["sent"] = True
            print(f"Sent reminder: {reminder['task']}")

scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", minutes=1)
scheduler.start()

if __name__ == "__main__":
    print("🤖 Bot running!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
