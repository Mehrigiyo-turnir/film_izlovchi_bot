import os, threading, time, io, glob, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from PIL import Image
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
SECRET_KEY = "kino123"
ALLOWED_FILE = "allowed_users.txt"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# XOTIRANI FAYLGA SAQLASH - ENDI UNUTILMAYDI
allowed_users = set()
if os.path.exists(ALLOWED_FILE):
    with open(ALLOWED_FILE, "r") as f:
        for line in f:
            try: allowed_users.add(int(line.strip()))
            except: pass

def save_user(user_id):
    allowed_users.add(user_id)
    with open(ALLOWED_FILE, "a") as f:
        f.write(f"{user_id}\n")

@bot.message_handler(commands=['start'])
def start(m):
    args = m.text.split()
    if len(args) > 1 and args[1] == SECRET_KEY:
        save_user(m.from_user.id)
        bot.send_message(m.chat.id, "✅ Xush kelibsiz! Endi bir marta kirdingiz, boshqa link so'ramaydi. Rasm yoki link tashlang 🎬")
    elif m.from_user.id in allowed_users:
        bot.send_message(m.chat.id, "Salom! Qaytganingizdan xursandman 😊 Rasm, video yoki link tashlang 🎬")
    else:
        bot.send_message(m.chat.id, "⛔ Bu bot shaxsiy. Kirish uchun maxsus link kerak.")

def check_access(m):
    if m.from_user.id not in allowed_users:
        bot.send_message(m.chat.id, "⛔ Ruxsat yo'q. Maxsus link orqali kiring.")
        return False
    return True

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    if not check_access(m): return
    msg = bot.send_message(m.chat.id, "📸 Rasm qabul qilindi...\n⏳ Tahlil qilinmoqda 0%")
    bot.send_chat_action(m.chat.id, 'typing')
    try:
        time.sleep(0.5)
        bot.edit_message_text("📸 Rasm qabul qilindi...\n🔍 Film izlanmoqda 50%...", m.chat.id, msg.message_id)
        file_info = bot.get_file(m.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded))
        bot.edit_message_text("📸 Rasm qabul qilindi...\n🧠 AI o'ylamoqda 90%...", m.chat.id, msg.message_id)
        response = model.generate_content(["Bu rasm qaysi filmdan? Film nomini va yilini ayt, o'zbek tilida.", image])
        bot.edit_message_text(f"✅ Tayyor!\n\n{response.text}", m.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}", m.chat.id, msg.message_id)

@bot.message_handler(content_types=['video', 'text'])
def handle_other(m):
    if not check_access(m): return
    if m.content_type == 'text' and 'http' not in m.text.lower(): return
    url = m.text if m.content_type == 'text' else None
    if url:
        status = bot.send_message(m.chat.id, f"🔗 Link qabul qilindi...\n⏳ Yuklanmoqda 20%")
        bot.send_chat_action(m.chat.id, 'typing')
        try:
            import yt_dlp, cv2
            bot.edit_message_text("🔗 Link qabul qilindi...\n📥 Video yuklanmoqda 50%...", m.chat.id, status.message_id)
            with tempfile.TemporaryDirectory() as tmpdir:
                ydl_opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best', 'quiet': True, 'no_warnings': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url, download=True)
                    files = glob.glob(f"{tmpdir}/*")
                    if not files: raise Exception("Video yuklanmadi")
                    video_path = files[0]
                bot.edit_message_text("🔗 Link qabul qilindi...\n🔍 Kadr olinmoqda 75%...", m.chat.id, status.message_id)
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
                ret, frame = cap.read()
                cap.release()
                if not ret: raise Exception("Kadr olinmadi")
                _, buffer = cv2.imencode('.jpg', frame)
                image = Image.open(io.BytesIO(buffer.tobytes()))
                bot.edit_message_text("🔗 Link qabul qilindi...\n🧠 AI tahlil qilmoqda 90%...", m.chat.id, status.message_id)
                response = model.generate_content(["Bu kadr qaysi filmdan? Film nomini va yilini ayt, o'zbek tilida.", image])
                bot.edit_message_text(f"✅ Tayyor!\n\n{response.text}", m.chat.id, status.message_id)
        except Exception as e:
            bot.edit_message_text(f"⚠️ Linkni yuklab bo'lmadi: {e}\n\nIltimos shu videodan screenshot olib tashlang!", m.chat.id, status.message_id)

bot.infinity_polling()
