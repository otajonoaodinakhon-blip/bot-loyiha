import os
import json
import logging
import asyncio
import threading
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 5000))
MOVIES_FILE = 'movies.json'
MOVIES_PER_PAGE = 20

application = None
loop = None
bot_ready = threading.Event()

def load_movies():
    if os.path.exists(MOVIES_FILE):
        with open(MOVIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_movies(movies):
    with open(MOVIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    movies = load_movies()
    
    welcome_text = (
        f"🎬 <b>Kino Qidiruv Botiga Xush Kelibsiz!</b>\n\n"
        f"Salom, <b>{user_name}</b>! 👋\n\n"
        f"📽 Bizda <b>{len(movies)}</b> ta kino mavjud\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 <b>Qidiruv:</b> Kino nomini yozing\n"
        f"📋 <b>Yordam:</b> /help\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✨ Yoqtirgan kinongizni toping!"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID:
        help_text = (
            "⚙️ <b>ADMIN PANELI</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 /stats - Statistikani ko'rish\n"
            "🗑 /delete <code>&lt;id&gt;</code> - Kinoni o'chirish\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📥 <b>Kino qo'shish:</b>\n"
            "Kanaldan video/faylni forward qiling\n\n"
            "💡 <i>Caption yoki fayl nomi kino nomi sifatida saqlanadi</i>"
        )
    else:
        help_text = (
            "📖 <b>FOYDALANISH YO'RIQNOMASI</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 Kino nomini yozing\n"
            "📋 Ro'yxatdan tanlang\n"
            "📥 Kinoni yuklab oling\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 <b>Masalan:</b> <code>Avatar</code>\n\n"
            "✨ Yaxshi tomosha!"
        )
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    movies = load_movies()
    
    video_count = sum(1 for m in movies.values() if m.get('file_type') == 'video')
    doc_count = sum(1 for m in movies.values() if m.get('file_type') == 'document')
    audio_count = sum(1 for m in movies.values() if m.get('file_type') == 'audio')
    
    stats_text = (
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Jami fayllar: <b>{len(movies)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 Videolar: <b>{video_count}</b>\n"
        f"📄 Dokumentlar: <b>{doc_count}</b>\n"
        f"🎵 Audio: <b>{audio_count}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(stats_text, parse_mode='HTML')

async def delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Foydalanish:</b>\n<code>/delete &lt;kino_id&gt;</code>",
            parse_mode='HTML'
        )
        return
    
    movie_id = context.args[0]
    movies = load_movies()
    
    if movie_id in movies:
        movie_name = movies[movie_id].get('name', 'Nomsiz')
        del movies[movie_id]
        save_movies(movies)
        await update.message.reply_text(
            f"✅ <b>O'chirildi!</b>\n\n"
            f"🎬 {movie_name}\n"
            f"🆔 <code>{movie_id}</code>",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("❌ Kino topilmadi.", parse_mode='HTML')

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    message = update.message
    
    forward_origin = message.forward_origin
    if not forward_origin:
        await message.reply_text(
            "⚠️ <b>Xato!</b>\n\nIltimos, kanaldan forward qiling.",
            parse_mode='HTML'
        )
        return
    
    channel_id = None
    message_id = None
    
    if hasattr(forward_origin, 'chat'):
        channel_id = str(forward_origin.chat.id)
        message_id = forward_origin.message_id
    elif hasattr(forward_origin, 'sender_chat'):
        channel_id = str(forward_origin.sender_chat.id)
        message_id = getattr(forward_origin, 'message_id', None)
    
    if not channel_id:
        await message.reply_text(
            "⚠️ <b>Xato!</b>\n\nIltimos, kanaldan forward qiling.",
            parse_mode='HTML'
        )
        return
    
    file_id = None
    file_type = None
    file_emoji = ""
    caption = message.caption or ""
    file_name = ""
    
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
        file_emoji = "🎬"
        file_name = message.video.file_name or ""
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
        file_emoji = "📄"
        file_name = message.document.file_name or ""
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
        file_emoji = "🎵"
        file_name = message.audio.file_name or ""
    else:
        await message.reply_text(
            "⚠️ <b>Xato!</b>\n\nFaqat video, dokument yoki audio qabul qilinadi.",
            parse_mode='HTML'
        )
        return
    
    movie_name = caption if caption else file_name
    if not movie_name:
        await message.reply_text(
            "⚠️ <b>Xato!</b>\n\nKino nomi topilmadi.\nCaption yoki fayl nomini tekshiring.",
            parse_mode='HTML'
        )
        return
    
    movie_name = movie_name.strip()
    
    if message_id is None:
        message_id = hash(f"{channel_id}_{file_id}")
    
    movies = load_movies()
    movie_id = f"{channel_id}_{message_id}"
    
    movies[movie_id] = {
        "name": movie_name,
        "file_id": file_id,
        "file_type": file_type,
        "channel_id": channel_id,
        "message_id": message_id
    }
    
    save_movies(movies)
    
    success_text = (
        f"✅ <b>MUVAFFAQIYATLI SAQLANDI!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{file_emoji} <b>Nomi:</b> {movie_name}\n"
        f"🆔 <b>ID:</b> <code>{movie_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Jami kinolar: <b>{len(movies)}</b>"
    )
    
    await message.reply_text(success_text, parse_mode='HTML')

async def search_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()
    
    if len(query) < 2:
        await update.message.reply_text(
            "⚠️ Kamida <b>2 ta</b> harf kiriting.",
            parse_mode='HTML'
        )
        return
    
    movies = load_movies()
    results = []
    
    for movie_id, movie_data in movies.items():
        if query in movie_data['name'].lower():
            results.append((movie_id, movie_data))
    
    if not results:
        await update.message.reply_text(
            f"😔 <b>Hech narsa topilmadi</b>\n\n"
            f"🔍 So'rov: <code>{query}</code>\n\n"
            f"💡 Boshqa nom bilan qidirib ko'ring",
            parse_mode='HTML'
        )
        return
    
    total = len(results)
    page = 0
    start_idx = page * MOVIES_PER_PAGE
    end_idx = start_idx + MOVIES_PER_PAGE
    page_results = results[start_idx:end_idx]
    
    keyboard = []
    for idx, (movie_id, movie_data) in enumerate(page_results, start=1):
        file_type = movie_data.get('file_type', 'video')
        emoji = "🎬" if file_type == "video" else "📄" if file_type == "document" else "🎵"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {movie_data['name'][:45]}",
            callback_data=f"get_{movie_id}"
        )])
    
    nav_buttons = []
    if end_idx < total:
        nav_buttons.append(InlineKeyboardButton(
            f"Keyingi ({total - end_idx}) ▶️",
            callback_data=f"page_{page + 1}_{query}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    result_text = (
        f"🔍 <b>QIDIRUV NATIJALARI</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Topildi: <b>{total}</b> ta\n"
        f"📄 Sahifa: <b>{page + 1}</b> / <b>{(total - 1) // MOVIES_PER_PAGE + 1}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 Kinoni tanlang:"
    )
    
    await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("get_"):
        movie_id = data[4:]
        movies = load_movies()
        
        if movie_id not in movies:
            await query.edit_message_text(
                "❌ <b>Kino topilmadi</b>\n\nEhtimol o'chirilgan.",
                parse_mode='HTML'
            )
            return
        
        movie = movies[movie_id]
        file_id = movie['file_id']
        file_type = movie['file_type']
        
        emoji = "🎬" if file_type == "video" else "📄" if file_type == "document" else "🎵"
        caption = f"{emoji} <b>{movie['name']}</b>"
        
        try:
            if file_type == "video":
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=file_id,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif file_type == "document":
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file_id,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif file_type == "audio":
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=file_id,
                    caption=caption,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await query.message.reply_text(
                "❌ <b>Xatolik!</b>\n\nFaylni yuborishda muammo. Keyinroq urinib ko'ring.",
                parse_mode='HTML'
            )
    
    elif data.startswith("page_"):
        parts = data.split("_", 2)
        page = int(parts[1])
        search_query = parts[2]
        
        movies = load_movies()
        results = []
        
        for movie_id, movie_data in movies.items():
            if search_query in movie_data['name'].lower():
                results.append((movie_id, movie_data))
        
        total = len(results)
        start_idx = page * MOVIES_PER_PAGE
        end_idx = start_idx + MOVIES_PER_PAGE
        page_results = results[start_idx:end_idx]
        
        keyboard = []
        for movie_id, movie_data in page_results:
            file_type = movie_data.get('file_type', 'video')
            emoji = "🎬" if file_type == "video" else "📄" if file_type == "document" else "🎵"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {movie_data['name'][:45]}",
                callback_data=f"get_{movie_id}"
            )])
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                "◀️ Oldingi",
                callback_data=f"page_{page - 1}_{search_query}"
            ))
        if end_idx < total:
            nav_buttons.append(InlineKeyboardButton(
                f"Keyingi ▶️",
                callback_data=f"page_{page + 1}_{search_query}"
            ))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        result_text = (
            f"🔍 <b>QIDIRUV NATIJALARI</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Topildi: <b>{total}</b> ta\n"
            f"📄 Sahifa: <b>{page + 1}</b> / <b>{(total - 1) // MOVIES_PER_PAGE + 1}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👇 Kinoni tanlang:"
        )
        
        await query.edit_message_text(result_text, reply_markup=reply_markup, parse_mode='HTML')

