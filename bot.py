import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes, ConversationHandler
from groq import Groq

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

SYSTEM_PROMPT = """Ты — AI-ассистент компании CARFIRE по пригону автомобилей из-за рубежа. Тебя зовут Игорь.

О компании:
- Название: CARFIRE
- Основные направления: Китай и США
- По запросу: Европа, Канада, Япония, Корея
- Комиссия за услуги: 90 000 рублей (включает полное сопровождение сделки)

Твоя задача:
1. Помогать клиенту прицениться — объяснять из каких стран везём, примерные сроки и условия
2. Отвечать на вопросы про пригон авто — стоимость, сроки, документы, растаможка
3. Когда клиент готов к покупке или хочет точный расчёт — передавать его менеджеру Евгению

Как передавать менеджеру:
Напиши: "Передаю тебя нашему менеджеру Евгению, он сделает точный расчёт и подберёт авто под тебя: @superluxxx в Telegram"

Правила:
- Ты AI-ассистент, не скрывай это — если спросят, честно скажи что ты искусственный интеллект
- Не здоровайся повторно если уже общался с клиентом в этом диалоге — просто продолжай разговор
- Отвечай коротко, максимум 4-5 предложений
- Говори только про направления которые реально везём
- Если не знаешь точного ответа — честно скажи и предложи связаться с менеджером
- Никогда не называй точную итоговую стоимость — говори что финальный расчёт делает менеджер Евгений
- Общайся на русском языке"""

client = Groq(api_key=GROQ_API_KEY)
user_histories = {}
user_data = {}

GET_NAME, GET_PHONE, CHAT = range(3)

def get_keyboard():
    keyboard = [
        [KeyboardButton("🚗 Подобрать авто"), KeyboardButton("💰 Прицениться")],
        [KeyboardButton("🌍 Из каких стран везёте?"), KeyboardButton("📞 Связаться с менеджером")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Я Игорь — AI-ассистент компании CARFIRE 🔥\n\n"
        "Я не просто бот — я искусственный интеллект, который поможет разобраться в пригоне авто из-за рубежа, прицениться и ответить на все вопросы.\n\n"
        "Прежде чем начать — как тебя зовут?",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"name": update.message.text}
    name = update.message.text
    await update.message.reply_text(
        f"Приятно познакомиться, {name}! 🤝\n\n"
        f"Оставь свой номер телефона — чтобы менеджер мог с тобой связаться когда будет нужно. "
        f"Никакого спама, только по делу 🙂",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Отправить номер", request_contact=True)]],
            resize_keyboard=True
        )
    )
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = user_data.get(user_id, {}).get("name", "")

    if update.message.contact:
        phone = update.message.contact.phone_number
        user_data[user_id]["phone"] = phone
        logging.info(f"Новый клиент: {name}, тел: {phone}, tg_id: {user_id}")
        await update.message.reply_text(
            f"Отлично, {name}! Теперь я готов помочь 🚀\n\n"
            f"Спрашивай всё что интересует — из каких стран везём, сколько стоит, "
            f"какие сроки, как работает растаможка. "
            f"Если захочешь точный расчёт — передам тебя менеджеру Евгению.",
            reply_markup=get_keyboard()
        )
        return CHAT
    else:
        await update.message.reply_text(
            f"{name}, всё понимаю 🙂\n\n"
            f"Номер нужен только для того, чтобы менеджер мог связаться с тобой когда будешь готов. "
            f"Без него я не смогу полноценно помочь с подбором и расчётом.\n\n"
            f"Нажми кнопку ниже — это займёт секунду 👇",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Отправить номер", request_contact=True)]],
                resize_keyboard=True
            )
        )
        return GET_PHONE

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    name = user_data.get(user_id, {}).get("name", "")

    if user_text == "📞 Связаться с менеджером":
        await update.message.reply_text(
            "Передаю тебя менеджеру Евгению! 💪\n\n"
            "Он сделает точный расчёт и подберёт авто под тебя.\n\n"
            "Telegram: @superluxxx",
            reply_markup=get_keyboard()
        )
        return CHAT

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": user_text})

    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    try:
        system = SYSTEM_PROMPT
        if name:
            system += f"\n\nКлиента зовут {name}. Обращайся к нему по имени иногда."

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system}] + user_histories[user_id],
            max_tokens=500,
        )
        reply = response.choices[0].message.content
        user_histories[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply, reply_markup=get_keyboard())

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("Что-то пошло не так, попробуй ещё раз.", reply_markup=get_keyboard())

    return CHAT

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
            CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    print("Бот запущен!")
    app.run_polling()
