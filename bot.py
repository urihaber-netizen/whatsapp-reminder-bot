import os
import json
from datetime import datetime
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from anthropic import Anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load env variables
load_dotenv()

app = Flask(__name__)

# Clients
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))

# In-memory reminders
reminders = []

# 🔔 Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():

    print("📩 Incoming request:", request.form)

    user_message = request.form.get("Body")
    from_number = request.form.get("From")

    if not user_message:
        print("❌ No message body received")
        return "OK", 200

    try:

        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""
Today is {datetime.now().isoformat()}.

Extract reminder info from this message.

Return JSON ONLY like this:
{{"task": "...", "datetime": "ISO8601 or null", "isReminder": true/false}}

Message:
{user_message}
"""
            }]
        )

        raw_text = response.content[0].text
        print("🧠 Claude raw response:", raw_text)

        # Clean markdown formatting if Claude adds it
        clean = raw_text.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(clean)
        except Exception as e:
            print("❌ JSON parse error:", e)
            parsed = {"isReminder": False}

    except Exception as e:
        print("❌ Anthropic error:", e)
        parsed = {"isReminder": False}

    # Decide response
    if parsed.get("isReminder") and parsed.get("datetime"):

        reminders.append({
            "task": parsed.get("task"),
            "datetime": parsed.get("datetime"),
            "to": from_number,
            "sent": False
        })

        print("✅ Reminder stored:", reminders)

        reply = f"✅ הבנתי! אזכיר לך: {parsed.get('task')}"

    else:

        reply = "לא הצלחתי להבין את התזכורת. נסה למשל: תזכיר לי להתקשר לאמא בשעה 6"

        print("⚠️ Not a valid reminder")

    # Twilio response
    resp = MessagingResponse()
    resp.message(reply)

    return str(resp)


# ⏰ Reminder checker
def check_reminders():

    now = datetime.now()

    print("⏳ Checking reminders at", now.isoformat())
    print("📦 Current reminders:", reminders)

    for reminder in reminders:

        try:

            if reminder["sent"]:
                continue

            # Fix ISO Z timezone
            reminder_time = datetime.fromisoformat(
                reminder["datetime"].replace("Z", "+00:00")
            )

            if reminder_time <= now:

                print("🚀 Sending reminder:", reminder)

                twilio_client.messages.create(
                    from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                    to=reminder["to"],
                    body=f"⏰ תזכורת: {reminder['task']}"
                )

                reminder["sent"] = True

                print("✅ Reminder sent")

        except Exception as e:

            print("❌ Reminder error:", str(e), reminder)


# 🧵 Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", seconds=30)
scheduler.start()


# 🚀 Start server
if __name__ == "__main__":

    print("🤖 Bot starting...")

    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port)
