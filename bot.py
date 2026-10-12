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

model = genai.GenerativeModel('gemini-1.5-flash')
model2 = genai.GenerativeModel('gemini-2.0-flash')

bot = telebot.TeleBot(TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Salom! 🎬 Instagram Reels link tashlang, 2 ta AI filmni topib beradi!")

@bot.message_handler(content_types=['text'])
def handle(m):
    if 'instagram.com' not in m.text and 'tiktok.com' not in m.text and 'http' not in m.text:
        return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "📥 Yuklanmoqda...")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best', 'quiet': True, 'nocheckcertificate': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
                files = glob.glob(f"{tmpdir}/*")
                path = files[0]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎬 Film nomi? (2 AI)", callback_data="find"))
            with open(path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Yuklandi! Pastni bosing 👇", reply_markup=markup)
            user_videos[m.chat.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"⚠️ Xato: {e}", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    bot.answer_callback_query(call.id, "2 ta AI tekshirmoqda...")
    msg = bot.send_message(chat_id, "🧠 2 ta AI + 3 ta kadr tekshirilmoqda...")

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

        prompt = """Bu 3 ta kadr bitta kinodan. Filmni top.
        Javob formati:
        1. Nomi (original va o'zbekcha)
        2. Yili
        3. Aktyorlar
        4. Qisqa mazmuni (2 jumla)
        O'zbek tilida javob ber. Agar topa olmasang 'topilmadi' de."""

        res1_text = "topilmadi"
        try:
            res1 = model.generate_content([prompt] + frames)
            res1_text = res1.text
        except Exception as e:
            res1_text = f"1-AI xato: {e}"

        if "topilmadi" in res1_text.lower() or len(res1_text) < 30:
            try:
                res2 = model2.generate_content([prompt + " Juda aniq top. Agar hind filmi bo'lsa ham nomini ayt."] + frames)
                final = f"🎬 1-AI o'yladi: {res1_text}\n\n🎬🎬 2-AI aniqlashtirdi:\n{res2.text}"
            except Exception as e:
                final = f"🎬 {res1_text}\n\n2-AI xato: {e}"
        else:
            final = f"🎬 {res1_text}"

        bot.edit_message_text(final, chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", chat_id, msg.message_id)

bot.infinity_polling()
