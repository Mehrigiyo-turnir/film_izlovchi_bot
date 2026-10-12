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

# ENG YANGI MODELNI TOPISH
def get_model():
    try:
        # Google tavsiya qilgan eng yangi nomlar
        for name in ['models/gemini-2.5-flash', 'models/gemini-2.0-flash', 'models/gemini-1.5-flash', 'gemini-1.5-flash-latest']:
            try:
                m = genai.GenerativeModel(name)
                # test
                return m
            except: continue
    except: pass
    return genai.GenerativeModel('models/gemini-2.5-flash')

model = get_model()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Salom! 👋 Link yoki rasm tashlang, filmni topib beraman 🎬")

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
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
    if 'http' not in m.text.lower(): return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "🔗 Qabul qilindi...\n📥 Video yuklanmoqda...")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best', 'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                files = glob.glob(f"{tmpdir}/*")
                video_path = files[0]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎬 Film nomi?", callback_data=f"find_{m.from_user.id}"))
            with open(video_path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Tayyor! Filmni bilish uchun bosing 👇", reply_markup=markup)
            user_videos[m.from_user.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"⚠️ Yuklab bo'lmadi: {e}", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda call: True)
def handle_button(call):
    user_id = call.from_user.id
    if user_id not in user_videos:
        bot.answer_callback_query(call.id, "Video topilmadi")
        return
    bot.answer_callback_query(call.id, "Aniqlanmoqda...")
    msg = bot.send_message(call.message.chat.id, "🧠 AI o'ylamoqda... 90%")
    try:
        import cv2
        file_info = bot.get_file(user_videos[user_id])
        downloaded = bot.download_file(file_info.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(downloaded); tf_path = tf.name
        cap = cv2.VideoCapture(tf_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
        ret, frame = cap.read()
        cap.release(); os.remove(tf_path)
        if not ret: raise Exception("Kadr olinmadi")
        _, buffer = cv2.imencode('.jpg', frame)
        image = Image.open(io.BytesIO(buffer.tobytes()))
        response = model.generate_content(["Bu kadr qaysi filmdan? Film nomini, yilini ayt o'zbek tilida.", image])
        bot.edit_message_text(f"🎬 Topildi!\n\n{response.text}", call.message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}\nModel: {model.model_name}", call.message.chat.id, msg.message_id)

bot.infinity_polling()
