import os, threading, io, glob, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from PIL import Image
import google.generativeai as genai

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
def run_web():
    HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI)
model = genai.GenerativeModel('gemini-1.5-flash') # ESKISI O'CHDI

bot = telebot.TeleBot(TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Salom! Instagram Reels link tashlang!")

@bot.message_handler(content_types=['text'])
def handle(m):
    if 'instagram.com' not in m.text and 'tiktok.com' not in m.text and 'http' not in m.text:
        return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "📥 Instagram yuklanmoqda...")

    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = {
                'outtmpl': f'{tmpdir}/video.%(ext)s',
                'format': 'best',
                'quiet': True,
                'nocheckcertificate': True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
                files = glob.glob(f"{tmpdir}/*")
                if not files:
                    raise Exception("Video topilmadi")
                path = files[0]

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎬 Film nomi?", callback_data="find"))
            with open(path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Yuklandi! Filmni bilish uchun bosing 👇", reply_markup=markup)
            user_videos[m.chat.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ Xatolik: {e}\n\nLink yopiq akkauntdan bo'lishi mumkin. Ochiq Reels bilan sinab ko'ring.", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos:
        return
    bot.answer_callback_query(call.id, "Topilmoqda...")
    msg = bot.send_message(chat_id, "🧠 Film aniqlanmoqda...")
    try:
        import cv2
        f = bot.get_file(user_videos[chat_id])
        d = bot.download_file(f.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(d); p=tf.name
        cap = cv2.VideoCapture(p)
        cap.set(cv2.CAP_PROP_POS_MSEC, 2000)
        ret, frame = cap.read()
        cap.release(); os.remove(p)
        _, buf = cv2.imencode('.jpg', frame)
        img = Image.open(io.BytesIO(buf.tobytes()))
        res = model.generate_content(["Bu kadr qaysi filmdan? Nomini o'zbek tilida ayt.", img])
        bot.edit_message_text(f"🎬 {res.text}", chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}", chat_id, msg.message_id)

bot.infinity_polling()