def create_application():
    global application
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return None
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("delete", delete_movie))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movies))
    
    return application

def get_webhook_url():
    if WEBHOOK_URL:
        return WEBHOOK_URL
    
    replit_domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
    if replit_domain:
        return f"https://{replit_domain}/webhook"
    
    railway_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if railway_domain:
        return f"https://{railway_domain}/webhook"
    
    render_domain = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
    if render_domain:
        return f"https://{render_domain}/webhook"
    
    heroku_app = os.environ.get('HEROKU_APP_NAME')
    if heroku_app:
        return f"https://{heroku_app}.herokuapp.com/webhook"
    
    return None

async def run_bot_loop():
    global application, loop
    loop = asyncio.get_event_loop()
    
    application = create_application()
    if application is None:
        logger.error("Failed to create application")
        return
    
    await application.initialize()
    await application.start()
    
    webhook_url = get_webhook_url()
    if webhook_url:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                await application.bot.set_webhook(webhook_url)
                logger.info(f"Webhook set to: {webhook_url}")
                break
            except Exception as e:
                if "Retry" in str(e) or "429" in str(e):
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Webhook error: {e}")
                    break
    else:
        logger.error("No webhook URL found. Set WEBHOOK_URL environment variable.")
    
    bot_ready.set()
    logger.info("Bot is ready to receive updates")
    
    while True:
        await asyncio.sleep(3600)

def start_bot_thread():
    def run():
        global loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot_loop())
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()

@app.route('/webhook', methods=['POST'])
def webhook():
    global application, loop
    
    if application is None or loop is None:
        logger.error("Application not initialized")
        return 'Bot not ready', 500
    
    if not application.running:
        logger.error("Application not running")
        return 'Bot not running', 500
    
    try:
        update = Update.de_json(request.get_json(), application.bot)
        future = asyncio.run_coroutine_threadsafe(
            application.process_update(update), 
            loop
        )
        future.result(timeout=30)
        return 'ok'
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'error', 500

@app.route('/')
def index():
    return '🎬 Kino Bot ishlamoqda!'

@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    if BOT_TOKEN:
        start_bot_thread()
        bot_ready.wait(timeout=15)
    else:
        logger.warning("BOT_TOKEN not set. Webhook not configured.")
    
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
