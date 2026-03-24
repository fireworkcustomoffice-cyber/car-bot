import os
import re
import logging
from typing import Dict, List, Any, Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Bot
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from groq import Groq

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# -----------------------------
# МЕНЕДЖЕРЫ
# -----------------------------
MANAGER_IDS = [7328478138, 295158168]

# -----------------------------
# ДАННЫЕ КОМПАНИИ
# -----------------------------
COMPANY_DATA: Dict[str, Any] = {
    "name": "CARFIRE",
    "assistant_name": "Игорь",
    "manager_name": "Евгений",
    "manager_telegram": "@superluxxx",
    "main_directions": ["Китай", "США"],
    "extra_directions": ["Европа", "Канада", "Япония", "Корея"],
    "commission_rub": 90000,
    "commission_text": "Наша комиссия — 90 000 ₽. Включает полное сопровождение сделки от подбора до получения авто.",
    "prepayment_policy": "По ряду вариантов можем работать без полной предоплаты — зависит от авто, площадки и условий.",
    "delivery_terms": {
        "Китай": "3–6 недель в зависимости от маршрута и оформления.",
        "США": "6–10 недель в зависимости от порта и логистики.",
        "Европа": "Индивидуально, зависит от страны и маршрута.",
        "Канада": "Индивидуально.",
        "Япония": "Индивидуально.",
        "Корея": "Индивидуально.",
    },
    "customs_note": "Итоговая стоимость зависит от курса таможни, мощности, года выпуска, комплектации и логистики.",
    "lead_handoff_triggers": [
        "хочу купить", "готов купить", "нужен точный расчет", "нужен точный расчёт",
        "давай оформлять", "хочу подбор", "подберите мне", "оформить заявку",
        "готов к покупке", "как оформить",
    ],
}

# -----------------------------
# БАЗА АВТОМОБИЛЕЙ
# Заполни своими реальными данными
# -----------------------------
CARS_DATABASE: List[Dict[str, Any]] = [
    {
        "brand": "Mazda", "model": "CX-5", "year": 2025,
        "country": "Китай", "power_hp": 155, "fuel": "бензин",
        "drive": "передний / полный",
        "price_from_rub": 2900000, "price_to_rub": 3400000,
        "is_under_160_hp": True, "is_available": True, "priority": True,
        "url": "https://che168.com",
        "comment": "Отличный проходной кроссовер до 160 л.с. Популярный вариант."
    },
    {
        "brand": "Volkswagen", "model": "Tiguan L", "year": 2024,
        "country": "Китай", "power_hp": 160, "fuel": "бензин",
        "drive": "передний / полный",
        "price_from_rub": 3000000, "price_to_rub": 3600000,
        "is_under_160_hp": True, "is_available": True, "priority": True,
        "url": "https://che168.com",
        "comment": "Семейный вариант с хорошей ликвидностью. Проходит до 160 л.с."
    },
    {
        "brand": "Toyota", "model": "Camry", "year": 2024,
        "country": "Китай", "power_hp": 173, "fuel": "бензин",
        "drive": "передний",
        "price_from_rub": 3100000, "price_to_rub": 3700000,
        "is_under_160_hp": False, "is_available": True, "priority": False,
        "url": "https://che168.com",
        "comment": "Популярная модель, но выше 160 л.с. — налог будет выше."
    },
    {
        "brand": "Haval", "model": "H6", "year": 2025,
        "country": "Китай", "power_hp": 150, "fuel": "бензин",
        "drive": "полный",
        "price_from_rub": 2400000, "price_to_rub": 2900000,
        "is_under_160_hp": True, "is_available": True, "priority": True,
        "url": "https://che168.com",
        "comment": "Бюджетный китайский кроссовер. Хорошее оснащение за деньги."
    },
    {
        "brand": "Li Auto", "model": "L6", "year": 2024,
        "country": "Китай", "power_hp": 330, "fuel": "гибрид",
        "drive": "полный",
        "price_from_rub": 4500000, "price_to_rub": 5500000,
        "is_under_160_hp": False, "is_available": True, "priority": False,
        "url": "https://che168.com",
        "comment": "Премиальный китайский гибрид. Большой внедорожник с запасом хода."
    },
]

