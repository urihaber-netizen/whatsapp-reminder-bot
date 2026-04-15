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
        reply = f"✅ Got it! I'll remind you to: {parsed['task']}"
    else:
        repl
