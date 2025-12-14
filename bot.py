import os
import logging
import asyncio
import threading
import random
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from models import db, Movie

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "kino-bot-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

with app.app_context():
    db.create_all()

BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 5000))
MOVIES_PER_PAGE = 20

application = None
loop = None
bot_ready = threading.Event()

def load_movies():
    with app.app_context():
        movies = Movie.query.all()
        return {m.movie_id: m.to_dict() for m in movies}

def save_movie(movie_id, name, file_id, file_type, channel_id, message_id):
    with app.app_context():
        existing = Movie.query.filter_by(movie_id=movie_id).first()
        if existing:
            existing.name = name
            existing.file_id = file_id
            existing.file_type = file_type
            existing.channel_id = channel_id
            existing.message_id = message_id
        else:
            movie = Movie(
                movie_id=movie_id,
                name=name,
                file_id=file_id,
                file_type=file_type,
                channel_id=channel_id,
                message_id=message_id
            )
            db.session.add(movie)
        db.session.commit()

def delete_movie_by_id(movie_id):
    with app.app_context():
        movie = Movie.query.filter_by(movie_id=movie_id).first()
        if movie:
            name = movie.name
            db.session.delete(movie)
            db.session.commit()
            return name
        return None

def get_movie_count():
    with app.app_context():
        return Movie.query.count()

def get_movies_by_type():
    with app.app_context():
        video_count = Movie.query.filter_by(file_type='video').count()
        doc_count = Movie.query.filter_by(file_type='document').count()
        audio_count = Movie.query.filter_by(file_type='audio').count()
        return video_count, doc_count, audio_count

def search_movies_db(query):
    with app.app_context():
        movies = Movie.query.filter(Movie.name.ilike(f'%{query}%')).all()
        return [(m.movie_id, m.to_dict()) for m in movies]

def get_movie_by_id(movie_id):
    with app.app_context():
        movie = Movie.query.filter_by(movie_id=movie_id).first()
        if movie:
            return movie.to_dict()
        return None

def get_all_movies():
    with app.app_context():
        movies = Movie.query.order_by(Movie.created_at.desc()).all()
        return [(m.movie_id, m.to_dict()) for m in movies]

