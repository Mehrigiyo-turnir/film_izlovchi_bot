import os, threading, io, tempfile, re, requests, glob
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from PIL import Image
import google.generativeai as genai

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot OK")
def run_web():
    HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI)
model = genai.GenerativeModel('models/gemini-2.5-flash')
bot = telebot.TeleBot(TOKEN)
user_videos = {}

def get_id(url):
    m = re.search(r'(?:v=|shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else None

def download_yt(video_id, tmpdir):
    # 1. Piped API - eng ishonchlisi
    try:
        data = requests.get(f"https://pipedapi.kavin.rocks/streams/{video_id}", timeout=20).json()
        for s in data.get('videoStreams', []):
            if 'mp4' in s.get('mimeType','') and s.get('url'):
                url = s['url']
                r = requests.get(url, stream=True, timeout=60)
                path = f"{tmpdir}/video.mp4"
                with open(path, 'wb') as f:
                    for c in r.iter_content(1024*1024): f.write(c)
                if os.path.getsize(path) > 100000: return path
    except Exception as e:
        print("piped fail", e)
    
    # 2. Cobalt
    try:
        r = requests.post("https://api.cobalt.tools/api/json", json={"url": f"https://youtu.be/{video_id}", "vQuality": "720"},
                          headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=20).json()
        dl = r.get('url')
        if dl:
            v = requests.get(dl, stream=True, timeout=60)
            path = f"{tmpdir}/video.mp4"
            with open(path, 'wb') as f:
                for c in v.iter_content(1024*1024): f.write(c)
            return path
    except Exception as e:
        print("cobalt fail", e)
    return None

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "YouTube link tashlang, yuklab beraman!")

@bot.message_handler(content_types=['text'])
def handle(m):
    if 'http' not in m.text: return
    url = m.text.strip()
    yt_id = get_id(url)
    if not yt_id:
        bot.send_message(m.chat.id, "Bu YouTube link emasga o'xshaydi")
        return
    
    status = bot.send_message(m.chat.id, "📥 YouTube yuklanmoqda, 10 soniya...")
    tmp = tempfile.TemporaryDirectory()
    path = download_yt(yt_id, tmp.name)
    
    if not path or not os.path.exists(path):
        bot.edit_message_text("⚠️ YouTube bu videoni qattiq himoyalagan ekan. Iltimos boshqa YouTube video bilan sinab ko'ring yoki Insta/TikTok link tashlang.", m.chat.id, status.message_id)
        tmp.cleanup()
        return
    
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎬 Film nomi?", callback_data="find"))
        with open(path, 'rb') as v:
            sent = bot.send_video(m.chat.id, v, caption="✅ Yuklandi!", reply_markup=markup)
        user_videos[m.chat.id] = sent.video.file_id
        bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Yuborishda xato: {e}", m.chat.id, status.message_id)
    finally:
        tmp.cleanup()

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    msg = bot.send_message(chat_id, "🧠 Aniqlanmoqda...")
    try:
        import cv2
        f = bot.get_file(user_videos[chat_id])
        d = bot.download_file(f.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(d); p=tf.name
        cap = cv2.VideoCapture(p)
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
        ret, frame = cap.read()
        cap.release(); os.remove(p)
        _, buf = cv2.imencode('.jpg', frame)
        img = Image.open(io.BytesIO(buf.tobytes()))
        res = model.generate_content(["Bu kadr qaysi filmdan?", img])
        bot.edit_message_text(f"🎬 {res.text}", chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(str(e), chat_id, msg.message_id)

bot.infinity_polling()
