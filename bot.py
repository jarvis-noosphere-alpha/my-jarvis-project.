import os
import telebot
import anthropic
from flask import Flask

app = Flask(__name__)
port = int(os.environ.get("PORT", 8080))

# Данные из ваших переменных Railway
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_KEY = os.environ.get("ANTHROPIC_API_KEY")

bot = telebot.TeleBot(TOKEN)
client = anthropic.Anthropic(api_key=CLAUDE_KEY)

@app.route('/')
def home():
    return "🏛️ JARVIS 2.0: система активна"
    
    
