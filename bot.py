import os
import logging
import httpx
import google.generativeai as genai
import PIL.Image
import io
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

SYSTEM_PROMPT = """Ты — личный тренер по имени Hunter. Ты строгий, но справедливый профессиональный фитнес-тренер и нутрициолог.

Твои правила:
- Ты требователен и не терпишь отговорок, но искренне заботишься о здоровье клиента
- Всегда обращайся на "ты", по-дружески но строго
- Если клиент ищет оправдания — мягко но твёрдо возвращай его к цели
- Давай конкретные советы, цифры, планы — никакой воды
- Мотивируй, но не льсти
- Если видишь фото еды — анализируй продукты и давай рецепты с КБЖУ
- Если видишь фото тела — профессионально оцени физическую форму и предложи план тренировок
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
        f"Я строгий, но это потому что мне не всё равно на твой результат. "
        f"Никаких отговорок — только работа и результат! 💪\n\n"
        f"Что я умею:\n"
        f"📸 Анализирую фото продуктов → даю рецепты\n"
        f"💪 Анализирую фото тела → составляю план тренировок\n"
        f"🧠 Отвечаю на любые вопросы по фитнесу и питанию\n\n"
        f"С чего начнём? ⬇️"
    )
    await update.message.reply_text(welcome, reply_markup=get_main_keyboard())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    await update.message.reply_text("Анализирую фото... 🔍 Подожди секунду!")
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    async with httpx.AsyncClient() as http_client:
        response = await http_client.get(file.file_path)
        image_data = response.content
    caption = update.message.caption or ""
    prompt = f"{SYSTEM_PROMPT}\n\nПроанализируй это фото. Если это еда/продукты — дай рецепты и КБЖУ. Если это тело человека — оцени физическую форму и составь план тренировок. {caption}"
    try:
        image = PIL.Image.open(io.BytesIO(image_data))
        ai_response = model.generate_content([prompt, image])
        reply = ai_response.text
        user_histories[user_id].append({"role": "user", "text": "фото"})
        user_histories[user_id].append({"role": "assistant", "text": reply})
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        await update.message.reply_text("Произошла ошибка при анализе фото. Попробуй ещё раз!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_histories:
        user_histories[user_id] = []
    text = update.message.text
    button_map = {
        "💪 Программа тренировок": "Составь мне программу тренировок. Сначала спроси мой уровень подготовки, цель и сколько дней в неделю могу тренироваться.",
        "🥗 Рецепт по фото": "Я хочу получить рецепт по фото продуктов. Что мне нужно сделать?",
        "📊 Мой прогресс": "Как мне отслеживать свой прогресс? Дай конкретный план.",
        "💬 Поговорить с тренером": "Привет тренер! Хочу поговорить.",
        "🎯 Моя цель": "Помоги мне поставить чёткую фитнес-цель и составить план её достижения.",
        "❓ Помощь": "Покажи что ты умеешь и как мне лучше с тобой работать."
    }
    user_message = button_map.get(text, text)
    history_text = ""
    for msg in user_histories[user_id][-10:]:
        if msg["role"] == "user":
            history_text += f"Клиент: {msg['text']}\n"
        else:
            history_text += f"Тренер: {msg['text']}\n"
    prompt = f"{SYSTEM_PROMPT}\n\nИстория разговора:\n{history_text}\nКлиент: {user_message}\nТренер:"
    try:
        ai_response = model.generate_content(prompt)
        reply = ai_response.text
        user_histories[user_id].append({"role": "user", "text": user_message})
        user_histories[user_id].append({"role": "assistant", "text": reply})
        if len(user_histories[user_id]) > 20:
            user_histories[user_id] = user_histories[user_id][-20:]
        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуй ещё раз!")

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
