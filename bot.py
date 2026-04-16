import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler,
)
from groq import Groq

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MANAGER_IDS = [7328478138, 295158168]

SYSTEM_PROMPT = """Ты — Игорь, AI-ассистент компании CARFIRE. Помогаем пригнать автомобиль из-за рубежа.

О компании CARFIRE:
— Привозим автомобили из Китая, США, Европы, Японии и Кореи
— Работаем с любыми марками
— Популярны авто до 160 л.с. — они выгоднее по налогу

Китай:
— Площадка: che168.com
— Новые и б/у автомобили
— Обычно высокая комплектация по сравнению с РФ
— Сроки: 3–6 недель

США:
— Работаем с аукционами (Copart, IAAI) и обычными авто
— Берём авто с небольшими повреждениями — восстановление включено в стоимость
— Сроки: 6–10 недель

Европа, Япония, Корея:
— Подбор по запросу
— Сроки и условия — индивидуально

Как работаем:
— Клиент оставляет заявку
— Обсуждаем задачу — что именно нужно, бюджет, пожелания
— Предлагаем варианты и находим то что лучше всего подходит
— Сопровождаем сделку от покупки до получения авто
— Возможна работа как с предоплатой так и без

Стоимость:
— Не называй конкретных цифр — это делает менеджер индивидуально
— Можно сказать что стоимость зависит от марки, модели, года, мощности и курса

Менеджер Евгений: @superluxxx
Сайт: carfire-import.ru

Стиль: живой, дружелюбный, уверенный. Без воды. Как опытный консультант. Иногда обращайся по имени.

Правила:
1. Отвечай на вопросы про пригон — сроки, страны, процесс, документы, растаможка
2. Никогда не называй конкретные цены — только менеджер
3. Не говори что мы что-то не можем
4. Не здоровайся повторно
5. Максимум 4–5 предложений
6. Только русский язык
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
        f"💬 @{profile.get('username') or 'нет'}\n"
        f"🆔 {profile.get('tg_id', '—')}"
    )
    for mid in MANAGER_IDS:
        try:
            await bot.send_message(chat_id=mid, text=text)
        except Exception as e:
            logging.error(f"Уведомление {mid}: {e}")


def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚗 Оставить заявку"), KeyboardButton("🌍 Страны и условия")],
        [KeyboardButton("⏱ Сроки доставки"), KeyboardButton("❓ Как это работает?")],
        [KeyboardButton("⚡ Авто до 160 л.с."), KeyboardButton("🌐 Наш сайт")],
        [KeyboardButton("📞 Связаться с менеджером")],
    ], resize_keyboard=True)

def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )

QUICK_ANSWERS = {
    "🌍 Страны и условия": (
        "Откуда привозим автомобили:\n\n"
        "🇨🇳 Китай — новые и б/у авто, высокая комплектация, площадка che168.com, 3–6 недель\n\n"
        "🇺🇸 США — аукционы Copart и IAAI, авто с повреждениями восстанавливаем, 6–10 недель\n\n"
        "🇪🇺 Европа — подбор по запросу, сроки индивидуально\n\n"
        "🇯🇵 Япония — подбор по запросу, сроки индивидуально\n\n"
        "🇰🇷 Корея — подбор по запросу, сроки индивидуально\n\n"
        "Привозим любые марки. Менеджер подберёт лучший вариант под твой запрос и бюджет."
    ),
    "⏱ Сроки доставки": (
        "Сроки доставки:\n\n"
        "🇨🇳 Китай — 3–6 недель\n"
        "🇺🇸 США — 6–10 недель\n"
        "🇪🇺 Европа — индивидуально\n"
        "🇯🇵 Япония — индивидуально\n"
        "🇰🇷 Корея — индивидуально\n\n"
        "Точные сроки зависят от конкретного авто и маршрута. "
        "Менеджер скажет точнее под твой запрос."
    ),
    "❓ Как это работает?": (
        "Процесс пригона:\n\n"
        "1️⃣ Оставляешь заявку — рассказываешь что нужно\n"
        "2️⃣ Обсуждаем задачу — бюджет, пожелания, приоритеты\n"
        "3️⃣ Подбираем варианты — предлагаем то что реально подходит\n"
        "4️⃣ Согласовываем — ты выбираешь, мы закупаем\n"
        "5️⃣ Доставка и оформление — берём на себя всё\n"
        "6️⃣ Получаешь авто — готовое к езде\n\n"
        "Работаем как с предоплатой так и без — обсуждается индивидуально."
    ),
    "⚡ Авто до 160 л.с.": (
        "Авто до 160 л.с. — популярный выбор 🔥\n\n"
        "Почему выгодно:\n"
        "— Ниже транспортный налог\n"
        "— Меньше таможенные платежи\n"
        "— Отличный выбор из Китая по хорошей цене\n\n"
        "Привозим любые марки до 160 л.с. — кроссоверы, седаны, хэтчбеки. "
        "Оставь заявку — подберём варианты под твой бюджет."
    ),
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_histories[update.effective_user.id] = []
    await update.message.reply_text(
        "Привет! Я Игорь — AI-ассистент компании CARFIRE 🔥\n\n"
        "Помогаем пригнать авто из Китая, США, Европы, Японии и Кореи.\n\n"
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
        f"{name}, приятно! 🤝\n\nОставь номер телефона — менеджер сможет связаться с тобой.",
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
            await update.message.reply_text(f"{name}, нажми кнопку или напиши номер 👇", reply_markup=phone_keyboard())
            return GET_PHONE
    else:
        await update.message.reply_text("Нажми кнопку ниже 👇", reply_markup=phone_keyboard())
        return GET_PHONE
    context.user_data["phone"] = phone
    await update.message.reply_text(
        f"Отлично! Теперь скажи — какой автомобиль тебя интересует?\n\nНапиши марку, модель, примерный бюджет или просто что ищешь.",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return GET_CAR


async def get_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    car = update.message.text.strip()
    context.user_data["car"] = car
    await notify_managers(context.bot, context.user_data)
    logging.info(f"Лид: {context.user_data}")
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"Принял, {name}! 👍\n\nМенеджер Евгений свяжется с тобой в ближайшее время и подберёт варианты.\n\nПока можешь узнать больше о нас 👇",
        reply_markup=main_keyboard()
    )
    return CHAT


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()

    if user_text == "📞 Связаться с менеджером":
        await update.message.reply_text(
            "Менеджер Евгений:\nTelegram: @superluxxx\n\nНапиши ему напрямую — он поможет с подбором и расчётом.",
            reply_markup=main_keyboard()
        )
        return CHAT

    if user_text == "🚗 Оставить заявку":
        await update.message.reply_text(
            "Напиши какой автомобиль тебя интересует — марку, модель, бюджет или страну.\nМенеджер свяжется и сделает подбор под твой запрос.",
            reply_markup=main_keyboard()
        )
        return CHAT

    if user_text == "🌐 Наш сайт":
        await update.message.reply_text(
            "Наш сайт: https://carfire-import.ru\n\nТам найдёшь подробную информацию о компании и услугах.",
            reply_markup=main_keyboard()
        )
        return CHAT

    if user_text in QUICK_ANSWERS:
        await update.message.reply_text(QUICK_ANSWERS[user_text], reply_markup=main_keyboard())
        return CHAT

    name = context.user_data.get("name", "")
    system = SYSTEM_PROMPT
    if name:
        system += f"\n\nИмя клиента: {name}"

    user_histories.setdefault(user_id, [])
    user_histories[user_id].append({"role": "user", "content": user_text})
    user_histories[user_id] = user_histories[user_id][-10:]

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
        await update.message.reply_text("Что-то пошло не так. Напиши менеджеру: @superluxxx", reply_markup=main_keyboard())

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
