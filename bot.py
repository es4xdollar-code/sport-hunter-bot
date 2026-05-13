import os
import logging
import asyncio
from datetime import datetime, time
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler, JobQueue
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, NetworkError, TimedOut

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

# ─── SYSTEM PROMPT ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Ты — личный тренер по имени Hunter 🦁. Строгий, мотивирующий, профессиональный фитнес-тренер и нутрициолог.

ПРАВИЛА ОБЩЕНИЯ:
- Обращайся на "ты", дружески но строго
- Определяй язык пользователя и отвечай на том же языке
- Используй эмодзи активно и уместно — они делают текст живым
- НЕ повторяй вопросы о данных если они уже были в диалоге
- Всегда помни данные пользователя из истории диалога
- Отвечай КОРОТКО и ПО ДЕЛУ — без воды и лишних слов

КОГДА ДАЁШЬ УПРАЖНЕНИЯ — ОБЯЗАТЕЛЬНО:
✅ Название упражнения + эмодзи
✅ Простое объяснение техники (1-2 предложения, как будто объясняешь новичку)
✅ Подходы × повторения
✅ Главная ошибка которую надо избегать

ФОРМАТ ПЛАНА ТРЕНИРОВОК:
🏋️ *День X: [Название]*
━━━━━━━━━━━━━━━
1️⃣ *Упражнение* — как делать — 3×12
   ⚠️ Ошибка: ...
2️⃣ ...
⏱ Отдых: X мин | 💧 Вода каждые 20 мин!

ПРАВИЛА ПЛАНА ПИТАНИЯ (очень важно!):
❌ НЕ пиши длинные списки продуктов
❌ НЕ объясняй зачем нужны белки/жиры/углеводы — это и так знают
❌ НЕ давай абстрактные "куриная грудка с рисом" каждый раз
✅ Давай КОНКРЕТНЫЕ блюда с граммовкой — реальная еда которую можно приготовить
✅ КАЖДЫЙ РАЗ предлагай РАЗНЫЕ варианты — не повторяйся
✅ Используй разнообразные продукты: яйца, творог, гречка, овсянка, лосось, тунец, говядина, индейка, авокадо, орехи, ягоды, овощи
✅ Учитывай цель пользователя (похудение/масса/рельеф)

ФОРМАТ ПЛАНА ПИТАНИЯ (коротко и конкретно):
🌅 *Завтрак 7:00*
Омлет из 3 яиц + помидор + сыр | Овсянка 100г с бананом и мёдом
~450 ккал | Б:28г Ж:18г У:35г

🍎 *Перекус 10:00*
Творог 5% — 150г + горсть грецких орехов
~280 ккал

🌞 *Обед 13:00*
Говяжий стейк 180г + гречка 150г + огурец с оливковым маслом
~580 ккал | Б:42г Ж:16г У:48г

🍊 *Перекус 16:00*
Яблоко + миндаль 30г
~180 ккал

🌆 *Ужин 19:00*
Лосось запечённый 200г + брокколи 200г + авокадо ½
~520 ккал | Б:38г Ж:28г У:12г

💧 Вода: [норма] л/день
🔥 Итого: ~[сумма] ккал

