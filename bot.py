import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Bot
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes, ConversationHandler,
)
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials
import json

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MANAGER_IDS = [7328478138, 295158168]

SYSTEM_PROMPT = """Ты — Игорь, AI-ассистент компании CARFIRE. Помогаем пригнать автомобиль из-за рубежа.

О компании CARFIRE:
— Привозим автомобили из Китая, США и других стран (Европа, Япония, Корея, Канада — по запросу)
— Работаем с любыми марками, чаще всего немецкие и японские
— Популярны авто до 160 л.с. — они выгоднее по налогу

Китай:
— Площадка: che168.com
— Новые и б/у автомобили
— Обычно высокая комплектация по сравнению с РФ
— Сроки: 3–6 недель

США:
— Работаем с аукционами (Copart, IAAI) и обычными авто
— Берём авто с небольшими повреждениями — восстановление включено в стоимость
— Клиент получает отличный автомобиль по выгодной цене
— Популярны немецкие и японские марки
— Сроки: 6–10 недель

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

SPREADSHEET_ID = "1ChQu78k-1b8wBWew1izazOpHDaq5N8HuFADLbHtMW_g"

GOOGLE_CREDS = {
    "type": "service_account",
    "project_id": "carfire-auto",
    "private_key_id": "b269e6de469fd6c2de7a1aca18a7e86d7996980a",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDPtdjVrdQ+Otec\nTpDRYwZmxAE0xppa+IbyWZW8oaalZvyVaAkQpu8Mk++5GfQXETodHcu6vCPDFndD\nuU4cIvaVqaMgAiM9X+1lWgnpCJE7fyowoceODIw7irCTn0GG36leA8JwWOpIoLJc\nk1Xoq3MFZCkalQMMSxAEfhi+Hnp3Fz12R6jHY4XF0aHgSbN9sU3br56Ysk97MSX6\nRIMzffappefRGMKUFBLotx+yVGWhLeS2+jokwSnRWsx7iMDc3nMfgm+QQayeoaCj\n9Khxk8nrEHjZmwGRWYuXWupcQhyai8cgWOLsmX5yViUmUxxfPmbg1i7M8fWdtC0T\ngPZ0jRzxAgMBAAECggEABHvduDEmM4i0Jlbo1+hOF1JUX1YJN30Fdr5Z1eZccVYh\njj0ecvpTjz8zTdjiVMwlp8LApuGQWRIHVZIuvjs//PeaQqLhLV5Agu9YZuwtLG5g\nlAeuBeI99bwW9zzZHob+Aj5NCH1W42X6q7ZvhJQM6dkhbQY5+F43dI1fTd1dEeyH\nyB0pCkeronjlBCjtadz2RXraTFxNH2Od4CLdXsa4MW2XXxtW7bW7rUYlqmcOB/wg\n1Z5JVQraFXFVBg8Bq/O6GEO4ZReAR1QQRFzrdPRQOETgTH6/ZAYHwKr/mJpfa5Vs\nz7FsxWsFlTa+SZkW62MyizQZPhXrDKX+27p7gTEuAQKBgQD2WQjvsjIXWYyf0vD3\nLkuyI/tYOAo3tG9TVBL/oj4R9RFinGyLsubsOLmlSwjua5O621gvrD1xP3xTlCCs\nJQLeQj5sG0d1bE2qJeV2nNV8PuFHC38Mt6fzVoZRbDmNj8mfB6f7Vjab6Q4zQ3WZ\nWwLoG6XYmalXS8fWLJhOHXF5gQKBgQDX2UNmWphFo1GKeqaqtJIknggvigf0XbeY\nsv9YHRu1c1dZmyShc1rzv6EF8+YZmv8H7iiWMhdmLxXN1baSZVzRKu1PLG9cAXRh\nib36+wLDARP+kvmkRzp6rVr++bhNi7a7Ac2jFK6c0906nKIoI2FH9csmWcwN//HE\nSpiim9X7cQKBgAnpiTeD1woje0oPBc0cWsVfN0TUdGzLYNNchastjwvP7ZQnMSLp\n3urQWX/yJfjZ8UbKfqDkcFB3OnxucGYc0yG4TqSw8E4kPnfDMJl2NAzcxtnB96m+\nVg6vg5YRIbu1dmpkt3igfnAFj6G2bCvwgoxuWFz/ydWOYgsXHkW+X4uBAoGAD7GX\nSfDaU23dduEWDyFT4t+unq49h9HskGirUh/DrPy25Cf4kNiPS1uqfIFQQJpZYp05\nTDpWIzLXNgEM5jYCep7RZElJy3m7mX/nVUE84SrJ5l+PURdwtAy4qgNEGDdJUO1/\noxTU4UgyNJnA3IQ+BXpki+RJhtcOIASAdoo4E7ECgYAru8c63MU6HBs4J4KnQAj8\n9zcswUZwGmwdJxGZFLSbnA8pnyCXDdQjOPCR0a0vzsevl4R6yJcOTn+WaTeqkLC3\nh0+Ob0mDiH15sVNCKyB87FpFWSSjIfVfKU7ZEBg/9B++P9qb0QsTyDl7gSslgMP9\nbBV148CPsBRbbrRM/IwgIw==\n-----END PRIVATE KEY-----\n",
    "client_email": "carfire-sheets@carfire-auto.iam.gserviceaccount.com",
    "client_id": "117620997756338360909",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/carfire-sheets%40carfire-auto.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}


def save_lead_to_sheets(profile: dict):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(GOOGLE_CREDS, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
        row = [
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            profile.get("name", "—"),
            profile.get("phone", "—"),
            profile.get("car", "—"),
            "Новый",
        ]
        sheet.append_row(row)
        logging.info(f"✅ Лид записан в Sheets: {row}")
    except Exception as e:
        logging.error(f"❌ Ошибка Sheets: {e}")


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
        [KeyboardButton("🚗 Оставить заявку"), KeyboardButton("🌍 Откуда привозите?")],
        [KeyboardButton("⏱ Сроки доставки"), KeyboardButton("❓ Как это работает?")],
        [KeyboardButton("⚡ Авто до 160 л.с."), KeyboardButton("🇨🇳 Китай vs 🇺🇸 США")],
        [KeyboardButton("📞 Связаться с менеджером")],
    ], resize_keyboard=True)


def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )


QUICK_ANSWERS = {
    "🌍 Откуда привозите?": (
        "Основные направления:\n\n"
        "🇨🇳 Китай — новые и б/у авто, высокая комплектация, площадка che168.com\n"
        "🇺🇸 США — аукционы Copart и IAAI, а также обычный рынок\n\n"
        "По запросу: Европа, Япония, Корея, Канада.\n\n"
        "Привозим любые марки — чаще всего немецкие и японские."
    ),
    "⏱ Сроки доставки": (
        "Сроки доставки:\n\n"
        "🇨🇳 Китай — 3–6 недель\n"
        "🇺🇸 США — 6–10 недель\n"
        "🌍 Европа, Япония, Корея — индивидуально\n\n"
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
    "🇨🇳 Китай vs 🇺🇸 США": (
        "Китай vs США — в чём разница?\n\n"
        "🇨🇳 Китай:\n"
        "— Новые и б/у авто\n"
        "— Высокая комплектация\n"
        "— Быстрее (3–6 недель)\n"
        "— Популярен для авто до 160 л.с.\n\n"
        "🇺🇸 США:\n"
        "— Аукционы и обычный рынок\n"
        "— Авто с повреждениями восстанавливаем — клиент получает отличную машину по выгодной цене\n"
        "— Хорошо для немецких и японских марок\n"
        "— Дольше (6–10 недель)\n\n"
        "Что лучше именно для тебя — зависит от бюджета и модели. "
        "Менеджер подскажет!"
    ),
}


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
        f"Оставь номер телефона — менеджер сможет связаться с тобой.",
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
                f"{name}, нажми кнопку или напиши номер 👇",
                reply_markup=phone_keyboard()
            )
            return GET_PHONE
    else:
        await update.message.reply_text("Нажми кнопку ниже 👇", reply_markup=phone_keyboard())
        return GET_PHONE

    context.user_data["phone"] = phone
    await update.message.reply_text(
        f"Отлично! Теперь скажи — какой автомобиль тебя интересует?\n\n"
        f"Напиши марку, модель, примерный бюджет или просто что ищешь.",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return GET_CAR


async def get_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    car = update.message.text.strip()
    context.user_data["car"] = car
    await notify_managers(context.bot, context.user_data)
    save_lead_to_sheets(context.user_data)
    logging.info(f"Лид: {context.user_data}")
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"Принял, {name}! 👍\n\n"
        f"Менеджер Евгений свяжется с тобой в ближайшее время и подберёт варианты.\n\n"
        f"Пока можешь узнать больше о нас 👇",
        reply_markup=main_keyboard()
    )
    return CHAT


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()

    if user_text == "📞 Связаться с менеджером":
        await update.message.reply_text(
            "Менеджер Евгений:\nTelegram: @superluxxx\n\n"
            "Напиши ему напрямую — он поможет с подбором и расчётом.",
            reply_markup=main_keyboard()
        )
        return CHAT

    if user_text == "🚗 Оставить заявку":
        await update.message.reply_text(
            "Напиши какой автомобиль тебя интересует — марку, модель, бюджет или страну.\n"
            "Менеджер свяжется и сделает подбор под твой запрос.",
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
        await update.message.reply_text(
            "Что-то пошло не так. Напиши менеджеру: @superluxxx",
            reply_markup=main_keyboard()
        )
    return CHAT


def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("Нет TELEGRAM_TOKEN")
    if not GROQ_API_KEY:
        raise ValueError("Нет GROQ_API_KEY")

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
