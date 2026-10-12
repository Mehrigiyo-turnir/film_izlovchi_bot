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

bot = telebot.TeleBot(TOKEN)
user_videos = {}

def get_working_model():
    # Google tez-tez nomini o'zgartiradi, shuning uchun bir nechta nomni sinaymiz
    candidates = [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "models/gemini-2.0-flash",
        "models/gemini-flash-latest",
    ]
    for name in candidates:
        try:
            m = genai.GenerativeModel(name)
            # kichik test
            m.generate_content("hi")
            print(f"Model ishladi: {name}")
            return m
        except Exception as e:
            print(f"Model ishlamadi {name}: {e}")
            continue
    return genai.GenerativeModel("gemini-2.0-flash")

model = get_working_model()

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Salom! Instagram Reels tashlang, filmni topaman!")

@bot.message_handler(content_types=['text'])
def handle(m):
    if 'http' not in m.text: return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "📥 Yuklanmoqda...")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best', 'quiet': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
                path = glob.glob(f"{tmpdir}/*")[0]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎬 Film nomi? (2 AI)", callback_data="find"))
            with open(path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Yuklandi! Pastni bosing 👇", reply_markup=markup)
            user_videos[m.chat.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    bot.answer_callback_query(call.id, "Tekshirilmoqda...")
    msg = bot.send_message(chat_id, "🧠 AI tekshirmoqda, 3 ta kadr...")
    try:
        import cv2
        f = bot.get_file(user_videos[chat_id])
        d = bot.download_file(f.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(d); p=tf.name
        cap = cv2.VideoCapture(p)
        frames = []
        for msec in [1000, 3000, 6000]:
            cap.set(cv2.CAP_PROP_POS_MSEC, msec)
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode('.jpg', frame)
                frames.append(Image.open(io.BytesIO(buf.tobytes())))
        cap.release(); os.remove(p)

        prompt = "Bu 3 kadr bitta film/serialdan. Nomini, yilini, aktyorlarini o'zbek tilida ayt. Topa olmasang ham taxmin qil."
        res = model.generate_content([prompt] + frames)
        bot.edit_message_text(f"🎬 {res.text}", chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"AI xato: {e}", chat_id, msg.message_id)

bot.infinity_polling()
