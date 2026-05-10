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
- Если клиент ищет оправдания — твёрдо возвращай к цели
- Давай конкретные советы, цифры, планы
- Если видишь фото еды — анализируй продукты, давай рецепты с КБЖУ
- Если видишь фото тела — оцени форму и составь план тренировок
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
        f"Что умею:\n"
        f"📸 Анализирую фото еды → рецепты и КБЖУ\n"
        f"💪 Анализирую фото тела → план тренировок\n"
        f"🧠 Отвечаю на вопросы по фитнесу и питанию\n\n"
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
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(file.file_path)
            image_bytes = response.content
        caption = update.message.caption or ""
        prompt = f"{SYSTEM_PROMPT}\n\nПроанализируй фото. Если еда/продукты — дай рецепты и КБЖУ. Если тело — оцени форму и составь план тренировок. {caption}"
        image_part = {
            "mime_type": "image/jpeg",
            "data": image_bytes
        }
        ai_response = model.generate_content([prompt, image_part])
        reply = ai_response.text
        user_histories[user_id].append({"role": "user", "text": "фото"})
        user_histories[user_id].append({"role": "assistant", "text": reply})
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
        "💪 Программа тренировок": "Составь мне программу тренировок. Сначала спроси мой уровень подготовки, цель и сколько дней в неделю тренируюсь.",
        "🥗 Рецепт по фото": "Хочу получить рецепт по фото продуктов. Что нужно сделать?",
        "📊 Мой прогресс": "Как отслеживать прогресс? Дай конкретный план.",
        "💬 Поговорить с тренером": "Привет тренер! Хочу поговорить.",
        "🎯 Моя цель": "Помоги поставить чёткую фитнес-цель и составить план.",
        "❓ Помощь": "Покажи что умеешь и как с тобой работать."
    }
    user_message = button_map.get(text, text)
    history_text = ""
    for msg in user_histories[user_id][-10:]:
        role = "Клиент" if msg["role"] == "user" else "Тренер"
        history_text += f"{role}: {msg['text']}\n"
    prompt = f"{SYSTEM_PROMPT}\n\nИстория:\n{history_text}\nКлиент: {user_message}\nТренер:"
    try:
        ai_response = model.generate_content(prompt)
        reply = ai_response.text
        user_histories[user_id].append({"role": "user", "text": user_message})
        user_histories[user_id].append({"role": "assistant", "text": reply})
        if len(user_histories[user_id]) > 20:
            user_histories[user_id] = user_histories[user_id][-20:]
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
