import os
import requests
import tempfile
from PIL import Image
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! 🎬 Kino dan rasm yoki 5 sekund video yuboring.")

def search_trace_moe(image_path):
    try:
        with open(image_path, 'rb') as f:
            r = requests.post('https://api.trace.moe/search', files={'image': f}, timeout=30)
        data = r.json()
        if data.get('result'):
            best = data['result'][0]
            if best['similarity'] > 0.80:
                return best
    except:
        pass
    return None

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await update.message.reply_text("⏳ Qidiryapman...")
    tmp_path = None
    try:
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
            tmp_path = tempfile.mktemp(suffix='.jpg')
            await file.download_to_drive(tmp_path)
        elif update.message.video:
            file = await update.message.video.get_file()
            tmp_path = tempfile.mktemp(suffix='.mp4')
            await file.download_to_drive(tmp_path)
        else:
            await status.edit_text("Iltimos rasm yuboring")
            return

        await status.edit_text("🔍 trace.moe da qidiryapman...")
        trace = search_trace_moe(tmp_path)
        if trace:
            sim = round(trace['similarity']*100, 1)
            await status.edit_text(f"✅ Topildi!\n🎬 {trace.get('filename')}\n🎯 {sim}%\n⏰ {int(trace.get('from',0))} sek")
            return

        await status.edit_text("🤖 Gemini qarayapti...")
        img = Image.open(tmp_path)
        resp = model.generate_content(["Bu qaysi kino? Nomini, yilini ayt, o'zbek tilida.", img])
        await status.edit_text(f"🤖 {resp.text}")

    except Exception as e:
        await status.edit_text(f"Xato: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle))
    app.run_polling()

if __name__ == "__main__":
    main()
