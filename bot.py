import os, threading, io, glob, tempfile, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from PIL import Image

class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
def run_web():
    HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_KEY_2 = os.environ.get("GEMINI_API_KEY_2")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")

from google import genai

bot = telebot.TeleBot(TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "Salom! Link tashlang, 3 ta AI tekshiradi!")

@bot.message_handler(content_types=['text'])
def handle(m):
    if 'http' not in m.text: return
    status = bot.send_message(m.chat.id, "📥 Yuklanmoqda...")
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best', 'quiet': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(m.text.strip(), download=True)
                path = glob.glob(f"{tmpdir}/*")[0]
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🎬 Film nomi? (3x AI)", callback_data="find"))
            with open(path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅ Yuklandi!", reply_markup=kb)
            user_videos[m.chat.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", m.chat.id, status.message_id)

def ask_gemini(frames, prompt, api_key):
    client = genai.Client(api_key=api_key)
    res = client.models.generate_content(model="gemini-2.0-flash", contents=[prompt] + frames[:4])
    return res.text

def ask_openrouter(frames, prompt):
    import requests
    images_b64 = []
    for img in frames[:4]:
        buf = io.BytesIO(); img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        images_b64.append(f"data:image/jpeg;base64,{b64}")

    content = [{"type": "text", "text": prompt}]
    for b64 in images_b64:
        content.append({"type": "image_url", "image_url": {"url": b64}})

    # Hozirda ishlaydigan bepul vision modellar ro'yxati
    models = [
        "qwen/qwen2.5-vl-7b-instruct:free",
        "google/gemma-3-27b-it:free",
        "meta-llama/llama-4-maverick:free",
        "nvidia/nemotron-nano-12b-v2-vl:free"
    ]

    for model_id in models:
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "HTTP-Referer": "https://render.com",
                    "X-Title": "Film Bot"
                },
                json={"model": model_id, "messages": [{"role": "user", "content": content}]},
                timeout=40
            )
            if r.status_code == 200:
                return f"[{model_id}] " + r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"{model_id} xato {e}")
            continue
    return None

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    bot.answer_callback_query(call.id, "3 ta AI ishlamoqda...")
    msg = bot.send_message(chat_id, "🧠 1-AI Gemini tekshirmoqda...")

    try:
        import cv2
        f = bot.get_file(user_videos[chat_id]); d = bot.download_file(f.file_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tf:
            tf.write(d); p=tf.name
        cap = cv2.VideoCapture(p); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        frames = []
        for i in range(10):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total*(i+1)/11))
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                frames.append(Image.open(io.BytesIO(buf.tobytes())))
        cap.release(); os.remove(p)
        prompt = "Bu kadrlardagi film yoki serial nomini, yilini, janrini o'zbek tilida top."

        # 1-AI: GEMINI 1
        try:
            txt = ask_gemini(frames, prompt, GEMINI_KEY)
            bot.edit_message_text(f"🎬 Gemini 1 topdi:\n{txt}", chat_id, msg.message_id)
            return
        except Exception as e:
            print(f"Gemini1 xato: {e}")

        # 2-AI: GEMINI 2
        if GEMINI_KEY_2:
            try:
                bot.edit_message_text("⚠️ Gemini 1 limit, 2-Gemini tekshirmoqda...", chat_id, msg.message_id)
                txt = ask_gemini(frames, prompt, GEMINI_KEY_2)
                bot.edit_message_text(f"🎬 Gemini 2 topdi:\n{txt}", chat_id, msg.message_id)
                return
            except Exception as e:
                print(f"Gemini2 xato: {e}")

        # 3-AI: OPENROUTER BEPUL
        bot.edit_message_text("⚠️ Gemini limit, OpenRouter bepul AI ga o'tildi...", chat_id, msg.message_id)
        txt = ask_openrouter(frames, prompt)
        if txt:
            bot.edit_message_text(f"🎬 OpenRouter topdi:\n{txt}", chat_id, msg.message_id)
        else:
            bot.edit_message_text("❌ Hozir 3 ta AI ham limitda, 1 daqiqadan keyin qayta bosing.", chat_id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", chat_id, msg.message_id)

bot.infinity_polling()