# -----------------------------
# ПАМЯТЬ
# -----------------------------
user_histories: Dict[int, List[Dict[str, str]]] = {}
user_profiles: Dict[int, Dict[str, Any]] = {}

GET_NAME, GET_PHONE, CHAT = range(3)

# -----------------------------
# ПРОМПТ
# -----------------------------
SYSTEM_PROMPT = """Ты — AI-ассистент компании CARFIRE по пригону автомобилей из-за рубежа.
Тебя зовут Игорь. Ты не просто бот — ты настоящий ИИ-консультант.

Тон общения:
— уверенный, спокойный, дружелюбный
— без воды и навязчивости
— как сильный консультант который реально разбирается в теме
— живой язык, без канцелярщины

Что ты умеешь:
1. Помогать клиенту сориентироваться — страны, сроки, бюджет, растаможка
2. Давать вилку цен под запрос клиента
3. Показывать подходящие варианты авто из контекста
4. Объяснять нюансы — до 160 л.с., таможня, документы
5. Передавать клиента менеджеру когда он готов

Жёсткие правила:
1. Не придумывай цены, сроки, ссылки и факты — используй только данные из контекста
2. Комиссию не называй, если клиент прямо не спросил про стоимость услуг
3. Не отправляй к менеджеру при каждом вопросе — сначала помоги сам
4. Передача менеджеру уместна только если: клиент готов к покупке, просит точный расчёт, просит оформить
5. Не здоровайся повторно если уже общался — просто продолжай разговор
6. Если есть подходящие авто — показывай 2–3 варианта с ценой и ссылкой
7. Отвечай коротко и по делу: 3–5 предложений
8. Всегда на русском языке
9. Если спросят кто ты — честно скажи что ты ИИ-ассистент CARFIRE

Формат ответа с авто:
• Марка Модель Год | Мощность | Цена от X до Y ₽
  Комментарий почему подходит

Передача менеджеру:
"Передаю тебя менеджеру Евгению — он сделает точный расчёт под конкретный вариант: @superluxxx"
"""

client = Groq(api_key=GROQ_API_KEY)


# -----------------------------
# УТИЛИТЫ
# -----------------------------
def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def format_price(price_from: int, price_to: int) -> str:
    return f"от {price_from:,} до {price_to:,} ₽".replace(",", " ")

def asked_commission(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in ["комиссия", "сколько берете", "сколько берёте",
                                  "стоимость услуг", "ваши услуги", "что входит"])

def needs_manager(text: str) -> bool:
    t = normalize(text)
    return any(phrase in t for phrase in COMPANY_DATA["lead_handoff_triggers"])

def extract_budget(text: str) -> Optional[int]:
    t = normalize(text).replace("₽", "").replace("рублей", "").replace("руб", "")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*млн", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000_000)
    m = re.search(r"\b(\d{6,8})\b", t)
    if m:
        return int(m.group(1))
    return None

def detect_countries(text: str) -> List[str]:
    t = normalize(text)
    all_c = COMPANY_DATA["main_directions"] + COMPANY_DATA["extra_directions"]
    return [c for c in all_c if c.lower() in t]

def detect_under_160(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in ["до 160", "проходной", "проходная", "проходные",
                                  "до налоговой", "160 сил", "160 лс"])

def search_cars(query: str, budget: Optional[int], countries: List[str], under_160: bool) -> List[Dict]:
    q = normalize(query)
    results = []
    for car in CARS_DATABASE:
        if not car.get("is_available"):
            continue
        if countries and car["country"] not in countries:
            continue
        if under_160 and not car.get("is_under_160_hp"):
            continue
        if budget and car["price_from_rub"] > budget:
            continue
        score = 0
        blob = f"{car['brand']} {car['model']} {car['country']} {car['comment']}".lower()
        for word in q.split():
            if len(word) >= 3 and word in blob:
                score += 2
        if car.get("priority"):
            score += 2
        if under_160 and car.get("is_under_160_hp"):
            score += 3
        results.append((score, car))
    results.sort(key=lambda x: (x[0], -x[1].get("year", 0)), reverse=True)
    return [c for _, c in results[:3]]

