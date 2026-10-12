import os, threading, io, glob, tempfile
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
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Salom! 🎬 Link tashlang. Videoni yuklab beraman + film nomini topaman!")

def get_ydl_opts(tmpdir):
    opts = {
        'outtmpl': f'{tmpdir}/video.%(ext)s',
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'nocheckcertificate': True,
        'extractor_args': {'youtube': {'player_client': ['android','ios','web']}},
    }
    if os.path.exists("cookies.txt"):
        opts['cookiefile'] = "cookies.txt"
    return opts

@bot.message_handler(content_types=['text'])
def handle_link(m):
    if 'http' not in m.text.lower(): return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "📥 Yuklanmoqda...")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            with yt_dlp.YoutubeDL(get_ydl_opts(tmpdir)) as ydl:
                ydl.extract_info(url, download=True)
                files = glob.glob(f"{tmpdir}/*")
                video_path = files[0]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎬 Film nomi?", callback_data="find"))
            with open(video_path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Tayyor! Bosing 👇", reply_markup=markup)
            user_videos[m.chat.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        if "Sign in to confirm" in str(e):
            bot.edit_message_text("⚠️ YouTube blokladi. Iltimos GitHub ga cookies.txt yuklang, shunda 100% ishlaydi.", m.chat.id, status.message_id)
        else:
            bot.edit_message_text(f"Xatolik: {e}", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "find")
def handle_button(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id, "Topilmoqda...")
    msg = bot.send_message(chat_id, "🧠 Aniqlanmoqda...")
    try:
        import cv2
        file_info = bot.get_file(user_videos[chat_id])
        downloaded = bot.download_file(file_info.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(downloaded); tf_path = tf.name
        cap = cv2.VideoCapture(tf_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
        ret, frame = cap.read()
        cap.release(); os.remove(tf_path)
        _, buffer = cv2.imencode('.jpg', frame)
        image = Image.open(io.BytesIO(buffer.tobytes()))
        response = model.generate_content(["Bu kadr qaysi filmdan? O'zbek tilida ayt.", image])
        bot.edit_message_text(f"🎬 {response.text}", chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}", chat_id, msg.message_id)

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    msg = bot.send_message(m.chat.id, "📸 Tahlil...")
    file_info = bot.get_file(m.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)
    image = Image.open(io.BytesIO(downloaded))
    response = model.generate_content(["Bu rasm qaysi filmdan?", image])
    bot.edit_message_text(f"✅ {response.text}", m.chat.id, msg.message_id)

bot.infinity_polling()