def get_random_movie():
    with app.app_context():
        count = Movie.query.count()
        if count == 0:
            return None, None
        offset = random.randint(0, count - 1)
        movie = Movie.query.offset(offset).first()
        if movie:
            return movie.movie_id, movie.to_dict()
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    movie_count = get_movie_count()
    video_count, doc_count, audio_count = get_movies_by_type()

    welcome_text = (
        f"╔══════════════════════════════╗\n"
        f"     🎬 <b>KINO QIDIRUV BOT</b> 🎬\n"
        f"╚══════════════════════════════╝\n\n"
        f"Assalomu alaykum, <b>{user_name}</b>! 👋\n\n"
        f"🏠 <b>Premium Kino Kutubxonasi</b>\n"
        f"┌─────────────────────────────┐\n"
        f"│  📊 Jami: <b>{movie_count}</b> ta kontent      │\n"
        f"│  🎬 Videolar: <b>{video_count}</b>              │\n"
        f"│  📄 Dokumentlar: <b>{doc_count}</b>            │\n"
        f"│  🎵 Audiolar: <b>{audio_count}</b>              │\n"
        f"└─────────────────────────────┘\n\n"
        f"💎 <b>IMKONIYATLAR:</b>\n"
        f"├ 🔍 Tez qidiruv\n"
        f"├ 🎲 Tasodifiy kino\n"
        f"├ 📋 To'liq ro'yxat\n"
        f"└ ⚡ Bir zumda yuklash\n\n"
        f"✨ <i>Kino nomini yozing yoki tugmalardan foydalaning!</i>"
    )

    keyboard = [
        [
            InlineKeyboardButton("📋 Barcha Kinolar ", callback_data="cmd_list"),
            InlineKeyboardButton("🎲 Tasodifiy", callback_data="cmd_random")
        ],
        [
            InlineKeyboardButton("ℹ️ Bot haqida", callback_data="cmd_about"),
            InlineKeyboardButton("📖 Yordam", callback_data="cmd_help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id == ADMIN_ID:
        help_text = (
            "╔══════════════════════════════╗\n"
            "      ⚙️ <b>ADMIN PANELI</b> ⚙️\n"
            "╚══════════════════════════════╝\n\n"
            "🔐 <b>BOSHQARUV BUYRUQLARI:</b>\n"
            "┌─────────────────────────────┐\n"
            "│ 📊 /stats - Statistika        │\n"
            "│ 📋 /list - Kinolar ro'yxati   │\n"
            "│ 🗑 /delete ID - O'chirish     │\n"
            "└─────────────────────────────┘\n\n"
            "📥 <b>KINO QO'SHISH:</b>\n"
            "├ Kanaldan video/fayl forward qiling\n"
            "├ Caption = Kino nomi\n"
            "└ Avtomatik saqlanadi\n\n"
            "💡 <i>ID: kanaldagi xabar IDsi</i>"
        )
    else:
        help_text = (
            "╔══════════════════════════════╗\n"
            "      📖 <b>YORDAM</b> 📖\n"
            "╚══════════════════════════════╝\n\n"
            "🎯 <b>QANDAY FOYDALANISH:</b>\n"
            "┌─────────────────────────────┐\n"
            "│ 1️⃣ Kino nomini yozing         │\n"
            "│ 2️⃣ Ro'yxatdan tanlang         │\n"
            "│ 3️⃣ Yuklab oling!               │\n"
            "└─────────────────────────────┘\n\n"
            "⚡ <b>TEZ BUYRUQLAR:</b>\n"
            "├ /start - Bosh sahifa\n"
            "├ /list - To'liq ro'yxat\n"
            "├ /random - Tasodifiy kino\n"
            "└ /about - Bot haqida\n\n"
            "💡 <b>Masalan:</b> <code>Avatar</code>\n\n"
            "🍿 <i>Yaxshi tomosha!</i>"
        )

    await update.message.reply_text(help_text, parse_mode='HTML')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movie_count = get_movie_count()
    video_count, doc_count, audio_count = get_movies_by_type()
    
    about_text = (
        "╔══════════════════════════════╗\n"
        "      ℹ️ <b>BOT HAQIDA</b> ℹ️\n"
        "╚══════════════════════════════╝\n\n"
        "🎬 <b>Kino Qidiruv Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Bu bot orqali siz eng yaxshi kinolarni\n"
        "qidirib topishingiz va yuklab olishingiz\n"
        "mumkin. Tez, qulay va bepul!\n\n"
        "📊 <b>STATISTIKA:</b>\n"
        f"├ 📁 Jami: <b>{movie_count}</b> ta\n"
        f"├ 🎬 Videolar: <b>{video_count}</b>\n"
        f"├ 📄 Dokumentlar: <b>{doc_count}</b>\n"
        f"└ 🎵 Audiolar: <b>{audio_count}</b>\n\n"
        "⚙️ <b>TEXNOLOGIYALAR:</b>\n"
        "├ Python + Telegram Bot API\n"
        "├ PostgreSQL Database\n"
        "└ Flask Web Framework\n\n"
        "🚀 <b>Versiya:</b> 2.0 Premium\n\n"
        "💎 <i>Har kuni yangi kinolar!</i>"
    )
    
    keyboard = [[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="cmd_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(about_text, reply_markup=reply_markup, parse_mode='HTML')

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movie_id, movie = get_random_movie()
    
    if not movie:
        await update.message.reply_text(
            "📭 <b>Kinolar ro'yxati bo'sh</b>\n\n"
            "Hozircha hech qanday kino qo'shilmagan.",
            parse_mode='HTML'
        )
        return
    
    file_id = movie['file_id']
    file_type = movie['file_type']
    movie_name = movie['name']
    
    emoji = "🎬" if file_type == "video" else "📄" if file_type == "document" else "🎵"
    caption = (
        f"🎲 <b>TASODIFIY KINO</b>\n\n"
        f"{emoji} <b>{movie_name}</b>\n\n"
        f"💎 <i>Yana birini olish: /random</i>"
    )
    
    try:
        if file_type == "video":
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=file_id,
                caption=caption,
                parse_mode='HTML'
            )
        elif file_type == "document":
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file_id,
                caption=caption,
                parse_mode='HTML'
            )
        elif file_type == "audio":
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=file_id,
                caption=caption,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Error sending random file: {e}")
        await update.message.reply_text(
            "❌ <b>Xatolik!</b>\n\n"
            "Faylni yuborishda muammo. /random qayta urinib ko'ring.",
            parse_mode='HTML'
        )

async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = get_all_movies()
    total = len(movies)
    
    if total == 0:
        await update.message.reply_text(
            "📭 <b>Kinolar ro'yxati bo'sh</b>\n\n"
            "Hozircha hech qanday kino qo'shilmagan.",
            parse_mode='HTML'
        )
        return
    
    page = 0
    start_idx = page * MOVIES_PER_PAGE
    end_idx = start_idx + MOVIES_PER_PAGE
    page_results = movies[start_idx:end_idx]
    
    keyboard = []
    for movie_id, movie_data in page_results:
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
            callback_data=f"list_{page + 1}"
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    result_text = (
        f"📋 <b>KINOLAR RO'YXATI</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Jami: <b>{total}</b> ta\n"
        f"📄 Sahifa: <b>{page + 1}</b> / <b>{(total - 1) // MOVIES_PER_PAGE + 1}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 Kinoni tanlang:"
    )
    
    await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='HTML')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return

    total = get_movie_count()
    video_count, doc_count, audio_count = get_movies_by_type()

    stats_text = (
        "╔══════════════════════════════╗\n"
        "     📊 <b>BOT STATISTIKASI</b> 📊\n"
        "╚══════════════════════════════╝\n\n"
        "📁 <b>KONTENT MA'LUMOTLARI</b>\n"
        "┌─────────────────────────────┐\n"
        f"│  📊 Jami: <b>{total}</b> ta fayl          │\n"
        f"│  🎬 Videolar: <b>{video_count}</b>              │\n"
        f"│  📄 Dokumentlar: <b>{doc_count}</b>            │\n"
        f"│  🎵 Audiolar: <b>{audio_count}</b>              │\n"
        "└─────────────────────────────┘\n\n"
        "💎 <i>Premium Kino Bot v2.0</i>"
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
    movie_name = delete_movie_by_id(movie_id)

    if movie_name:
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

    movie_id = f"{channel_id}_{message_id}"
    
    save_movie(movie_id, movie_name, file_id, file_type, channel_id, str(message_id))
    total = get_movie_count()

    success_text = (
        f"✅ <b>MUVAFFAQIYATLI SAQLANDI!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{file_emoji} <b>Nomi:</b> {movie_name}\n"
        f"🆔 <b>ID:</b> <code>{movie_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Jami kinolar: <b>{total}</b>"
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

    results = search_movies_db(query)

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
    for movie_id, movie_data in page_results:
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
        movie = get_movie_by_id(movie_id)

        if not movie:
            await query.edit_message_text(
                "❌ <b>Kino topilmadi</b>\n\nEhtimol o'chirilgan.",
                parse_mode='HTML'
            )
            return

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

        results = search_movies_db(search_query)

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
    
    elif data.startswith("list_"):
        page = int(data.split("_")[1])
        
        movies = get_all_movies()
        total = len(movies)
        start_idx = page * MOVIES_PER_PAGE
        end_idx = start_idx + MOVIES_PER_PAGE
        page_results = movies[start_idx:end_idx]
        
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
                callback_data=f"list_{page - 1}"
            ))
        if end_idx < total:
            nav_buttons.append(InlineKeyboardButton(
                f"Keyingi ▶️",
                callback_data=f"list_{page + 1}"
            ))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        result_text = (
            f"📋 <b>KINOLAR RO'YXATI</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Jami: <b>{total}</b> ta\n"
            f"📄 Sahifa: <b>{page + 1}</b> / <b>{(total - 1) // MOVIES_PER_PAGE + 1}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👇 Kinoni tanlang:"
        )
        
        await query.edit_message_text(result_text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif data == "cmd_list":
        movies = get_all_movies()
        total = len(movies)
        
        if total == 0:
            await query.edit_message_text(
                "📭 <b>Kinolar ro'yxati bo'sh</b>\n\n"
                "Hozircha hech qanday kino qo'shilmagan.",
                parse_mode='HTML'
            )
            return
        
        page = 0
        start_idx = page * MOVIES_PER_PAGE
        end_idx = start_idx + MOVIES_PER_PAGE
        page_results = movies[start_idx:end_idx]
        
        keyboard = []
        for movie_id, movie_data in page_results:
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
                callback_data=f"list_{page + 1}"
            ))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="cmd_start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        result_text = (
            f"╔══════════════════════════════╗\n"
            f"     📋 <b>KINOLAR RO'YXATI</b> 📋\n"
            f"╚══════════════════════════════╝\n\n"
            f"📊 Jami: <b>{total}</b> ta\n"
            f"📄 Sahifa: <b>{page + 1}</b> / <b>{(total - 1) // MOVIES_PER_PAGE + 1}</b>\n\n"
            f"👇 Kinoni tanlang:"
        )
        
        await query.edit_message_text(result_text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif data == "cmd_random":
        movie_id, movie = get_random_movie()
        
        if not movie:
            await query.edit_message_text(
                "📭 <b>Kinolar ro'yxati bo'sh</b>\n\n"
                "Hozircha hech qanday kino qo'shilmagan.",
                parse_mode='HTML'
            )
            return
        
        file_id = movie['file_id']
        file_type = movie['file_type']
        movie_name = movie['name']
        
        emoji = "🎬" if file_type == "video" else "📄" if file_type == "document" else "🎵"
        caption = (
            f"🎲 <b>TASODIFIY KINO</b>\n\n"
            f"{emoji} <b>{movie_name}</b>\n\n"
            f"💎 <i>Yana birini olish: /random</i>"
        )
        
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
            logger.error(f"Error sending random file: {e}")
            await query.message.reply_text(
                "❌ <b>Xatolik!</b>\n\nFaylni yuborishda muammo.",
                parse_mode='HTML'
            )
    
    elif data == "cmd_about":
        movie_count = get_movie_count()
        video_count, doc_count, audio_count = get_movies_by_type()
        
        about_text = (
            "╔══════════════════════════════╗\n"
            "      ℹ️ <b>BOT HAQIDA</b> ℹ️\n"
            "╚══════════════════════════════╝\n\n"
            "🎬 <b>Kino Qidiruv Bot</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Bu bot orqali siz eng yaxshi kinolarni\n"
            "qidirib topishingiz va yuklab olishingiz\n"
            "mumkin. Tez, qulay va bepul!\n\n"
            "📊 <b>STATISTIKA:</b>\n"
            f"├ 📁 Jami: <b>{movie_count}</b> ta\n"
            f"├ 🎬 Videolar: <b>{video_count}</b>\n"
            f"├ 📄 Dokumentlar: <b>{doc_count}</b>\n"
            f"└ 🎵 Audiolar: <b>{audio_count}</b>\n\n"
            "🚀 <b>Versiya:</b> 2.0 Premium\n\n"
            "💎 <i>Har kuni yangi kinolar!</i>"
        )
        
        keyboard = [[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="cmd_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(about_text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif data == "cmd_help":
        user_id = str(query.from_user.id)
        
        if user_id == ADMIN_ID:
            help_text = (
                "╔══════════════════════════════╗\n"
                "      ⚙️ <b>ADMIN PANELI</b> ⚙️\n"
                "╚══════════════════════════════╝\n\n"
                "🔐 <b>BOSHQARUV BUYRUQLARI:</b>\n"
                "├ 📊 /stats - Statistika\n"
                "├ 📋 /list - Kinolar ro'yxati\n"
                "└ 🗑 /delete ID - O'chirish\n\n"
                "📥 <b>KINO QO'SHISH:</b>\n"
                "Kanaldan video/fayl forward qiling"
            )
        else:
            help_text = (
                "╔══════════════════════════════╗\n"
                "      📖 <b>YORDAM</b> 📖\n"
                "╚══════════════════════════════╝\n\n"
                "🎯 <b>QANDAY FOYDALANISH:</b>\n"
                "├ 1️⃣ Kino nomini yozing\n"
                "├ 2️⃣ Ro'yxatdan tanlang\n"
                "└ 3️⃣ Yuklab oling!\n\n"
                "⚡ <b>TEZ BUYRUQLAR:</b>\n"
                "├ /start - Bosh sahifa\n"
                "├ /list - To'liq ro'yxat\n"
                "├ /random - Tasodifiy kino\n"
                "└ /about - Bot haqida\n\n"
                "🍿 <i>Yaxshi tomosha!</i>"
            )
        
        keyboard = [[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="cmd_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif data == "cmd_start":
        user_name = query.from_user.first_name
        movie_count = get_movie_count()
        video_count, doc_count, audio_count = get_movies_by_type()
        
        welcome_text = (
            f"╔══════════════════════════════╗\n"
            f"     🎬 <b>KINO QIDIRUV BOT</b> 🎬\n"
            f"╚══════════════════════════════╝\n\n"
            f"Assalomu alaykum, <b>{user_name}</b>! 👋\n\n"
            f"🏠 <b>Premium Kino Kutubxonasi</b>\n"
            f"┌─────────────────────────────┐\n"
            f"│  📊 Jami: <b>{movie_count}</b> ta kontent      │\n"
            f"│  🎬 Videolar: <b>{video_count}</b>              │\n"
            f"│  📄 Dokumentlar: <b>{doc_count}</b>            │\n"
            f"│  🎵 Audiolar: <b>{audio_count}</b>              │\n"
            f"└─────────────────────────────┘\n\n"
            f"💎 <b>IMKONIYATLAR:</b>\n"
            f"├ 🔍 Tez qidiruv\n"
            f"├ 🎲 Tasodifiy kino\n"
            f"├ 📋 To'liq ro'yxat\n"
            f"└ ⚡ Bir zumda yuklash\n\n"
            f"✨ <i>Kino nomini yozing yoki tugmalardan foydalaning!</i>"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📋 Ro'yxat", callback_data="cmd_list"),
                InlineKeyboardButton("🎲 Tasodifiy", callback_data="cmd_random")
            ],
            [
                InlineKeyboardButton("ℹ️ Bot haqida", callback_data="cmd_about"),
                InlineKeyboardButton("📖 Yordam", callback_data="cmd_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

def create_application():
    global application
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return None

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("list", list_movies))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("random", random_command))
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

if BOT_TOKEN:
    start_bot_thread()

if __name__ == '__main__':
    if BOT_TOKEN:
        bot_ready.wait(timeout=15)
    else:
        logger.warning("BOT_TOKEN not set. Webhook not configured.")

    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

