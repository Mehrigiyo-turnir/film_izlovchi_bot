#... tepadagi kodlar bir xil qolsin...
# faqat handle_other funksiyasini bunga almashtiring:

@bot.message_handler(content_types=['video', 'text'])
def handle_other(m):
    if not check_access(m): return
    if m.content_type == 'text' and 'http' not in m.text.lower(): return

    url = m.text if m.content_type == 'text' else None

    if url:
        status = bot.send_message(m.chat.id, f"🔗 Link qabul qilindi...\n⏳ Yuklanmoqda 20%")
        bot.send_chat_action(m.chat.id, 'typing')
        try:
            import yt_dlp, cv2, tempfile
            bot.edit_message_text("🔗 Link qabul qilindi...\n📥 Video yuklanmoqda 50%...", m.chat.id, status.message_id)

            with tempfile.TemporaryDirectory() as tmpdir:
                ydl_opts = {'outtmpl': f'{tmpdir}/video.%(ext)s', 'format': 'best[height<=480]', 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_path = ydl.prepare_filename(info).replace('.webm','.mp4').replace('.mkv','.mp4')
                    # faylni topish
                    import glob
                    files = glob.glob(f"{tmpdir}/*")
                    if not files: raise Exception("Video yuklanmadi")
                    video_path = files[0]

                bot.edit_message_text("🔗 Link qabul qilindi...\n🔍 Kadr olinmoqda 75%...", m.chat.id, status.message_id)
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_MSEC, 1000) # 1-sekunddan kadr ol
                ret, frame = cap.read()
                if not ret: raise Exception("Kadr olinmadi")
                _, buffer = cv2.imencode('.jpg', frame)
                image = Image.open(io.BytesIO(buffer.tobytes()))

                bot.edit_message_text("🔗 Link qabul qilindi...\n🧠 AI tahlil qilmoqda 90%...", m.chat.id, status.message_id)
                response = model.generate_content(["Bu kadr qaysi filmdan? Nomini va yilini ayt, o'zbek tilida", image])
                bot.edit_message_text(f"✅ Tayyor!\n\n{response.text}", m.chat.id, status.message_id)

        except Exception as e:
            bot.edit_message_text(f"⚠️ Linkni yuklab bo'lmadi: {e}\n\nIltimos shu videodan screenshot olib tashlang, 100% topaman!", m.chat.id, status.message_id)
