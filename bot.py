import os
import logging
import random
from datetime import time
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError, NetworkError, TimedOut

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Ты — личный тренер по имени Hunter. Строгий, мотивирующий, профессиональный фитнес-тренер и нутрициолог.

ПРАВИЛА:
- Обращайся на "ты", дружески но строго
- Определяй язык пользователя и отвечай на том же языке
- Используй эмодзи активно и уместно
- НЕ повторяй вопросы о данных если они уже были в диалоге
- Всегда помни данные пользователя из истории диалога
- Отвечай КОРОТКО и ПО ДЕЛУ

УПРАЖНЕНИЯ — ОБЯЗАТЕЛЬНО:
- Название + эмодзи
- Техника (1-2 предложения)
- Подходы x повторения
- Главная ошибка

ПИТАНИЕ — ПРАВИЛА:
- НЕ пиши длинные списки, НЕ объясняй зачем БЖУ
- Давай КОНКРЕТНЫЕ блюда с граммовкой
- КАЖДЫЙ РАЗ разные варианты!
- Продукты: яйца, творог, гречка, овсянка, лосось, тунец, говядина, индейка, авокадо, орехи, ягоды, овощи

ФОРМАТ ПИТАНИЯ:
Завтрак 7:00 — Омлет 3 яйца + помидор | ~450 ккал | Б:28 Ж:18 У:35
Перекус 10:00 — Творог 150г + орехи | ~280 ккал
Обед 13:00 — Говядина 180г + гречка 150г | ~580 ккал
Перекус 16:00 — Яблоко + миндаль 30г | ~180 ккал
Ужин 19:00 — Лосось 200г + брокколи | ~520 ккал
Вода: X л/день | Итого: ~XXXX ккал

