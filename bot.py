import os
import logging
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Ты — личный тренер по имени Hunter. Строгий, но справедливый профессиональный фитнес-тренер и нутрициолог.
- Обращайся на "ты", дружески но строго
- Давай конкретные советы, цифры, планы
- Определяй язык пользователя и отвечай на том же языке
- Используй эмодзи умеренно"""

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("💪 Программа тренировок"), KeyboardButton("🥗 Рецепт питания")],
        [KeyboardButton("📊 Мой прогресс"), KeyboardButton("💬 Поговорить с тренером")],
        [KeyboardButton("🎯 Моя цель"), KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome = (
        f"Привет, {user_name}! 👊\n\n"
        f"Я — Hunter, твой личный AI-тренер.\n\n"
        f"Строгий, но справедливый. Никаких отговорок — только результат! 💪\n\n"
        f"С чего начнём? ⬇️"
    )
    await update.message.reply_text(welcome, reply_markup=get_main_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    button_map = {
        "💪 Программа тренировок": "Составь мне программу тренировок.",
        "🥗 Рецепт питания": "Дай мне план питания на день.",
        "📊 Мой прогресс": "Как отслеживать прогресс?",
        "💬 Поговорить с тренером": "Привет тренер!",
        "🎯 Моя цель": "Помоги поставить фитнес-цель.",
        "❓ Помощь": "Что ты умеешь?"
    }
    user_message = button_map.get(text, text)
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Groq error: {e}")
        await update.message.reply_text("Ошибка. Попробуй ещё раз!")

def main():
    if not TOKEN:
        raise ValueError("TOKEN не найден!")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY не найден!")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