def build_context(user_id: int, user_text: str) -> str:
    profile = user_profiles.get(user_id, {})
    name = profile.get("name", "")
    budget = extract_budget(user_text)
    countries = detect_countries(user_text)
    under_160 = detect_under_160(user_text)
    show_commission = asked_commission(user_text)
    cars = search_cars(user_text, budget, countries, under_160)

    lines = [
        f"Компания: {COMPANY_DATA['name']}",
        f"Основные направления: {', '.join(COMPANY_DATA['main_directions'])}",
        f"По запросу: {', '.join(COMPANY_DATA['extra_directions'])}",
        f"Предоплата: {COMPANY_DATA['prepayment_policy']}",
        f"Расчёт: {COMPANY_DATA['customs_note']}",
    ]

    if name:
        lines.append(f"Имя клиента: {name}")
    if budget:
        lines.append(f"Бюджет клиента: до {budget:,} ₽".replace(",", " "))
    if countries:
        lines.append(f"Интересующие страны: {', '.join(countries)}")
    if under_160:
        lines.append("Клиент ищет авто до 160 л.с. (проходные по налогу)")

    lines.append("\nСроки доставки:")
    for country, term in COMPANY_DATA["delivery_terms"].items():
        lines.append(f"  {country}: {term}")

    if show_commission:
        lines.append(f"\nКомиссия: {COMPANY_DATA['commission_text']}")
    else:
        lines.append("\nКомиссию не упоминать — клиент не спрашивал.")

    lines.append("\nПодходящие автомобили:")
    if cars:
        for car in cars:
            lines.append(
                f"  • {car['brand']} {car['model']} {car['year']} | "
                f"{car['power_hp']} л.с. | "
                f"{format_price(car['price_from_rub'], car['price_to_rub'])} | "
                f"{'✅ до 160 л.с.' if car['is_under_160_hp'] else '⚠️ выше 160 л.с.'} | "
                f"Площадка: {car['url']} | {car['comment']}"
            )
    else:
        lines.append("  Подходящих авто в базе не найдено. Предложи связаться с менеджером для индивидуального подбора.")

    lines.append(f"\nМенеджер: {COMPANY_DATA['manager_name']} — {COMPANY_DATA['manager_telegram']}")
    return "\n".join(lines)


# -----------------------------
# УВЕДОМЛЕНИЕ МЕНЕДЖЕРАМ
# -----------------------------
async def notify_managers(bot: Bot, name: str, phone: str, tg_id: int, username: str):
    text = (
        f"🔥 Новый лид!\n\n"
        f"👤 {name}\n"
        f"📱 {phone}\n"
        f"💬 @{username if username else 'нет username'}\n"
        f"🆔 {tg_id}"
    )
    for mid in MANAGER_IDS:
        try:
            await bot.send_message(chat_id=mid, text=text)
        except Exception as e:
            logging.error(f"Ошибка уведомления менеджеру {mid}: {e}")


# -----------------------------
# КЛАВИАТУРЫ
# -----------------------------
def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚗 Подобрать авто"), KeyboardButton("💰 Прицениться")],
        [KeyboardButton("⚡ До 160 л.с."), KeyboardButton("⏱ Сроки доставки")],
        [KeyboardButton("🌍 Из каких стран везёте?"), KeyboardButton("📞 Связаться с менеджером")],
    ], resize_keyboard=True)

def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )


