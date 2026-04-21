import os
import json
from datetime import datetime
from flask import Flask, request
from twilio.rest import Client
from anthropic import Anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from loguru import logger
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)
logger.add("bot.log", rotation="10 MB", retention="7 days", level="DEBUG")

claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))

# ─── Database ───────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_phone TEXT NOT NULL,
                    task TEXT NOT NULL,
                    remind_at TIMESTAMP NOT NULL,
                    sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS list_items (
                    id SERIAL PRIMARY KEY,
                    user_phone TEXT NOT NULL,
                    list_name TEXT NOT NULL,
                    item TEXT NOT NULL,
                    done BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
    logger.success("✅ Database initialized")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def send_whatsapp(to, body):
    try:
        twilio_client.messages.create(
            from_=os.getenv("TWILIO_WHATSAPP_FROM"),
            to=to,
            body=body
        )
        logger.success(f"📤 Sent to {to}: {body}")
    except Exception as e:
        logger.error(f"❌ Failed to send: {e}")

# ─── Webhook ─────────────────────────────────────────────────────────────────

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    user_message = request.form.get("Body", "")
    from_number = request.form.get("From", "")
    logger.info(f"📩 From {from_number}: {user_message}")

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Today is {datetime.now().isoformat()}, {datetime.now().strftime('%A %d/%m/%Y')}, time is {datetime.now().strftime('%H:%M')}.

You are a Hebrew personal assistant bot. Understand the user's message and return JSON only, no markdown, no extra text.

Hebrew day names: ראשון=Sunday, שני=Monday, שלישי=Tuesday, רביעי=Wednesday, חמישי=Thursday, שישי=Friday, שבת=Saturday
If a day is mentioned, calculate the next upcoming occurrence from today.
Default time if not specified: 09:00.

Possible actions:
1. SET_REMINDER - user wants a reminder
2. ADD_TO_LIST - user wants to add items to a list (shopping/todo/custom)
3. VIEW_LIST - user wants to see a list
4. REMOVE_FROM_LIST - user wants to remove/complete an item
5. VIEW_REMINDERS - user wants to see upcoming reminders
6. UNKNOWN - none of the above

Return format:
{{
  "action": "SET_REMINDER" | "ADD_TO_LIST" | "VIEW_LIST" | "REMOVE_FROM_LIST" | "VIEW_REMINDERS" | "UNKNOWN",
  "reminders": [
    {{"task": "...", "datetime": "ISO8601"}},
    {{"task": "תזכורת מוקדמת: ...", "datetime": "ISO8601 of day before at 20:00"}}
  ],
  "list_name": "קניות" | "משימות" | "custom name",
  "items": ["item1", "item2"],
  "remove_items": ["item to remove"]
}}

Message: "{user_message}" """
            }]
        )

        raw = response.content[0].text
        logger.debug(f"🤖 Claude: {raw}")
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(clean)
        action = parsed.get("action", "UNKNOWN")

        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                # ── SET REMINDER ──
                if action == "SET_REMINDER":
                    added = []
                    for r in parsed.get("reminders", []):
                        if r.get("task") and r.get("datetime"):
                            cur.execute(
                                "INSERT INTO reminders (user_phone, task, remind_at) VALUES (%s, %s, %s)",
                                (from_number, r["task"], r["datetime"])
                            )
                            added.append(r["task"])
                    conn.commit()
                    tasks_text = "\n".join([f"• {t}" for t in added])
                    reply = f"✅ קבעתי לך תזכורות:\n{tasks_text}"

                # ── ADD TO LIST ──
                elif action == "ADD_TO_LIST":
                    list_name = parsed.get("list_name", "קניות")
                    items = parsed.get("items", [])
                    for item in items:
                        cur.execute(
                            "INSERT INTO list_items (user_phone, list_name, item) VALUES (%s, %s, %s)",
                            (from_number, list_name, item)
                        )
                    conn.commit()
                    items_text = "\n".join([f"• {i}" for i in items])
                    reply = f"✅ הוספתי לרשימת {list_name}:\n{items_text}"

                # ── VIEW LIST ──
                elif action == "VIEW_LIST":
                    list_name = parsed.get("list_name", "קניות")
                    cur.execute(
                        "SELECT item FROM list_items WHERE user_phone=%s AND list_name=%s AND done=FALSE ORDER BY created_at",
                        (from_number, list_name)
                    )
                    rows = cur.fetchall()
                    if rows:
                        items_text = "\n".join([f"• {r['item']}" for r in rows])
                        reply = f"📋 רשימת {list_name}:\n{items_text}"
                    else:
                        reply = f"רשימת {list_name} ריקה!"

                # ── REMOVE FROM LIST ──
                elif action == "REMOVE_FROM_LIST":
                    list_name = parsed.get("list_name", "קניות")
                    remove_items = parsed.get("remove_items", [])
                    for item in remove_items:
                        cur.execute(
                            "UPDATE list_items SET done=TRUE WHERE user_phone=%s AND list_name=%s AND item ILIKE %s",
                            (from_number, list_name, f"%{item}%")
                        )
                    conn.commit()
                    items_text = "\n".join([f"• {i}" for i in remove_items])
                    reply = f"✅ סימנתי כהושלם:\n{items_text}"

                # ── VIEW REMINDERS ──
                elif action == "VIEW_REMINDERS":
                    cur.execute(
                        "SELECT task, remind_at FROM reminders WHERE user_phone=%s AND sent=FALSE ORDER BY remind_at LIMIT 10",
                        (from_number,)
                    )
                    rows = cur.fetchall()
                    if rows:
                        items_text = "\n".join([f"• {r['task']} - {r['remind_at'].strftime('%d/%m %H:%M')}" for r in rows])
                        reply = f"📅 התזכורות הקרובות שלך:\n{items_text}"
                    else:
                        reply = "אין לך תזכורות קרובות!"

                else:
                    reply = "לא הבנתי. נסה:\n• 'תזכיר לי...'\n• 'תוסיף... לרשימת הקניות'\n• 'מה יש לי ברשימת הקניות?'\n• 'מה התזכורות שלי?'"

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        reply = "אירעה שגיאה, נסה שוב"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response><Message>{reply}</Message></Response>"""

# ─── Scheduler ───────────────────────────────────────────────────────────────

def check_reminders():
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM reminders WHERE sent=FALSE AND remind_at <= NOW()",
                )
                rows = cur.fetchall()
                for r in rows:
                    send_whatsapp(r["user_phone"], f"⏰ תזכורת: {r['task']}")
                    cur.execute("UPDATE reminders SET sent=TRUE WHERE id=%s", (r["id"],))
                conn.commit()
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")

# ─── Start ───────────────────────────────────────────────────────────────────

init_db()

scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "interval", minutes=1)
scheduler.start()
logger.info("⏰ Scheduler started")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🤖 Bot starting on port {port}...")
    app.run(host="0.0.0.0", port=port)