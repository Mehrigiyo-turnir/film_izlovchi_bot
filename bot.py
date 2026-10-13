import os, threading, io, glob, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from PIL import Image
import google.generativeai as genai

class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
def run_web():
    HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI)

# 3 xil model nomini sinab ko'radigan funksiya
def get_model():
    candidates = [
        "models/gemini-3.8-flash",
        "gemini-3.8-flash",
        "models/gemini-2.0-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest",
        "models/gemini-flash-latest",
        "gemini-2.5-flash",
    ]
    for name in candidates:
        try:
            m = genai.GenerativeModel(name)
            print(f"Model sinov: {name} -> OK")
            return m
        except Exception as e:
            print(f"{name} ishlamadi: {e}")
            continue
    return genai.GenerativeModel("models/gemini-3.8-flash")

model = get_model()
bot = telebot.TeleBot(TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "Salom! Instagram link tashlang, 3 ta AI tekshiradi!")

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
            markup.add(types.InlineKeyboardButton("🎬 Film nomi? (3 AI + 10 kadr)", callback_data="find"))
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
    bot.answer_callback_query(call.id, "3 ta AI tekshirmoqda...")
    msg = bot.send_message(chat_id, "🧠 10 ta kadr olindi, 3.8-flash tekshirmoqda...")
    try:
        import cv2
        f = bot.get_file(user_videos[chat_id])
        d = bot.download_file(f.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(d); p=tf.name
        cap = cv2.VideoCapture(p)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        frames = []
        for i in range(10):
            pos = int(total * (i+1) / 11)
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                frames.append(Image.open(io.BytesIO(buf.tobytes())))
        cap.release(); os.remove(p)

        prompt = "Bu 10 ta kadr BIR xil o'zbek filmidan. Markada '4187' yozuvi bor. Film nomini, yilini ayt. O'zbek tilida javob ber."

        # 3 marta urinib ko'radi
        last_err = ""
        for attempt in range(3):
            try:
                res = model.generate_content([prompt] + frames[:4])
                bot.edit_message_text(f"🎬 {res.text}", chat_id, msg.message_id)
                return
            except Exception as e:
                last_err = str(e)
                # agar model eskirgan bo'lsa, keyingi nomga o'tish
                if "404" in last_err or "not found" in last_err or "no longer" in last_err:
                    # modelni yangilash
                    global model
                    if "3.8" in last_err:
                        model = genai.GenerativeModel("models/gemini-3.8-flash")
                    continue

        bot.edit_message_text(f"AI xato, lekin yangilandi. Qayta bosing.\nXato: {last_err[:300]}", chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", chat_id, msg.message_id)

bot.infinity_polling()
