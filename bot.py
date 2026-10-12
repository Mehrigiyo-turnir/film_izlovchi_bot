import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from PIL import Image
import io
import google.generativeai as genai

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

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SECRET_KEY = "kino123" # <-- Bu sizning maxfiy parolingiz

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Ruxsat berilgan odamlar ro'yxati (avtomatik to'ladi)
allowed_users = set()

@bot.message_handler(commands=['start'])
def start(m):
    args = m.text.split()
    if len(args) > 1 and args[1] == SECRET_KEY:
        allowed_users.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ Xush kelibsiz! Endi rasm yuborishingiz mumkin 🎬")
    elif m.from_user.id in allowed_users:
        bot.send_message(m.chat.id, "Salom! Rasm yuboring 🎬")
    else:
        bot.send_message(m.chat.id, "⛔ Bu bot shaxsiy. Kirish uchun maxsus link kerak.")

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    if m.from_user.id not in allowed_users:
        bot.send_message(m.chat.id, "⛔ Sizda ruxsat yo'q. Maxsus link orqali kiring.")
        return
    try:
        bot.send_message(m.chat.id, "Tekshirilmoqda... ⏳")
        file_info = bot.get_file(m.file_id)
        downloaded = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded))
        prompt = "Bu rasm qaysi filmdan? Film nomini va yilini ayt, o'zbek tilida."
        response = model.generate_content([prompt, image])
        bot.send_message(m.chat.id, response.text)
    except Exception as e:
        bot.send_message(m.chat.id, f"Xatolik: {e}")

bot.infinity_polling()
