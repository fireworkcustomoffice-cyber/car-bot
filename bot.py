import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

SYSTEM_PROMPT = """Ты — консультант компании CARFIRE по пригону автомобилей из-за рубежа. Общаешься дружелюбно и неформально.

О компании:
- Название: CARFIRE
- Основные направления: Китай и США
- По запросу: Европа, Канада, Япония, Корея
- Комиссия за услуги: 90 000 рублей (включает полное сопровождение сделки)

Твоя задача:
1. Отвечать на вопросы клиентов про пригон авто — стоимость, сроки, документы, растаможка
2. Помогать выбрать страну под запрос клиента
3. Когда клиент готов к покупке или хочет точный расчёт — передавать его менеджеру

Как передавать менеджеру:
Напиши: "Для точного расчёта и подбора авто свяжись с нашим менеджером Максом: @superluxxx в Telegram"

Правила:
- Отвечай коротко, максимум 4-5 предложений
- Говори только про направления которые реально везём
- Если не знаешь точного ответа — честно скажи и предложи связаться с менеджером
- Никогда не называй точную итоговую стоимость — говори что финальный расчёт делает менеджер
- Общайся на русском языке"""

client = Groq(api_key=GROQ_API_KEY)
user_histories = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": user_text})

    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user_id],
            max_tokens=500,
        )
        reply = response.choices[0].message.content
        user_histories[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("Что-то пошло не так, попробуй ещё раз.")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    app.run_polling()
