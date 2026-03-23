import os
import re
import json
import html
import logging
from typing import Dict, List, Any, Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from groq import Groq

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

GET_NAME, GET_PHONE, CHAT = range(3)

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
    "show_commission_only_if_asked": True,
    "commission_rub": 90000,
    "commission_text": "Комиссия за услуги составляет 90 000 ₽ и включает полное сопровождение сделки.",
    "prepayment_policy": "По некоторым вариантам можем работать без полной предоплаты, но это зависит от автомобиля, площадки и условий сделки.",
    "delivery_terms": {
        "Китай": "Обычно от 3 до 6 недель, в зависимости от маршрута, очередей и оформления.",
        "США": "Обычно от 6 до 10 недель, зависит от порта, логистики и оформления.",
        "Европа": "Сроки считаются индивидуально.",
        "Канада": "Сроки считаются индивидуально.",
        "Япония": "Сроки считаются индивидуально.",
        "Корея": "Сроки считаются индивидуально.",
    },
    "customs_note": "Точный расчёт зависит от курса, таможенных платежей, мощности, года выпуска, комплектации и логистики.",
    "price_policy": "Бот может давать ориентир и вилку цены, но не обещает точную финальную сумму.",
    "manager_handoff_text": (
        "Если хочешь, передам твой запрос менеджеру Евгению. "
        "Он сделает точный расчёт и поможет уже по конкретному варианту: @superluxxx"
    ),
    "lead_handoff_trigger_phrases": [
        "хочу купить",
        "готов купить",
        "нужен точный расчет",
        "нужен точный расчёт",
        "давай оформлять",
        "связи с менеджером",
        "хочу подбор",
        "подберите мне",
        "оставьте менеджера",
    ],
}

# -----------------------------
# БАЗА МАШИН
# Тут ты потом заполнишь своими реальными данными
# -----------------------------
CARS_DATABASE: List[Dict[str, Any]] = [
    {
        "id": 1,
        "brand": "Mazda",
        "model": "CX-5",
        "year": 2025,
        "country": "Китай",
        "power_hp": 155,
        "fuel": "бензин",
        "drive": "передний / полный",
        "price_from_rub": 2900000,
        "price_to_rub": 3400000,
        "is_under_160_hp": True,
        "is_available": True,
        "priority": True,
        "source_name": "Китайская площадка",
        "url": "https://example.com/mazda-cx5-2025",
        "comment": "Хороший вариант для тех, кто хочет проходной кроссовер до 160 л.с."
    },
    {
        "id": 2,
        "brand": "Volkswagen",
        "model": "Tiguan L",
        "year": 2024,
        "country": "Китай",
        "power_hp": 160,
        "fuel": "бензин",
        "drive": "передний / полный",
        "price_from_rub": 3000000,
        "price_to_rub": 3600000,
        "is_under_160_hp": True,
        "is_available": True,
        "priority": True,
        "source_name": "Китайская площадка",
        "url": "https://example.com/tiguan-l-2024",
        "comment": "Можно смотреть как семейный вариант с хорошей ликвидностью."
    },
    {
        "id": 3,
        "brand": "Toyota",
        "model": "Camry",
        "year": 2024,
        "country": "Китай",
        "power_hp": 173,
        "fuel": "бензин",
        "drive": "передний",
        "price_from_rub": 3100000,
        "price_to_rub": 3700000,
        "is_under_160_hp": False,
        "is_available": True,
        "priority": False,
        "source_name": "Китайская площадка",
        "url": "https://example.com/camry-2024",
        "comment": "Популярная модель, но не под фильтр до 160 л.с."
    },
]

# -----------------------------
# ПАМЯТЬ ПОЛЬЗОВАТЕЛЕЙ
# -----------------------------
user_histories: Dict[int, List[Dict[str, str]]] = {}
user_profiles: Dict[int, Dict[str, Any]] = {}

