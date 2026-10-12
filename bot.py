import os, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from PIL import Image
import io, re
import google.generativeai as genai

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot running")
def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SECRET_KEY = "kino123"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)
allowed_users = set()

@bot.message_handler(commands=['start'])
def start(m):
    args = m.text.split()
    if len(args) > 1 and args[1] == SECRET_KEY:
        allowed_users.add(m.from_user.id)
        bot.send_message(m.chat.id, "✅ Xush kelibsiz! Endi rasm, video yoki link tashlang 🎬")
    elif m.from_user.id in allowed_users:
        bot.send_message(m.chat.id, "Salom! Rasm, video yoki link tashlang 🎬")
    else:
        bot.send_message(m.chat.id, "⛔ Bu bot shaxsiy. Kirish uchun maxsus link kerak.")

def check_access(m):
    if m.from_user.id not in allowed_users:
        bot.send_message(m.chat.id, "⛔ Ruxsat yo'q. Maxsus link orqali kiring.")
        return False
    return True

# 1. RASM UCHUN
@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    if not check_access(m): return
    msg = bot.send_message(m.chat.id, "📸 Rasm qabul qilindi...\n⏳ Tahlil qilinmoqda 0%")
    bot.send_chat_action(m.chat.id, 'typing')
    try:
        time.sleep(0.5)
        bot.edit_message_text("📸 Rasm qabul qilindi...\n🔍 Film izlanmoqda 50%...", m.chat.id, msg.message_id)
        file_info = bot.get_file(m.file_id)
        downloaded = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded))
        bot.edit_message_text("📸 Rasm qabul qilindi...\n🧠 AI o'ylamoqda 90%...", m.chat.id, msg.message_id)
        response = model.generate_content(["Bu rasm qaysi filmdan? Nomini va yilini ayt, o'zbek tilida", image])
        bot.edit_message_text(f"✅ Tayyor!\n\n{response.text}", m.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}", m.chat.id, msg.message_id)

# 2. VIDEO VA LINK UCHUN
@bot.message_handler(content_types=['video', 'text'])
def handle_other(m):
    if not check_access(m): return
    if m.content_type == 'text' and 'http' not in m.text.lower():
        return

    if m.content_type == 'video':
        status = bot.send_message(m.chat.id, "🎥 Video qabul qilindi...\n⏳ Yuklanmoqda 0%")
        bot.send_chat_action(m.chat.id, 'typing')
        time.sleep(1)
        bot.edit_message_text("🎥 Video qabul qilindi...\n🔍 Kadrlar tahlil qilinmoqda 60%...", m.chat.id, status.message_id)
        bot.send_message(m.chat.id, "⚠️ Hozircha video ichidan aniq topish qiyin, videodan screenshot olib tashlang, 100% topib beradi!")
        return

    if 'http' in m.text.lower():
        status = bot.send_message(m.chat.id, f"🔗 Link qabul qilindi: {m.text[:30]}...\n⏳ Tekshirilmoqda 20%")
        bot.send_chat_action(m.chat.id, 'typing')
        time.sleep(1)
        bot.edit_message_text(f"🔗 Link qabul qilindi...\n🌐 Saytga ulanmoqda 50%...", m.chat.id, status.message_id)
        time.sleep(1)
        bot.edit_message_text(f"🔗 Link qabul qilindi...\n🎬 Film ma'lumoti olinmoqda 80%...", m.chat.id, status.message_id)
        bot.send_message(m.chat.id, "⚠️ Link dan to'g'ridan-to'g'ri izlab bo'lmaydi. Linkdagi videodan screenshot olib tashlang, men topib beraman!")

bot.infinity_polling()