# -----------------------------
# ХЭНДЛЕРЫ
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет!\n\n"
        "Я Игорь — AI-ассистент компании CARFIRE 🔥\n\n"
        "Помогу разобраться в пригоне авто из-за рубежа: подберу варианты, "
        "объясню сроки, расскажу про растаможку и помогу прицениться.\n\n"
        "Как тебя зовут?",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()
    user_profiles[user_id] = {"name": name, "phone": None}
    user_histories[user_id] = []

    await update.message.reply_text(
        f"{name}, приятно познакомиться! 🤝\n\n"
        f"Оставь номер телефона — менеджер сможет связаться с тобой "
        f"когда дойдёт до конкретики по подбору.",
        reply_markup=phone_keyboard()
    )
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = user_profiles.get(user_id, {}).get("name", "")
    username = update.effective_user.username or ""

    phone = None
    if update.message.contact:
        phone = update.message.contact.phone_number
    elif update.message.text:
        digits = "".join(filter(str.isdigit, update.message.text))
        if len(digits) >= 10:
            phone = update.message.text.strip()

    if not phone:
        await update.message.reply_text(
            f"{name}, без номера не получится передать тебя менеджеру когда придёт время 🙂\n\n"
            f"Нажми кнопку ниже 👇",
            reply_markup=phone_keyboard()
        )
        return GET_PHONE

    user_profiles[user_id]["phone"] = phone
    logging.info(f"Новый лид | {name} | {phone} | @{username} | {user_id}")

    await notify_managers(context.bot, name, phone, user_id, username)

    await update.message.reply_text(
        f"Отлично, {name}!\n\n"
        f"Пиши что ищешь — марку, модель, бюджет, страну. "
        f"Например: «кроссовер из Китая до 3 млн и до 160 сил».\n\n"
        f"Или нажми одну из кнопок 👇",
        reply_markup=main_keyboard()
    )
    return CHAT

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()

    if user_text == "📞 Связаться с менеджером":
        await update.message.reply_text(
            "Передаю тебя менеджеру Евгению 💪\n\n"
            "Он сделает точный расчёт и подберёт авто под тебя.\n\n"
            "Telegram: @superluxxx",
            reply_markup=main_keyboard()
        )
        return CHAT

    quick_map = {
        "🚗 Подобрать авто": "Помоги подобрать автомобиль для пригона. Покажи варианты и ориентир по цене.",
        "💰 Прицениться": "Хочу понять примерный бюджет на привоз автомобиля под ключ.",
        "⚡ До 160 л.с.": "Покажи варианты авто до 160 л.с. которые можно привезти.",
        "🌍 Из каких стран везёте?": "Из каких стран вы привозите автомобили и какие особенности у каждой?",
        "⏱ Сроки доставки": "Какие сроки доставки по разным направлениям?",
    }
    llm_input = quick_map.get(user_text, user_text)

    if needs_manager(llm_input):
        await update.message.reply_text(
            "Понял, передаю тебя менеджеру Евгению — он поможет с точным расчётом: @superluxxx",
            reply_markup=main_keyboard()
        )
        return CHAT

    user_histories.setdefault(user_id, [])
    user_histories[user_id].append({"role": "user", "content": llm_input})
    user_histories[user_id] = user_histories[user_id][-14:]

    context_block = build_context(user_id, llm_input)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": "Бизнес-контекст и данные:\n" + context_block},
            ] + user_histories[user_id],
            temperature=0.35,
            max_tokens=600,
        )

        reply = response.choices[0].message.content.strip()
        if not reply:
            reply = "Напиши что именно ищешь — марку, модель, бюджет или страну. Помогу сориентироваться."

        user_histories[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply, reply_markup=main_keyboard())

    except Exception as e:
        logging.exception(f"Ошибка LLM: {e}")
        await update.message.reply_text(
            "Что-то пошло не так. Попробуй ещё раз.",
            reply_markup=main_keyboard()
        )

    return CHAT


# -----------------------------
# ЗАПУСК
# -----------------------------
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("Не задан TELEGRAM_TOKEN")
    if not GROQ_API_KEY:
        raise ValueError("Не задан GROQ_API_KEY")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
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
        allow_reentry=True,
    )

    application.add_handler(conv)
    logging.info("Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()
