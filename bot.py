import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Bot
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes, ConversationHandler,
)
from groq import Groq

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ID менеджеров — Евгений должен написать /start боту чтобы получать уведомления
MANAGER_IDS = [7328478138, 295158168]

SYSTEM_PROMPT = """Ты — Игорь, AI-ассистент компании CARFIRE. Помогаем пригнать автомобиль из-за рубежа.

О компании:
— Основные направления: Китай (новые авто, высокая комплектация) и США (аукционы битых авто, восстанавливаем до идеального состояния)
— По запросу: Европа, Канада, Япония, Корея
— Сроки из Китая: 3–6 недель
— Сроки из США: 6–10 недель
— Европа и другие: индивидуально
— Менеджер Евгений: @superluxxx

Стиль: живой, дружелюбный, уверенный. Без воды. Как опытный консультант.

Правила:
1. Отвечай на вопросы про пригон — сроки, страны, документы, растаможка, как работаем
2. Никогда не называй точные цены и не считай стоимость — говори что менеджер сделает точный расчёт
3. Не говори что мы не можем что-то привезти
4. Не здоровайся повторно в одном диалоге
5. Максимум 4–5 предложений
6. Только русский язык
7. Когда клиент готов к покупке или хочет расчёт — говори что менеджер Евгений (@superluxxx) свяжется с ним
"""

client = Groq(api_key=GROQ_API_KEY)
user_histories = {}

GET_NAME, GET_PHONE, GET_CAR, CHAT = range(4)


async def notify_managers(bot: Bot, profile: dict):
    text = (
        f"🔥 Новый лид!\n\n"
        f"👤 {profile.get('name', '—')}\n"
        f"📱 {profile.get('phone', '—')}\n"
        f"🚗 Интерес: {profile.get('car', '—')}\n"
        f"💬 @{profile.get('username', 'нет')}\n"
        f"🆔 {profile.get('tg_id', '—')}"
    )
    for mid in MANAGER_IDS:
        try:
            await bot.send_message(chat_id=mid, text=text)
        except Exception as e:
            logging.error(f"Уведомление {mid}: {e}")


def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚗 Оставить заявку"), KeyboardButton("🌍 Откуда привозите?")],
        [KeyboardButton("⏱ Сроки доставки"), KeyboardButton("❓ Как это работает?")],
        [KeyboardButton("📞 Связаться с менеджером")],
    ], resize_keyboard=True)

def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_histories[update.effective_user.id] = []
    await update.message.reply_text(
        "Привет! Я Игорь — AI-ассистент компании CARFIRE 🔥\n\n"
        "Помогаем пригнать авто из Китая, США и других стран.\n\n"
        "Как тебя зовут?",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return GET_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    context.user_data["username"] = update.effective_user.username or ""
    context.user_data["tg_id"] = update.effective_user.id
    await update.message.reply_text(
        f"{name}, приятно! 🤝\n\n"
        f"Оставь номер — менеджер сможет с тобой связаться.",
        reply_markup=phone_keyboard()
    )
    return GET_PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get("name", "")

    if update.message.contact:
        phone = update.message.contact.phone_number
    elif update.message.text:
        digits = "".join(filter(str.isdigit, update.message.text))
        if len(digits) >= 10:
            phone = update.message.text.strip()
        else:
            await update.message.reply_text(
                f"{name}, нажми кнопку ниже или напиши номер 👇",
                reply_markup=phone_keyboard()
            )
            return GET_PHONE
    else:
        await update.message.reply_text(
            f"Нажми кнопку ниже 👇",
            reply_markup=phone_keyboard()
        )
        return GET_PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text(
        f"Отлично! Теперь скажи — какой автомобиль интересует?\n\n"
        f"Напиши марку, модель, примерный бюджет или просто что ищешь.",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return GET_CAR


async def get_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    car = update.message.text.strip()
    context.user_data["car"] = car

    # Отправляем лид менеджерам
    await notify_managers(context.bot, context.user_data)
    logging.info(f"Лид: {context.user_data}")

    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"Принял! 👍\n\n"
        f"Менеджер Евгений свяжется с тобой в ближайшее время и сделает точный расчёт.\n\n"
        f"Пока можешь задать любой вопрос — я отвечу 👇",
        reply_markup=main_keyboard()
    )
    return CHAT


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()

    if user_text == "📞 Связаться с менеджером":
        await update.message.reply_text(
            "Менеджер Евгений:\nTelegram: @superluxxx\n\nНапиши ему напрямую — он поможет с расчётом и подбором.",
            reply_markup=main_keyboard()
        )
        return CHAT

    if user_text == "🚗 Оставить заявку":
        await update.message.reply_text(
            "Напиши какой автомобиль тебя интересует — марку, модель, бюджет или страну.\n"
            "Менеджер свяжется и сделает расчёт под твой запрос.",
            reply_markup=main_keyboard()
        )
        return CHAT

    quick_map = {
        "🌍 Откуда привозите?": "Из каких стран вы привозите автомобили?",
        "⏱ Сроки доставки": "Какие сроки доставки?",
        "❓ Как это работает?": "Как работает пригон авто? Расскажи процесс.",
    }
    llm_input = quick_map.get(user_text, user_text)

    user_histories.setdefault(user_id, [])
    user_histories[user_id].append({"role": "user", "content": llm_input})
    user_histories[user_id] = user_histories[user_id][-10:]

    name = context.user_data.get("name", "")
    system = SYSTEM_PROMPT
    if name:
        system += f"\n\nИмя клиента: {name}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system}] + user_histories[user_id],
            temperature=0.4,
            max_tokens=400,
        )
        reply = response.choices[0].message.content.strip()
        if not reply:
            reply = "Задай вопрос — отвечу! Или нажми кнопку ниже."
        user_histories[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply, reply_markup=main_keyboard())
    except Exception as e:
        logging.exception(f"Ошибка: {e}")
        await update.message.reply_text(
            "Что-то пошло не так. Напиши менеджеру напрямую: @superluxxx",
            reply_markup=main_keyboard()
        )

    return CHAT


def main():
    if not TELEGRAM_TOKEN: raise ValueError("Нет TELEGRAM_TOKEN")
    if not GROQ_API_KEY: raise ValueError("Нет GROQ_API_KEY")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
            GET_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car)],
            CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    logging.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
