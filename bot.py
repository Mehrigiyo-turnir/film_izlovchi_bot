import os
import requests
import tempfile
import yt_dlp
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Kalitlarni Render dan oladi
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! 🎬 Menga kino dan video / rasm yoki Instagram link tashlang.\n"
        "Men avval trace.moe da, topolmasam Gemini AI da qidiraman."
    )

def search_trace_moe(image_path):
    try:
        with open(image_path, 'rb') as f:
            r = requests.post('https://api.trace.moe/search', files={'image': f}, timeout=20)
        data = r.json()
        if data.get('result') and len(data['result']) > 0:
            best = data['result'][0]
            # similarity 85% dan yuqori bo'lsa aniq topildi deb olamiz
            if best['similarity'] > 0.85:
                return best
    except Exception as e:
        print(f"trace.moe xato: {e}")
    return None

def search_gemini(image_path, caption="Bu qaysi kino yoki serialdan?"):
    try:
        img = genai.upload_file(image_path)
        prompt = f"""
        Sen kino mutaxassisisan. Rasmni ko'rib qaysi kino/serial ekanini top.
        Agar topsang: Nomi, Yili, Qisqacha syujeti, Aktyorlari haqida o'zbek tilida javob ber.
        Agar topolmasang halol ayt.
        Savol: {caption}
        """
        response = model.generate_content([img, prompt])
        return response.text
    except Exception as e:
        print(f"Gemini xato: {e}")
        return f"Gemini da xato: {e}"

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Qidiryapman... avval trace.moe tekshirilmoqda")

    tmp_path = None
    try:
        # Faylni yuklab olish
        if update.message.video or update.message.document:
            file = await (update.message.video or update.message.document).get_file()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tmp_path = tmp.name
            await file.download_to_drive(tmp_path)
            # Videodan rasm olish uchun yt-dlp bilan emas, oddiy yo'l - trace.moe videoni ham qabul qiladi
            # Lekin biz birinchi kadrni rasm qilib jo'natamiz - soddalik uchun shu videoni rasm sifatida yuboramiz
            # trace.moe API rasm kutadi, shuning uchun biz videodan screenshot ololmaymiz, Gemini ga beramiz
            # Shuning uchun video bo'lsa to'g'ridan to'g'ri Gemini ga o'tkazamiz yoki trace.moe uchun rasm ajratib olamiz
            # Hozircha Gemini ga beramiz va trace.moe ni ham sinab ko'ramiz
            image_for_search = tmp_path

        elif update.message.photo:
            file = await update.message.photo[-1].get_file()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            tmp_path = tmp.name
            await file.download_to_drive(tmp_path)
            image_for_search = tmp_path

        else: # Link bo'lsa
            text = update.message.text
            if "instagram.com" in text or "tiktok.com" in text or "youtu" in text:
                await msg.edit_text("🔗 Link yuklanmoqda...")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                tmp_path = tmp.name
                ydl_opts = {'outtmpl': tmp_path, 'format': 'mp4', 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([text])
                image_for_search = tmp_path
            else:
                await msg.edit_text("Iltimos video, rasm yoki link tashlang")
                return

        # 1-QADAM: trace.moe
        await msg.edit_text("🔍 trace.moe da qidiryapman...")
        trace_result = search_trace_moe(image_for_search)

        if trace_result:
            title = trace_result.get('filename', 'Noma\'lum')
            anilist = trace_result.get('anilist', {})
            sim = round(trace_result['similarity']*100, 2)
            from_sec = int(trace_result.get('from', 0))
            m, s = divmod(from_sec, 60)
            h, m = divmod(m, 60)
            await msg.edit_text(
                f"✅ trace.moe topdi!\n\n"
                f"🎬 Nomi: {title}\n"
                f"🎯 O'xshashlik: {sim}%\n"
                f"⏰ Sahna vaqti: {h:02}:{m:02}:{s:02}\n"
                f"📊 Aniqlik: Juda yuqori"
            )
            return

        # 2-QADAM: topolmasa Gemini
        await msg.edit_text("🤖 trace.moe topolmadi, Gemini AI ga berdim...")
        gemini_answer = search_gemini(image_for_search)
        await msg.edit_text(f"🤖 Gemini AI javobi:\n\n{gemini_answer}")

    except Exception as e:
        await msg.edit_text(f"Xato bo'ldi: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except: pass

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO | filters.Document.ALL | filters.TEXT & ~filters.COMMAND, handle_media))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