# -----------------------------
# СИСТЕМНЫЙ ПРОМПТ
# -----------------------------
SYSTEM_PROMPT = """
Ты — AI-ассистент компании CARFIRE по пригону автомобилей из-за рубежа.
Тебя зовут Игорь.

Тон:
- уверенный
- спокойный
- дружелюбный
- без лишней воды
- без навязчивости
- без перегруза
- отвечай естественно, как сильный консультант

Твоя задача:
- помогать человеку сориентироваться по пригону авто
- объяснять направления, сроки, условия
- давать ориентир по бюджету и вилку цены
- предлагать подходящие варианты из переданного контекста
- не выдумывать факты, которых нет в контексте
- не навязывать менеджера без причины

Жёсткие правила:
1. Не придумывай автомобили, цены, сроки, ссылки, комиссии и условия.
2. Используй только ту информацию, которая пришла в контексте.
3. Если точных данных нет — честно скажи, что нужен точный расчёт.
4. Не упоминай комиссию, если пользователь прямо не спросил про комиссию / стоимость услуг / сколько берёте / что входит в услуги.
5. Не отправляй к менеджеру при каждом вопросе. Сначала постарайся помочь сам.
6. Передача менеджеру уместна только если:
   - клиент явно готов к покупке,
   - просит точный расчёт,
   - просит оформить,
   - нужен нестандартный кейс,
   - в контексте недостаточно данных.
7. Отвечай коротко и содержательно: обычно 3–6 предложений.
8. Если есть подходящие машины из контекста — покажи 2–4 самых релевантных.
9. Если есть ссылка — приложи ссылку.
10. Если пользователь спрашивает "до 160 сил" или "проходные" — учитывай этот фильтр как приоритетный.

Формат хорошего ответа:
- сначала суть
- потом 2–4 подходящих варианта, если они есть
- потом мягкий следующий шаг без давления
"""

# -----------------------------
# КЛАВИАТУРЫ
# -----------------------------
def get_empty_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[]], resize_keyboard=True)

