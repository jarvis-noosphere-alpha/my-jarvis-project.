import os
import telebot
import anthropic
from flask import Flask

# 1. Настройка сервера для Railway
app = Flask(__name__)
PORT = int(os.environ.get("PORT", 8080))

# 2. Данные из ваших переменных Railway
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_KEY = os.environ.get("ANTHROPIC_API_KEY")

bot = telebot.TeleBot(TOKEN)
client = anthropic.Anthropic(api_key=CLAUDE_KEY)

@app.route('/')
def home():
    return "🏛️ JARVIS 2.0: Система активна и слушает Telegram!"

# 3. Как Альфред будет отвечать в Telegram
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # Запрос к Claude
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            system="Ты — Альфред, ИИ-ассистент Артура (LuckyEntrepreneur). Пиши дерзко, аналитично, используй вайбкодинг.",
            messages=[{"role": "user", "content": message.text}]
        )
        bot.reply_to(message, response.content[0].text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

# 4. Запуск
if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: bot.infinity_polling()).start()
    app.run(host='0.0.0.0', port=PORT)
    