МОТИВАЦИЯ:
- Заканчивай сообщения мотивирующей фразой (1 строка, не больше!)
- Хвали за прогресс и усилия"""

# ─── EXERCISE IMAGES (GIF URLs для наглядности) ────────────────────────────────
EXERCISE_TIPS = [
    "💧 *Вода — топливо чемпиона!* Выпей стакан прямо сейчас!",
    "🔥 *Факт:* Мышцы растут во время отдыха, не тренировки. Спи 7-8 часов!",
    "⚡ *Совет Hunter'а:* 10 приседаний прямо сейчас — твоё тело скажет спасибо!",
    "🥗 *Питание = 70% результата.* Ты поел сегодня правильно?",
    "💪 *Мотивация:* Каждая тренировка — это инвестиция в себя будущего!",
    "🧘 *Стресс убивает прогресс.* 5 минут глубокого дыхания творят чудеса!",
    "🏃 *10 000 шагов в день* — простой способ сжечь 300-500 калорий!",
    "😴 *Недосып = потеря мышц.* Сегодня ляг вовремя!",
]

WATER_REMINDERS = [
    "💧 *Время пить воду!* Hunter следит за тобой 👀\nВыпей стакан (200-250 мл) прямо сейчас!",
    "🚰 *Стоп! Вода!* Ты уже выпил достаточно сегодня?\nНорма: 30 мл × твой вес в кг",
    "💦 *Гидратация = производительность!*\nОбезвоживание на 2% снижает силу на 10%. Пей!",
    "🥤 *Напоминание от Hunter'а:*\nТвои мышцы на 75% состоят из воды. Дай им то, что нужно!",
]

# ─── КЛАВИАТУРЫ ──────────────────────────────────────────────────────────────
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("💪 Программа тренировок"), KeyboardButton("🥗 План питания")],
        [KeyboardButton("📊 Мой прогресс"), KeyboardButton("💬 Чат с тренером")],
        [KeyboardButton("🎯 Поставить цель"), KeyboardButton("🔥 Мотивация")],
        [KeyboardButton("💧 Водный баланс"), KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_workout_inline():
    keyboard = [
        [
            InlineKeyboardButton("🏠 Дома", callback_data="workout_home"),
            InlineKeyboardButton("🏋️ Зал", callback_data="workout_gym"),
            InlineKeyboardButton("🏃 Улица", callback_data="workout_outdoor")
        ],
        [
            InlineKeyboardButton("⚡ 20 мин", callback_data="time_20"),
            InlineKeyboardButton("🕐 45 мин", callback_data="time_45"),
            InlineKeyboardButton("💪 1+ час", callback_data="time_60")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_goal_inline():
    keyboard = [
        [
            InlineKeyboardButton("🔥 Похудеть", callback_data="goal_lose"),
            InlineKeyboardButton("💪 Набрать массу", callback_data="goal_gain")
        ],
        [
            InlineKeyboardButton("⚡ Выносливость", callback_data="goal_endurance"),
            InlineKeyboardButton("🧘 Рельеф", callback_data="goal_tone")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ─── НАПОМИНАНИЯ ─────────────────────────────────────────────────────────────
async def water_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Напоминание пить воду каждые 2 часа"""
    job = context.job
    chat_id = job.chat_id
    import random
    reminder = random.choice(WATER_REMINDERS)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=reminder,
            parse_mode=ParseMode.MARKDOWN
        )
    except TelegramError as e:
        logger.error(f"Water reminder error: {e}")