def get_phone_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("📱 Отправить номер", request_contact=True)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🚗 Подобрать авто"), KeyboardButton("💰 Прицениться")],
        [KeyboardButton("⚡ До 160 л.с."), KeyboardButton("🌍 Из каких стран везёте?")],
        [KeyboardButton("⏱ Сроки"), KeyboardButton("📞 Связаться с менеджером")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# -----------------------------
# УТИЛИТЫ
# -----------------------------
def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def format_price_range(price_from: int, price_to: int) -> str:
    return f"от {price_from:,} до {price_to:,} ₽".replace(",", " ")

def user_asked_about_commission(text: str) -> bool:
    t = normalize_text(text)
    triggers = [
        "комиссия",
        "сколько берете",
        "сколько берёте",
        "стоимость услуг",
        "ваши услуги",
        "что входит в услуги",
        "сколько стоит ваша работа",
        "сколько стоит подбор",
    ]
    return any(trigger in t for trigger in triggers)

def user_needs_manager(text: str) -> bool:
    t = normalize_text(text)
    if "связаться с менеджером" in t:
        return True
    return any(phrase in t for phrase in COMPANY_DATA["lead_handoff_trigger_phrases"])

def extract_budget(text: str) -> Optional[int]:
    """
    Пытаемся вытащить бюджет типа:
    - 3 млн
    - до 2500000
    - 2.8
    """
    t = normalize_text(text).replace("₽", "").replace("рублей", "").replace("руб", "")
    mln_match = re.search(r"(\d+(?:[.,]\d+)?)\s*млн", t)
    if mln_match:
        value = float(mln_match.group(1).replace(",", "."))
        return int(value * 1_000_000)

    num_match = re.search(r"\b(\d{6,8})\b", t)
    if num_match:
        return int(num_match.group(1))

    return None

def detect_country_preferences(text: str) -> List[str]:
    t = normalize_text(text)
    found = []
    all_countries = COMPANY_DATA["main_directions"] + COMPANY_DATA["extra_directions"]
    for country in all_countries:
        if country.lower() in t:
            found.append(country)
    return found

def detect_under_160_need(text: str) -> bool:
    t = normalize_text(text)
    triggers = [
        "до 160",
        "до 160 сил",
        "до 160 л.с",
        "до 160 лс",
        "проходной",
        "проходная",
        "проходные",
        "до налоговой",
    ]
    return any(trigger in t for trigger in triggers)

def search_cars(
    query: str,
    budget: Optional[int] = None,
    preferred_countries: Optional[List[str]] = None,
    under_160_only: bool = False,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    q = normalize_text(query)
    results = []

    for car in CARS_DATABASE:
        if not car.get("is_available", False):
            continue

        if preferred_countries and car["country"] not in preferred_countries:
            continue

        if under_160_only and not car.get("is_under_160_hp", False):
            continue

        if budget is not None and car["price_from_rub"] > budget:
            continue

        score = 0

        text_blob = " ".join([
            str(car.get("brand", "")),
            str(car.get("model", "")),
            str(car.get("country", "")),
            str(car.get("comment", "")),
        ]).lower()

        query_words = q.split()
        for word in query_words:
            if len(word) >= 3 and word in text_blob:
                score += 2

        if car.get("priority"):
            score += 2

        if under_160_only and car.get("is_under_160_hp"):
            score += 3

        results.append((score, car))

    results.sort(key=lambda x: (x[0], x[1].get("priority", False), -x[1].get("year", 0)), reverse=True)
    return [item[1] for item in results[:limit]]

def build_company_context(user_text: str) -> Dict[str, Any]:
    asked_commission = user_asked_about_commission(user_text)
    preferred_countries = detect_country_preferences(user_text)
    under_160_only = detect_under_160_need(user_text)
    budget = extract_budget(user_text)

    cars = search_cars(
        query=user_text,
        budget=budget,
        preferred_countries=preferred_countries if preferred_countries else None,
        under_160_only=under_160_only,
        limit=4,
    )

    context = {
        "company_name": COMPANY_DATA["name"],
        "assistant_name": COMPANY_DATA["assistant_name"],
        "main_directions": COMPANY_DATA["main_directions"],
        "extra_directions": COMPANY_DATA["extra_directions"],
        "delivery_terms": COMPANY_DATA["delivery_terms"],
        "prepayment_policy": COMPANY_DATA["prepayment_policy"],
        "customs_note": COMPANY_DATA["customs_note"],
        "price_policy": COMPANY_DATA["price_policy"],
        "show_commission": asked_commission,
        "commission_text": COMPANY_DATA["commission_text"] if asked_commission else None,
        "preferred_countries": preferred_countries,
        "budget": budget,
        "under_160_only": under_160_only,
        "car_matches": cars,
        "manager_handoff_text": COMPANY_DATA["manager_handoff_text"],
    }
    return context

def render_context_for_llm(context_data: Dict[str, Any], user_name: str = "") -> str:
    lines = []

    lines.append(f"Компания: {context_data['company_name']}")
    lines.append(f"Основные направления: {', '.join(context_data['main_directions'])}")
    lines.append(f"Дополнительные направления по запросу: {', '.join(context_data['extra_directions'])}")
    lines.append(f"Политика по предоплате: {context_data['prepayment_policy']}")
    lines.append(f"Комментарий по расчётам: {context_data['customs_note']}")
    lines.append(f"Политика по цене: {context_data['price_policy']}")

    if user_name:
        lines.append(f"Имя клиента: {user_name}")

    if context_data.get("preferred_countries"):
        lines.append("Предпочтительные страны клиента: " + ", ".join(context_data["preferred_countries"]))

    if context_data.get("budget"):
        lines.append(f"Бюджет клиента: до {context_data['budget']:,} ₽".replace(",", " "))

    lines.append(f"Фильтр до 160 л.с.: {'да' if context_data.get('under_160_only') else 'нет'}")

    lines.append("Сроки по направлениям:")
    for country, term in context_data["delivery_terms"].items():
        lines.append(f"- {country}: {term}")

    if context_data.get("show_commission") and context_data.get("commission_text"):
        lines.append(f"Информация о комиссии: {context_data['commission_text']}")
    else:
        lines.append("Информацию о комиссии не раскрывать, если пользователь прямо не спрашивал.")

    lines.append("Подходящие автомобили:")
    matches = context_data.get("car_matches", [])
    if not matches:
        lines.append("- Подходящих машин в локальной базе по этому запросу не найдено.")
    else:
        for car in matches:
            lines.append(
                f"- {car['brand']} {car['model']} {car['year']} | "
                f"Страна: {car['country']} | "
                f"Мощность: {car['power_hp']} л.с. | "
                f"Цена: {format_price_range(car['price_from_rub'], car['price_to_rub'])} | "
                f"До 160 л.с.: {'да' if car['is_under_160_hp'] else 'нет'} | "
                f"Ссылка: {car['url']} | "
                f"Комментарий: {car['comment']}"
            )

    lines.append(f"Передача менеджеру, если уместно: {context_data['manager_handoff_text']}")

    return "\n".join(lines)

def build_messages_for_llm(user_id: int, user_text: str) -> List[Dict[str, str]]:
    profile = user_profiles.get(user_id, {})
    user_name = profile.get("name", "")
    context_data = build_company_context(user_text)
    business_context = render_context_for_llm(context_data, user_name=user_name)

    history = user_histories.get(user_id, [])
    trimmed_history = history[-12:]  # не раздуваем контекст

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "Контекст по бизнесу и доступным данным:\n" + business_context},
    ] + trimmed_history + [
        {"role": "user", "content": user_text}
    ]

    return messages

