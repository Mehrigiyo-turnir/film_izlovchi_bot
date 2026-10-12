import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import google.generativeai as genai
from PIL import Image
import io
import requests

# Port uchun fake web server (Render Live bo'lishi uchun)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# Telegram bot
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Salom! Menga kino rasmini yuboring, men nomini topib beraman 🎬")

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    try:
        bot.send_message(m.chat.id, "Rasm tekshirilmoqda... ⏳")
        file_info = bot.get_file(m.file_id)
        downloaded = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded))
        
        prompt = "Bu rasm qaysi filmdan? Faqat film nomini va yilini ayta olasanmi? O'zbek tilida javob ber."
        response = model.generate_content([prompt, image])
        bot.send_message(m.chat.id, response.text)
    except Exception as e:
        bot.send_message(m.chat.id, f"Xatolik: {e}")

bot.infinity_polling()