МОТИВАЦИЯ: одна фраза в конце!"""

WATER_REMINDERS = [
    "💧 Время пить воду! Hunter следит за тобой 👀\nВыпей стакан (200-250 мл) прямо сейчас!",
    "🚰 Стоп! Вода!\nНорма: 30 мл x твой вес в кг. Пей!",
    "💦 Гидратация = производительность!\nОбезвоживание на 2% снижает силу на 10%.",
    "🥤 Напоминание от Hunter'а:\nТвои мышцы на 75% состоят из воды. Дай им то, что нужно!",
]

MORNING_TIPS = [
    "💧 Вода — топливо чемпиона! Выпей стакан прямо сейчас!",
    "🔥 Мышцы растут во время отдыха. Спи 7-8 часов!",
    "⚡ 10 приседаний прямо сейчас — твоё тело скажет спасибо!",
    "💪 Каждая тренировка — это инвестиция в себя будущего!",
    "🧘 Стресс убивает прогресс. 5 минут дыхания творят чудеса!",
    "😴 Недосып = потеря мышц. Сегодня ляг вовремя!",
]

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💪 Программа тренировок"), KeyboardButton("🥗 План питания")],
        [KeyboardButton("📊 Мой прогресс"), KeyboardButton("💬 Чат с тренером")],
        [KeyboardButton("🎯 Поставить цель"), KeyboardButton("🔥 Мотивация")],
        [KeyboardButton("💧 Водный баланс"), KeyboardButton("❓ Помощь")]
    ], resize_keyboard=True)

def get_workout_inline():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Дома", callback_data="workout_home"),
         InlineKeyboardButton("🏋️ Зал", callback_data="workout_gym"),
         InlineKeyboardButton("🏃 Улица", callback_data="workout_outdoor")],
        [InlineKeyboardButton("⚡ 20 мин", callback_data="time_20"),
         InlineKeyboardButton("🕐 45 мин", callback_data="time_45"),
         InlineKeyboardButton("💪 1+ час", callback_data="time_60")]
    ])

def get_goal_inline():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Похудеть", callback_data="goal_lose"),
         InlineKeyboardButton("💪 Набрать массу", callback_data="goal_gain")],
        [InlineKeyboardButton("⚡ Выносливость", callback_data="goal_endurance"),
         InlineKeyboardButton("🧘 Рельеф", callback_data="goal_tone")]
    ])

async def water_reminder(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(chat_id=context.job.chat_id, text=random.choice(WATER_REMINDERS))
    except TelegramError as e:
        logger.error(f"Water reminder error: {e}")

async def morning_motivation(context: ContextTypes.DEFAULT_TYPE):
    tip = random.choice(MORNING_TIPS)
    try:
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=f"🌅 Доброе утро от Hunter'а!\n\n{tip}\n\nСегодня ты станешь лучше чем вчера! 🚀"
        )
    except TelegramError as e:
        logger.error(f"Morning motivation error: {e}")

async def evening_checkin(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text="🌆 Вечерний отчёт от Hunter'а!\n\nКак прошёл твой день?\n\n✅ Потренировался?\n💧 Выпил норму воды?\n🥗 Питался по плану?\n\nНапиши — разберём что улучшить! 💪"
        )
    except TelegramError as e:
        logger.error(f"Evening check-in error: {e}")

def setup_reminders(app: Application, chat_id: int):
    jq = app.job_queue
    for name in [f"water_{chat_id}", f"morning_{chat_id}", f"evening_{chat_id}"]:
        for job in jq.get_jobs_by_name(name):
            job.schedule_removal()
    jq.run_repeating(water_reminder, interval=7200, first=7200, chat_id=chat_id, name=f"water_{chat_id}")
    jq.run_daily(morning_motivation, time=time(6, 0), chat_id=chat_id, name=f"morning_{chat_id}")
    jq.run_daily(evening_checkin, time=time(17, 0), chat_id=chat_id, name=f"evening_{chat_id}")

async def ask_groq(user_message: str, history: list) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    messages.append({"role": "user", "content": user_message})
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1500,
        temperature=0.7
    )
    return response.choices[0].message.content

def add_to_history(context: ContextTypes.DEFAULT_TYPE, user_msg: str, bot_reply: str):
    if 'history' not in context.user_data:
        context.user_data['history'] = []
    context.user_data['history'].append({"role": "user", "content": user_msg})
    context.user_data['history'].append({"role": "assistant", "content": bot_reply})
    if len(context.user_data['history']) > 30:
        context.user_data['history'] = context.user_data['history'][-30:]

async def safe_send(message, text: str, reply_markup=None):
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for i, chunk in enumerate(chunks):
        kb = reply_markup if i == len(chunks) - 1 else None
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except TelegramError:
            try:
                await message.reply_text(chunk, reply_markup=kb)
            except TelegramError as e:
                logger.error(f"safe_send failed: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    context.user_data['history'] = []
    context.user_data['reminders_active'] = True
    setup_reminders(context.application, chat_id)
    await update.message.reply_text(
        f"👊 Привет, {user_name}!\n\n"
        f"Я — Hunter, твой личный AI-тренер.\n"
        f"Строгий, но справедливый. Никаких отговорок!\n\n"
        f"🔔 Буду напоминать:\n"
        f"💧 Пить воду каждые 2 часа\n"
        f"🌅 Утренняя мотивация в 9:00\n"
        f"🌆 Вечерний чек-ин в 20:00\n\n"
        f"Давай познакомимся! Напиши:\n"
        f"• Возраст, рост, вес\n"
        f"• Цель (похудеть / набрать массу / рельеф)\n"
        f"• Опыт тренировок\n\n"
        f"Чем больше знаю — тем точнее план! 💪",
        reply_markup=get_main_keyboard()
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    history = context.user_data.get('history', [])

    cb_map = {
        "workout_home": "Составь программу тренировок дома без оборудования с объяснением техники.",
        "workout_gym": "Составь программу тренировок в тренажёрном зале с объяснением техники.",
        "workout_outdoor": "Составь программу тренировок на улице с объяснением техники.",
        "time_20": "Составь быструю 20-минутную тренировку.",
        "time_45": "Составь тренировку на 45 минут.",
        "time_60": "Составь полноценную тренировку на час+.",
        "goal_lose": "Моя цель — похудеть. Составь план тренировок и питания для жиросжигания.",
        "goal_gain": "Моя цель — набрать мышечную массу. Составь план.",
        "goal_endurance": "Моя цель — выносливость. Составь план тренировок.",
        "goal_tone": "Моя цель — рельеф. Составь план тренировок и питания.",
    }

    user_message = cb_map.get(query.data, "Помоги мне с тренировками.")
    await query.message.reply_text("⏳ Hunter анализирует...")
    try:
        reply = await ask_groq(user_message, history)
        add_to_history(context, user_message, reply)
        await safe_send(query.message, reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.message.reply_text("❌ Ошибка. Попробуй ещё раз!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    if not context.user_data.get('reminders_active'):
        setup_reminders(context.application, chat_id)
        context.user_data['reminders_active'] = True

    if 'history' not in context.user_data:
        context.user_data['history'] = []

    button_map = {
        "💪 Программа тренировок": ("workout_choice", None),
        "🥗 План питания": ("ask", "Составь план питания на день с конкретными блюдами и калориями."),
        "📊 Мой прогресс": ("ask", "Как отслеживать прогресс? Дай конкретные метрики."),
        "💬 Чат с тренером": ("ask", "Привет Hunter! Хочу поговорить о тренировках."),
        "🎯 Поставить цель": ("goal_choice", None),
        "🔥 Мотивация": ("ask", "Дай мощную мотивацию и интересный факт о фитнесе!"),
        "💧 Водный баланс": ("ask", "Сколько мне пить воды в день и как контролировать баланс?"),
        "❓ Помощь": ("ask", "Что ты умеешь? Расскажи кратко."),
    }

    if text in button_map:
        action, msg = button_map[text]
        if action == "workout_choice":
            await update.message.reply_text("🏋️ Выбери тип тренировки:", reply_markup=get_workout_inline())
            return
        if action == "goal_choice":
            await update.message.reply_text("🎯 Какая твоя цель?", reply_markup=get_goal_inline())
            return
        user_message = msg
    else:
        user_message = text

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        reply = await ask_groq(user_message, context.user_data['history'])
        add_to_history(context, user_message, reply)
        await safe_send(update.message, reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"handle_text error: {e}")
        await update.message.reply_text("❌ Ошибка. Попробуй ещё раз!", reply_markup=get_main_keyboard())

async def reminders_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for name in [f"water_{chat_id}", f"morning_{chat_id}", f"evening_{chat_id}"]:
        for job in context.application.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    context.user_data['reminders_active'] = False
    await update.message.reply_text("🔕 Напоминания выключены. Включить: /reminders_on")

async def reminders_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    setup_reminders(context.application, update.effective_chat.id)
    context.user_data['reminders_active'] = True
    await update.message.reply_text("🔔 Напоминания включены!\n💧 Вода каждые 2 часа\n🌅 9:00\n🌆 20:00")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}", exc_info=context.error)
    if isinstance(context.error, (NetworkError, TimedOut)):
        return
    if update and hasattr(update, 'message') and update.message:
        try:
            await update.message.reply_text("⚠️ Что-то пошло не так. Попробуй ещё раз!")
        except Exception:
            pass

def main():
    if not TOKEN:
        raise ValueError("TOKEN не найден!")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY не найден!")

    app = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reminders_off", reminders_off))
    app.add_handler(CommandHandler("reminders_on", reminders_on))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    logger.info("Hunter Bot started!")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