def safe_store_history(user_id: int, role: str, content: str) -> None:
    user_histories.setdefault(user_id, [])
    user_histories[user_id].append({"role": role, "content": content})
    user_histories[user_id] = user_histories[user_id][-20:]

# -----------------------------
# ОБРАБОТЧИКИ
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет.\n\n"
        "Я Игорь, AI-ассистент CARFIRE.\n"
        "Помогу сориентироваться по пригону авто, срокам, направлениям и примерному бюджету.\n\n"
        "Для начала напиши, как тебя зовут.",
        reply_markup=get_empty_keyboard()
    )
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()

    user_profiles[user_id] = {
        "name": name,
        "phone": None,
    }
    user_histories[user_id] = []

    await update.message.reply_text(
        f"{name}, приятно познакомиться.\n\n"
        "Перед тем как продолжим, отправь номер телефона.\n"
        "Так мы сохраним твой запрос и сможем быстро связаться по подбору, если потребуется.",
        reply_markup=get_phone_keyboard()
    )
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = user_profiles.get(user_id, {}).get("name", "друг")

    phone = None
    if update.message.contact:
        phone = update.message.contact.phone_number
    elif update.message.text:
        # если человек просто ввёл номер руками
        phone = update.message.text.strip()

    if not phone:
        await update.message.reply_text(
            "Нужен номер телефона, чтобы продолжить.\n"
            "Можешь отправить его кнопкой ниже или вручную сообщением.",
            reply_markup=get_phone_keyboard()
        )
        return GET_PHONE

    user_profiles[user_id]["phone"] = phone
    logging.info("Новый лид | name=%s | phone=%s | tg_id=%s", name, phone, user_id)

    await update.message.reply_text(
        f"Отлично, {name}.\n\n"
        "Теперь можешь написать, что именно ищешь: марку, модель, бюджет или просто задачу.\n"
        "Например: «нужен кроссовер из Китая до 3 млн и до 160 сил».",
        reply_markup=get_main_keyboard()
    )
    return CHAT

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()

    # Быстрая ручная ветка на менеджера
    if user_text == "📞 Связаться с менеджером":
        await update.message.reply_text(
            f"Передаю тебя менеджеру {COMPANY_DATA['manager_name']}.\n"
            f"Telegram: {COMPANY_DATA['manager_telegram']}",
            reply_markup=get_main_keyboard()
        )
        return CHAT

    # Быстрые сценарии-кнопки
    quick_map = {
        "🚗 Подобрать авто": "Помоги подобрать автомобиль под привоз. Нужны варианты и ориентир по цене.",
        "💰 Прицениться": "Хочу понять примерный бюджет и вилку цены на привоз автомобиля.",
        "⚡ До 160 л.с.": "Покажи варианты до 160 л.с. и объясни, что можно привезти.",
        "🌍 Из каких стран везёте?": "Из каких стран вы привозите автомобили?",
        "⏱ Сроки": "Какие у вас обычно сроки доставки по разным направлениям?",
    }
    llm_input = quick_map.get(user_text, user_text)

    # Если клиент явно готов — можно аккуратно переключать
    if user_needs_manager(llm_input):
        await update.message.reply_text(
            f"Хорошо. Передаю тебя менеджеру {COMPANY_DATA['manager_name']}.\n"
            f"Он уже поможет по точному расчёту и конкретным вариантам: {COMPANY_DATA['manager_telegram']}",
            reply_markup=get_main_keyboard()
        )
        return CHAT

    safe_store_history(user_id, "user", llm_input)

    try:
        messages = build_messages_for_llm(user_id, llm_input)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.35,
            max_tokens=500,
        )

        reply = response.choices[0].message.content.strip()

        # Лёгкая санитарная защита на случай пустого ответа
        if not reply:
            reply = (
                "Могу помочь по направлениям, срокам, бюджету и подбору вариантов. "
                "Напиши, какая машина интересует или какой у тебя бюджет."
            )

        safe_store_history(user_id, "assistant", reply)

        await update.message.reply_text(reply, reply_markup=get_main_keyboard())
        return CHAT

    except Exception as e:
        logging.exception("Ошибка при генерации ответа: %s", e)
        await update.message.reply_text(
            "Что-то пошло не так. Напиши запрос ещё раз — например марку, модель, страну или бюджет.",
            reply_markup=get_main_keyboard()
        )
        return CHAT

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("Не задан TELEGRAM_TOKEN")
    if not GROQ_API_KEY:
        raise ValueError("Не задан GROQ_API_KEY")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
            ],
            GET_PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
            CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)

    logging.info("Бот запущен")
    application.run_polling()

if __name__ == "__main__":
    main()
