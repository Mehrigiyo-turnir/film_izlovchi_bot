import os, threading, io, glob, tempfile, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from PIL import Image
from google import genai

class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
def run_web():
    HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_web, daemon=True).start()

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
bot = telebot.TeleBot(TOKEN)
user_videos = {}

@bot.message_handler(commands=['start'])
def start(m): bot.send_message(m.chat.id, "Salom! Link tashlang!")

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
            kb.add(types.InlineKeyboardButton("🎬 Film nomi?", callback_data="find"))
            with open(path, 'rb') as v:
                sent = bot.send_video(m.chat.id, v, caption="✅", reply_markup=kb)
            user_videos[m.chat.id] = sent.video.file_id
            bot.delete_message(m.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", m.chat.id, status.message_id)

def ask_groq(frames, prompt):
    from groq import Groq
    client = Groq(api_key=GROQ_KEY)
    content = [{"type": "text", "text": prompt}]
    for img in frames[:4]:
        buf = io.BytesIO(); img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    # HOZIRGI KUNDA ISHLAYDIGAN ENG YANGI MODEL
    res = client.chat.completions.create(
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        messages=[{"role": "user", "content": content}],
        max_tokens=700
    )
    return res.choices[0].message.content

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    chat_id = call.message.chat.id
    if chat_id not in user_videos: return
    bot.answer_callback_query(call.id, "Tekshirilmoqda...")
    msg = bot.send_message(chat_id, "🧠 Gemini tekshirmoqda...")
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
        prompt = "Bu kadrlardagi film/serial nomini, yilini o'zbek tilida ayt."

        try:
            res = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=[prompt] + frames[:4])
            bot.edit_message_text(f"🎬 Gemini:\n{res.text}", chat_id, msg.message_id)
            return
        except Exception as e:
            print(f"Gemini xato: {e}")
            bot.edit_message_text(f"⚠️ Gemini xato, Groq ga o'tilmoqda...", chat_id, msg.message_id)

        if GROQ_KEY:
            answer = ask_groq(frames, prompt)
            bot.edit_message_text(f"🎬 Groq topdi:\n{answer}", chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"Xato: {e}", chat_id, msg.message_id)

bot.infinity_polling()
