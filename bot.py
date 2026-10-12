import os, threading, io, glob, tempfile, re, requests
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

def get_youtube_id(url):
    m = re.search(r'(?:v=|shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else None

def download_youtube_piped(video_id, tmpdir):
    # Piped - YouTube ni boshqa server orqali oladi, bloklanmaydi
    try:
        api_url = f"https://pipedapi.kavin.rocks/streams/{video_id}"
        data = requests.get(api_url, timeout=20).json()
        # Eng yaxshi mp4 ni topish
        streams = data.get('videoStreams', [])
        best_url = None
        for s in streams:
            if s.get('mimeType') == 'video/mp4' and s.get('quality') == '720p':
                best_url = s['url']; break
        if not best_url:
            for s in streams:
                if 'mp4' in s.get('mimeType',''):
                    best_url = s['url']; break
        if not best_url: return None

        r = requests.get(best_url, stream=True, timeout=60)
        path = f"{tmpdir}/video.mp4"
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                f.write(chunk)
        return path
    except Exception as e:
        print(f"Piped error: {e}")
        return None

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "Salom! 🎬 YouTube link tashlang, 100% yuklab beraman!")

@bot.message_handler(content_types=['text'])
def handle_link(m):
    if 'http' not in m.text.lower(): return
    url = m.text.strip()
    status = bot.send_message(m.chat.id, "🔗 YouTube link qabul qilindi...\n📥 Boshqa server orqali yuklanmoqda 50%...")

    tmpdir_obj = tempfile.TemporaryDirectory()
    tmpdir = tmpdir_obj.name
    video_path = None

    try:
        yt_id = get_youtube_id(url)
        if yt_id:
            # 1-USUL: Piped (YouTube uchun eng zo'ri)
            video_path = download_youtube_piped(yt_id, tmpdir)

        # 2-USUL: Cobalt API
        if not video_path:
            try:
                r = requests.post("https://api.cobalt.tools/api/json",
                    json={"url": url, "vQuality": "720"},
                    headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=20)
                dl_url = r.json().get('url')
                if dl_url:
                    v = requests.get(dl_url, stream=True, timeout=60)
                    video_path = f"{tmpdir}/video.mp4"
                    with open(video_path, 'wb') as f:
                        for ch in v.iter_content(1024*1024): f.write(ch)
            except: pass

        # 3-USUL: yt-dlp (oxirgi umid)
        if not video_path:
            bot.edit_message_text("📥 2-usul sinab ko'rilmoqda 80%...", m.chat.id, status.message_id)
            import yt_dlp
            opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best[ext=mp4]/best', 'quiet': True,
                    'extractor_args': {'youtube': {'player_client': ['android','ios']}}}
            if os.path.exists("cookies.txt"): opts['cookiefile'] = "cookies.txt"
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)
                files = glob.glob(f"{tmpdir}/*")
                if files: video_path = files[0]

        if not video_path: raise Exception("Hamma usul ishlamadi")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎬 Film nomi?", callback_data="find"))
        with open(video_path, 'rb') as v:
            sent = bot.send_video(m.chat.id, v, caption="✅ YouTube video yuklandi! Filmni bilish uchun bosing 👇", reply_markup=markup)
        user_videos[m.chat.id] = sent.video.file_id
        bot.delete_message(m.chat.id, status.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ Xatolik: {e}", m.chat.id, status.message_id)
    finally:
        tmpdir_obj.cleanup()

@bot.callback_query_handler(func=lambda call: True)
def handle_button(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    msg = bot.send_message(chat_id, "🧠 Film aniqlanmoqda...")
    try:
        import cv2
        file_info = bot.get_file(user_videos[chat_id])
        data = bot.download_file(file_info.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(data); p = tf.name
        cap = cv2.VideoCapture(p)
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
        ret, frame = cap.read()
        cap.release(); os.remove(p)
        _, buf = cv2.imencode('.jpg', frame)
        img = Image.open(io.BytesIO(buf.tobytes()))
        res = model.generate_content(["Bu kadr qaysi filmdan? O'zbek tilida ayt.", img])
        bot.edit_message_text(f"🎬 {res.text}", chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xatolik: {e}", chat_id, msg.message_id)

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    msg = bot.send_message(m.chat.id, "📸 Tahlil...")
    f = bot.get_file(m.photo[-1].file_id)
    d = bot.download_file(f.file_path)
    img = Image.open(io.BytesIO(d))
    res = model.generate_content(["Bu rasm qaysi filmdan?", img])
    bot.edit_message_text(f"✅ {res.text}", m.chat.id, msg.message_id)

bot.infinity_polling()
