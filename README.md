# 🤖 WhatsApp AI Reminder Bot

A personal AI assistant that runs on WhatsApp — set reminders, manage shopping lists, and to-do lists in natural Hebrew (or English).

## ✨ Features

- ⏰ **Smart Reminders** — understands natural language like "תזכיר לי ללכת לשיננית ביום שלישי"
- 📅 **Early Reminders** — automatically sends a heads-up the day before an event
- 🛒 **Shopping List** — add, view, and remove items
- ✅ **To-Do List** — track tasks
- 📋 **Custom Lists** — create any list you want
- 🇮🇱 **Hebrew Support** — fully understands and responds in Hebrew
- 💾 **Persistent Storage** — reminders and lists survive restarts (PostgreSQL)

## 🏗️ Stack

| Component | Technology |
|---|---|
| WhatsApp API | Twilio Sandbox |
| AI Brain | Claude (Anthropic API) |
| Server | Python + Flask |
| Scheduler | APScheduler |
| Database | PostgreSQL (Railway) |
| Hosting | Railway |
| Logging | Loguru |

## 📋 Prerequisites

- Python 3.12+
- A [Twilio](https://twilio.com) account with WhatsApp sandbox access
- An [Anthropic](https://console.anthropic.com) API key
- A [Railway](https://railway.app) account
- A [GitHub](https://github.com) account

## 🚀 Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/whatsapp-reminder-bot.git
cd whatsapp-reminder-bot
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the root directory:

```env
TWILIO_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_TOKEN=your_auth_token
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
YOUR_WHATSAPP=whatsapp:+972xxxxxxxxx
DATABASE_URL=postgresql://...
```

### 4. Connect WhatsApp Sandbox

1. Go to [Twilio Console](https://console.twilio.com) → Messaging → Try it out → Send a WhatsApp message
2. Send the join code from your WhatsApp to the Twilio sandbox number
3. Note: sandbox membership lasts 72 hours — rejoin anytime

### 5. Run locally

```bash
python3 bot.py
```

In a separate terminal, expose your server with ngrok:

```bash
ngrok http 8080
```

Set the ngrok URL as your Twilio webhook:
```
https://xxxx.ngrok-free.app/webhook
```

## ☁️ Deploy to Railway

1. Push code to GitHub (make sure `.env` is in `.gitignore`)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add a PostgreSQL database to the project
4. Set all environment variables in Railway's Variables tab (including `DATABASE_URL` from the Postgres service)
5. In Networking settings, generate a domain on port `8080`
6. Update your Twilio webhook to: `https://your-app.up.railway.app/webhook`

## 💬 Usage

Send any of these to your Twilio WhatsApp number:

| Message | Action |
|---|---|
| `תזכיר לי להתקשר לאמא ב-6` | Set a reminder for 6pm |
| `תזכיר לי ללכת לשיננית ביום שלישי` | Reminder on Tuesday + early reminder Monday evening |
| `תוסיף חלב ולחם לרשימת הקניות` | Add items to shopping list |
| `מה יש לי ברשימת הקניות?` | View shopping list |
| `סיימתי חלב` | Remove item from list |
| `מה התזכורות שלי?` | View upcoming reminders |
| `תוסיף להתקשר לדני למשימות` | Add to to-do list |

## 📁 Project Structure

```
whatsapp-reminder-bot/
├── bot.py              # Main application
├── requirements.txt    # Python dependencies
├── Procfile            # Railway start command
├── runtime.txt         # Python version
├── .gitignore          # Excludes .env from git
└── README.md           # This file
```

## 📦 Dependencies

```
flask
twilio
anthropic
apscheduler
python-dotenv
loguru
psycopg2-binary
```

## ⚠️ Notes

- Never commit your `.env` file to GitHub
- Twilio sandbox requires rejoining every 72 hours
- Railway free trial includes $5 credit (~30 days)
- Anthropic API costs ~$0.001 per message (very cheap)

## 📄 License

MIT