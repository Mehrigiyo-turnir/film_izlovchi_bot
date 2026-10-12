import os, threading, io, glob, tempfile, requests
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
    bot.send_message(m.chat.id, "Salom! 🎬 YouTube, Insta, TikTok link tashlang. 100% yuklab beraman!")

def download_via_cobalt(url, tmpdir):
    # Boshqa botlar ishlatadigan API lar
    apis = ["https://api.cobalt.tools/api/json", "https://co.wuk.sh/api/json", "https://api.ownv.id/api/json"]
    for api in apis:
        try:
            r = requests.post(api, json={"url": url, "vQuality": "720", "aFormat": "mp3", "isAudioOnly": False},
                              headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=20)
            data = r.json()
            dl_url = data.get('url') or data.get('link')
            if dl_url:
                video_data = requests.get(dl_url, timeout=60, stream=True)
                ext = ".mp4"
                if "video/webm" in str(data): ext = ".webm"
                path = f"{tmpdir}/video{ext}"
                with open(path, 'wb') as f:
                    for chunk in video_data.iter_content(1024*1024):
                        f.write(chunk)
                return path
        except Exception as e:
            print(f"Cobalt {api} failed: {e}")
            continue
    return None

@bot.message_handler(content_types=['text'])
def handle_link(m):
    if 'http' not in m.text.lower(): return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "🔗 Qabul qilindi...\n📥 Boshqa botlar usulida yuklanmoqda 50%...")
    video_path = None
    tmpdir_obj = tempfile.TemporaryDirectory()
    tmpdir = tmpdir_obj.name

    try:
        # 1-USUL: Cobalt (eng kuchlisi)
        video_path = download_via_cobalt(url, tmpdir)

        # 2-USUL: Agar Cobalt ishlamasa yt-dlp
        if not video_path:
            bot.edit_message_text("🔗 Cobalt ishlamadi, 2-usul sinab ko'rilmoqda 70%...", m.chat.id, status.message_id)
            import yt_dlp
            opts = {
                'outtmpl': f'{tmpdir}/video.%(ext)s',
                'format': 'best[ext=mp4]/best',
                'quiet': True,
                'nocheckcertificate': True,
                'extractor_args': {'youtube': {'player_client': ['android','ios']}},
            }
            if os.path.exists("cookies.txt"): opts['cookiefile'] = "cookies.txt"
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
                files = glob.glob(f"{tmpdir}/*")
                if files: video_path = files[0]

        if not video_path or not os.path.exists(video_path):
            raise Exception("Yuklab bo'lmadi")

        bot.edit_message_text("✅ Yuklandi, yuborilmoqda...", m.chat.id, status.message_id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎬 Film nomi?", callback_data="find"))

        with open(video_path, 'rb') as v:
            sent = bot.send_video(m.chat.id, v, caption="✅ Video tayyor! Filmni bilish uchun bosing 👇", reply_markup=markup)

        user_videos[m.chat.id] = sent.video.file_id
        bot.delete_message(m.chat.id, status.message_id)
        tmpdir_obj.cleanup()

    except Exception as e:
        tmpdir_obj.cleanup()
        bot.edit_message_text(f"⚠️ Xatolik: {e}\n\nLinkni tekshiring, yoki screenshot tashlang.", m.chat.id, status.message_id)

@bot.callback_query_handler(func=lambda call: True)
def handle_button(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    bot.answer_callback_query(call.id, "Aniqlanmoqda...")
    msg = bot.send_message(chat_id, "🧠 AI o'ylamoqda...")
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
