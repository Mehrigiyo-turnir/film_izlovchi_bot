import os, threading, time, io, glob, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from PIL import Image
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
ALLOWED_FILE = "allowed_users.txt"

genai.configure(api_key=GEMINI_API_KEY)
# XATO TUZATILDI - yangi model
model = genai.GenerativeModel('gemini-2.0-flash')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
allowed_users = set()
if os.path.exists(ALLOWED_FILE):
    with open(ALLOWED_FILE, "r") as f:
        for line in f:
            try: allowed_users.add(int(line.strip()))
            except: pass

def save_user(uid):
    if uid not in allowed_users:
        allowed_users.add(uid)
        with open(ALLOWED_FILE, "a") as f: f.write(f"{uid}\n")

# Vaqtincha videolarni eslab qolish uchun
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m):
    args = m.text.split()
    if len(args) > 1 and args[1] == SECRET_KEY:
        save_user(m.from_user.id)
        bot.send_message(m.chat.id, "✅ Bir marta kirdingiz, endi boshqa link so'ramaydi! Video link tashlang 🎬")
    elif m.from_user.id in allowed_users:
        bot.send_message(m.chat.id, "Salom! Link tashlang, videoni yuklab beraman 🎬")
    else:
        bot.send_message(m.chat.id, "⛔ Ruxsat yo'q.")

def check_access(m):
    if m.from_user.id not in allowed_users:
        bot.send_message(m.chat.id, "⛔ Ruxsat yo'q. Maxsus link orqali kiring.")
        return False
    return True

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    if not check_access(m): return
    msg = bot.send_message(m.chat.id, "📸 Tahlil qilinmoqda... ⏳")
    try:
        file_info = bot.get_file(m.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        image = Image.open(io.BytesIO(downloaded))
        response = model.generate_content(["Bu rasm qaysi filmdan? Nomini, yilini ayt o'zbek tilida", image])
        bot.edit_message_text(f"✅ {response.text}", m.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}", m.chat.id, msg.message_id)

@bot.message_handler(content_types=['text'])
def handle_link(m):
    if not check_access(m): return
    if 'http' not in m.text.lower(): return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "🔗 Link qabul qilindi...\n📥 Video yuklanmoqda 20%")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            bot.edit_message_text("🔗 Link qabul qilindi...\n📥 Video yuklanmoqda 60%...", m.chat.id, status.message_id)
            ydl_opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best', 'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                files = glob.glob(f"{tmpdir}/*")
                video_path = files[0]

            bot.edit_message_text("🔗 Yuklandi, sizga yuborilmoqda...", m.chat.id, status.message_id)

            # Knopka yaratamiz
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton("🎬 Film nomi?", callback_data=f"find_{m.from_user.id}")
            markup.add(btn)

            # Videoni userga yuboramiz va eslab qolamiz
            with open(video_path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Video tayyor! Filmni bilish uchun knopkani bosing 👇", reply_markup=markup)

            # Video file_id sini saqlab qo'yamiz
            user_videos[m.from_user.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ Yuklab bo'lmadi: {e}", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda call: True)
def handle_button(call):
    if not call.data.startswith("find_"): return
    user_id = call.from_user.id
    if user_id not in user_videos:
        bot.answer_callback_query(call.id, "Video topilmadi, linkni qayta tashlang")
        return

    bot.answer_callback_query(call.id, "Tahlil qilinmoqda...")
    msg = bot.send_message(call.message.chat.id, "🧠 AI filmni aniqlamoqda... 90%")

    try:
        import cv2
        file_info = bot.get_file(user_videos[user_id])
        downloaded = bot.download_file(file_info.file_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(downloaded)
            tf_path = tf.name

        cap = cv2.VideoCapture(tf_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500) # 1.5 sekunddan kadr
        ret, frame = cap.read()
        cap.release()
        os.remove(tf_path)

        if not ret: raise Exception("Kadr olinmadi")
        _, buffer = cv2.imencode('.jpg', frame)
        image = Image.open(io.BytesIO(buffer.tobytes()))

        response = model.generate_content(["Bu kadr qaysi filmdan? Film nomini, yilini va qisqacha mazmunini o'zbek tilida ayt.", image])
        bot.edit_message_text(f"🎬 **Topildi!**\n\n{response.text}", call.message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}", call.message.chat.id, msg.message_id)

bot.infinity_polling()
