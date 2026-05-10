import os
import logging
import httpx
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

SYSTEM_PROMPT = """Ты — личный тренер по имени Hunter. Строгий, но справедливый профессиональный фитнес-тренер и нутрициолог.

Правила:
- Требователен, не терпишь отговорок, но заботишься о здоровье клиента
- Обращайся на "ты", дружески но строго
- Давай конкретные советы, цифры, планы
- Отвечай ТОЛЬКО на русском языке
- Используй эмодзи умеренно"""

user_histories = {}

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("💪 Программа тренировок"), KeyboardButton("🥗 Рецепт по фото")],
        [KeyboardButton("📊 Мой прогресс"), KeyboardButton("💬 Поговорить с тренером")],
        [KeyboardButton("🎯 Моя цель"), KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_histories[user_id] = []
    welcome = (
        f"Привет, {user_name}! 👊\n\n"
        f"Я — Hunter, твой личный AI-тренер.\n\n"
        f"Строгий, но справедливый. Никаких отговорок — только результат! 💪\n\n"
        f"С чего начнём? ⬇️"
    )
    await update.message.reply_text(welcome, reply_markup=get_main_keyboard())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    await update.message.reply_text("Анализирую фото... 🔍 Подожди секунду!")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        async with httpx.AsyncClient(timeout=30) as http_client:
            response = await http_client.get(file.file_path)
            image_bytes = response.content
        caption = update.message.caption or ""
        prompt = f"{SYSTEM_PROMPT}\n\nПроанализируй фото. Если еда — дай рецепты и КБЖУ. Если тело — оцени форму и составь план. {caption}"
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        ai_response = model.generate_content(
            [prompt, image_part],
            request_options={"timeout": 60}
        )
        reply = ai_response.text
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Gemini photo error: {e}")
        await update.message.reply_text("Ошибка при анализе фото. Попробуй ещё раз!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    text = update.message.text
    button_map = {
        "💪 Программа тренировок": "Составь мне программу тренировок.",
        "🥗 Рецепт по фото": "Как получить рецепт по фото продуктов?",
        "📊 Мой прогресс": "Как отслеживать прогресс?",
        "💬 Поговорить с тренером": "Привет тренер!",
        "🎯 Моя цель": "Помоги поставить фитнес-цель.",
        "❓ Помощь": "Что ты умеешь?"
    }
    user_message = button_map.get(text, text)
    prompt = f"{SYSTEM_PROMPT}\n\nКлиент: {user_message}\nТренер:"
    try:
        ai_response = model.generate_content(
            prompt,
            request_options={"timeout": 60}
        )
        reply = ai_response.text
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Gemini text error: {e}")
        await update.message.reply_text("Ошибка. Попробуй ещё раз!")

def main():
    if not TOKEN:
        raise ValueError("TOKEN не найден!")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY не найден!")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
