import os, threading, io, glob, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from PIL import Image
from google import genai
from google.genai import types as genai_types

class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
def run_web():
    HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# YANGI API CLIENT
client = genai.Client(api_key=GEMINI_KEY)

bot = telebot.TeleBot(TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "Salom! Instagram link tashlang, yangi AI tekshiradi!")

@bot.message_handler(content_types=['text'])
def handle(m):
    if 'http' not in m.text: return
    status = bot.send_message(m.chat.id, "📥 Yuklanmoqda...")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best', 'quiet': True, 'nocheckcertificate': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(m.text.strip(), download=True)
                path = glob.glob(f"{tmpdir}/*")[0]
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🎬 Film nomi? (Yangi AI)", callback_data="find"))
            with open(path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Yuklandi! Pastni bosing 👇", reply_markup=kb)
            user_videos[m.chat.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    bot.answer_callback_query(call.id, "Yangi API tekshirmoqda...")
    msg = bot.send_message(chat_id, "🧠 Yangi Gemini 3.8 tekshirmoqda...")
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
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total*(i+1)/11))
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                frames.append(Image.open(io.BytesIO(buf.tobytes())))
        cap.release(); os.remove(p)

        # YANGI API DA SO'ROV
        prompt = "Bu 10 ta kadr bitta o'zbek filmdan. Film nomini, yilini, mazmunini o'zbek tilida ayt."

        # Rasmlarni yangi formatga o'tkazish
        content = [prompt] + frames[:4]

        # Google tavsiya qilgan yangi model
        response = client.models.generate_content(
            model="gemini-2.0-flash", # yangi API da bu nom barqaror
            contents=content
        )
        bot.edit_message_text(f"🎬 {response.text}", chat_id, msg.message_id)

    except Exception as e:
        # Agar 2.0 ham ishlamasa 3.8 ni sinab ko'rish
        try:
            response = client.models.generate_content(
                model="gemini-3.0-flash",
                contents=[prompt] + frames[:4]
            )
            bot.edit_message_text(f"🎬 {response.text}", chat_id, msg.message_id)
        except Exception as e2:
            bot.edit_message_text(f"AI xato: {e} | {e2}", chat_id, msg.message_id)

bot.infinity_polling()