async def daily_motivation(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная мотивация в 9 утра"""
    job = context.job
    chat_id = job.chat_id
    import random
    tip = random.choice(EXERCISE_TIPS)
    msg = f"🌅 *Доброе утро от Hunter'а!*\n\n{tip}\n\n_Сегодня ты станешь лучше чем вчера!_ 🚀"
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN
        )
    except TelegramError as e:
        logger.error(f"Daily motivation error: {e}")

async def evening_checkin(context: ContextTypes.DEFAULT_TYPE):
    """Вечерний чек-ин в 20:00"""
    job = context.job
    chat_id = job.chat_id
    msg = (
        "🌆 *Вечерний отчёт от Hunter'а!*\n\n"
        "Как прошёл твой день?\n\n"
        "✅ Потренировался?\n"
        "💧 Выпил норму воды?\n"
        "🥗 Питался по плану?\n\n"
        "Напиши мне — разберём что было и что улучшить! 💪"
    )
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN
        )
    except TelegramError as e:
        logger.error(f"Evening check-in error: {e}")

def setup_reminders(application, chat_id):
    """Настройка всех напоминаний для пользователя"""
    job_queue = application.job_queue

    # Убираем старые задачи для этого пользователя
    current_jobs = job_queue.get_jobs_by_name(f"water_{chat_id}")
    for job in current_jobs:
        job.schedule_removal()
    current_jobs = job_queue.get_jobs_by_name(f"morning_{chat_id}")
    for job in current_jobs:
        job.schedule_removal()
    current_jobs = job_queue.get_jobs_by_name(f"evening_{chat_id}")
    for job in current_jobs:
        job.schedule_removal()

    # Вода каждые 2 часа (7200 секунд)
    job_queue.run_repeating(
        water_reminder,
        interval=7200,
        first=7200,
        chat_id=chat_id,
        name=f"water_{chat_id}"
    )

    # Утренняя мотивация в 9:00
    job_queue.run_daily(
        daily_motivation,
        time=time(hour=6, minute=0),  # UTC (9:00 МСК)
        chat_id=chat_id,
        name=f"morning_{chat_id}"
    )

    # Вечерний чек-ин в 20:00
    job_queue.run_daily(
        evening_checkin,
        time=time(hour=17, minute=0),  # UTC (20:00 МСК)
        chat_id=chat_id,
        name=f"evening_{chat_id}"
    )

# ─── GROQ ЗАПРОС С ИСТОРИЕЙ ──────────────────────────────────────────────────
async def ask_groq(user_message: str, history: list) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise

def update_history(context: ContextTypes.DEFAULT_TYPE, user_msg: str, bot_reply: str):
    """Обновляем историю, ограничивая до 30 сообщений"""
    if 'history' not in context.user_data:
        context.user_data['history'] = []

    context.user_data['history'].append({"role": "user", "content": user_msg})
    context.user_data['history'].append({"role": "assistant", "content": bot_reply})

    # Храним последние 30 сообщений (15 диалогов)
    if len(context.user_data['history']) > 30:
        context.user_data['history'] = context.user_data['history'][-30:]

async def safe_send(message, text: str, reply_markup=None):
    """Отправка с fallback: Markdown -> plain text"""
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for i, chunk in enumerate(chunks):
        kb = reply_markup if i == len(chunks) - 1 else None
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except TelegramError as e:
            logger.warning(f"Markdown failed, sending plain: {e}")
            try:
                await message.reply_text(chunk, reply_markup=kb)
            except TelegramError as e2:
                logger.error(f"Send failed: {e2}")

# ─── HANDLERS ────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт бота"""
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name

    # Сбрасываем историю
    context.user_data['history'] = []
    context.user_data['reminders_active'] = True

    # Запускаем напоминания
    setup_reminders(context.application, chat_id)

    welcome = (
        f"👊 *Привет, {user_name}!*\n\n"
        f"Я — *Hunter*, твой личный AI-тренер.\n"
        f"Строгий, но справедливый. Никаких отговорок!\n\n"
        f"🔔 *Я буду напоминать тебе:*\n"
        f"💧 Пить воду каждые 2 часа\n"
        f"🌅 Утренняя мотивация в 9:00\n"
        f"🌆 Вечерний чек-ин в 20:00\n\n"
        f"*Давай познакомимся!* Напиши:\n"
        f"• Возраст\n"
        f"• Рост и вес\n"
        f"• Цель (похудеть / набрать массу / рельеф)\n"
        f"• Опыт тренировок\n\n"
        f"_Чем больше знаю — тем точнее план!_ 💪"
    )

    await update.message.reply_text(
        welcome,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard()
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка inline кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data
    history = context.user_data.get('history', [])

    callback_messages = {
        "workout_home": "Составь программу тренировок дома без оборудования с объяснением техники каждого упражнения.",
        "workout_gym": "Составь программу тренировок в тренажёрном зале с объяснением техники каждого упражнения.",
        "workout_outdoor": "Составь программу тренировок на улице с объяснением техники каждого упражнения.",
        "time_20": "Составь быструю 20-минутную тренировку с объяснением упражнений.",
        "time_45": "Составь тренировку на 45 минут с объяснением упражнений.",
        "time_60": "Составь полноценную тренировку на час и более с объяснением упражнений.",
        "goal_lose": "Моя цель — похудеть. Составь план тренировок и питания для жиросжигания.",
        "goal_gain": "Моя цель — набрать мышечную массу. Составь план тренировок и питания для набора.",
        "goal_endurance": "Моя цель — развить выносливость. Составь план тренировок.",
        "goal_tone": "Моя цель — рельеф и подтянутое тело. Составь план тренировок и питания.",
    }

    user_message = callback_messages.get(data, "Помоги мне с тренировками.")

    await query.message.reply_text("⏳ Hunter анализирует...")

    try:
        reply = await ask_groq(user_message, history)
        update_history(context, user_message, reply)
        await safe_send(query.message, reply, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.message.reply_text("❌ Ошибка соединения. Попробуй ещё раз!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик сообщений"""
    text = update.message.text
    chat_id = update.effective_chat.id

    # Убеждаемся что напоминания активны
    if not context.user_data.get('reminders_active'):
        setup_reminders(context.application, chat_id)
        context.user_data['reminders_active'] = True

    # Инициализация истории
    if 'history' not in context.user_data:
        context.user_data['history'] = []

    # Маппинг кнопок
    button_map = {
        "💪 Программа тренировок": ("workout_choice", None),
        "🥗 План питания": ("ask", "Составь подробный план питания на день с калориями и БЖУ, учитывая мои данные."),
        "📊 Мой прогресс": ("ask", "Как мне отслеживать прогресс? Дай конкретные метрики и методы измерения."),
        "💬 Чат с тренером": ("ask", "Привет Hunter! Хочу поговорить о своих тренировках."),
        "🎯 Поставить цель": ("goal_choice", None),
        "🔥 Мотивация": ("ask", "Дай мне мощную мотивацию и несколько интересных фактов о фитнесе!"),
        "💧 Водный баланс": ("ask", "Расскажи про водный баланс. Сколько мне пить воды в день и как это контролировать?"),
        "❓ Помощь": ("ask", "Что ты умеешь? Расскажи подробно о своих возможностях."),
    }

    if text in button_map:
        action, message = button_map[text]

        if action == "workout_choice":
            await update.message.reply_text(
                "🏋️ *Выбери тип тренировки:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_workout_inline()
            )
            return

        if action == "goal_choice":
            await update.message.reply_text(
                "🎯 *Какая твоя цель?*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_goal_inline()
            )
            return

        user_message = message
    else:
        user_message = text

    # Показываем что бот печатает
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        reply = await ask_groq(user_message, context.user_data['history'])
        update_history(context, user_message, reply)

        await safe_send(update.message, reply, reply_markup=get_main_keyboard())

    except Exception as e:
        logger.error(f"Handle text error: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуй ещё раз через несколько секунд!",
            reply_markup=get_main_keyboard()
        )

async def reminders_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выключить напоминания"""
    chat_id = update.effective_chat.id
    job_queue = context.application.job_queue

    for name in [f"water_{chat_id}", f"morning_{chat_id}", f"evening_{chat_id}"]:
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()

    context.user_data['reminders_active'] = False
    await update.message.reply_text(
        "🔕 Напоминания выключены.\nВключить обратно: /reminders_on",
        reply_markup=get_main_keyboard()
    )

async def reminders_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить напоминания"""
    chat_id = update.effective_chat.id
    setup_reminders(context.application, chat_id)
    context.user_data['reminders_active'] = True
    await update.message.reply_text(
        "🔔 Напоминания включены!\n💧 Вода каждые 2 часа\n🌅 Мотивация в 9:00\n🌆 Чек-ин в 20:00",
        reply_markup=get_main_keyboard()
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error(f"Exception: {context.error}", exc_info=context.error)

    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning("Network error — will retry automatically")
        return

    if update and hasattr(update, 'message') and update.message:
        try:
            await update.message.reply_text("⚠️ Что-то пошло не так. Попробуй ещё раз!")
        except Exception:
            pass

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        raise ValueError("❌ TOKEN не найден в переменных окружения!")
    if not GROQ_API_KEY:
        raise ValueError("❌ GROQ_API_KEY не найден в переменных окружения!")

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reminders_off", reminders_off))
    app.add_handler(CommandHandler("reminders_on", reminders_on))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Глобальный обработчик ошибок
    app.add_error_handler(error_handler)

    logger.info("🚀 Hunter Bot запущен!")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()
