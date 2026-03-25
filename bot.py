import os
import re
import logging
import asyncio
from typing import Dict, List, Any, Optional

import aiohttp
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

MANAGER_IDS = [7328478138, 295158168]

COMPANY_DATA: Dict[str, Any] = {
    "name": "CARFIRE",
    "assistant_name": "Игорь",
    "manager_name": "Евгений",
    "manager_telegram": "@superluxxx",
    "main_directions": ["Китай", "США"],
    "extra_directions": ["Европа", "Канада", "Япония", "Корея"],
    "commission_rub": 90000,
    "hidden_margin_rub": 200000,
    "commission_text": "Наша комиссия — 90 000 ₽. Включает полное сопровождение сделки.",
    "logistics_usd": 2500,
    "china_processing_usd": 1700,
    "transfer_commission_pct": 0.02,
    "sbkts_epts_rus_rub": 75000,
    "prepayment_policy": "По ряду вариантов можем работать без полной предоплаты — зависит от авто и условий.",
    "delivery_terms": {
        "Китай": "3–6 недель",
        "США": "6–10 недель",
        "Европа": "Индивидуально",
        "Канада": "Индивидуально",
        "Япония": "Индивидуально",
        "Корея": "Индивидуально",
    },
    "customs_note": "Итоговая стоимость зависит от курса, мощности, года выпуска и комплектации.",
    "lead_handoff_triggers": [
        "хочу купить", "готов купить", "нужен точный расчет", "нужен точный расчёт",
        "давай оформлять", "хочу подбор", "подберите мне", "оформить заявку",
        "готов к покупке", "как оформить",
    ],
}

CARS_DATABASE: List[Dict[str, Any]] = [
    {
        "brand": "Mazda", "model": "CX-5", "year": 2025,
        "country": "Китай", "power_hp": 155, "engine_cc": 1500,
        "fuel": "бензин", "drive": "передний / полный",
        "price_usd": 18000,
        "is_under_160_hp": True, "is_available": True, "priority": True,
        "url": "https://che168.com",
        "comment": "Проходной кроссовер до 160 л.с. Популярный вариант."
    },
    {
        "brand": "Volkswagen", "model": "Tiguan L", "year": 2024,
        "country": "Китай", "power_hp": 160, "engine_cc": 1400,
        "fuel": "бензин", "drive": "передний / полный",
        "price_usd": 20000,
        "is_under_160_hp": True, "is_available": True, "priority": True,
        "url": "https://che168.com",
        "comment": "Семейный вариант с хорошей ликвидностью."
    },
    {
        "brand": "Toyota", "model": "Camry", "year": 2024,
        "country": "Китай", "power_hp": 173, "engine_cc": 2000,
        "fuel": "бензин", "drive": "передний",
        "price_usd": 22000,
        "is_under_160_hp": False, "is_available": True, "priority": False,
        "url": "https://che168.com",
        "comment": "Популярная модель, выше 160 л.с."
    },
    {
        "brand": "Haval", "model": "H6", "year": 2025,
        "country": "Китай", "power_hp": 150, "engine_cc": 1500,
        "fuel": "бензин", "drive": "полный",
        "price_usd": 15000,
        "is_under_160_hp": True, "is_available": True, "priority": True,
        "url": "https://che168.com",
        "comment": "Бюджетный кроссовер с хорошим оснащением."
    },
    {
        "brand": "Li Auto", "model": "L6", "year": 2024,
        "country": "Китай", "power_hp": 330, "engine_cc": 1500,
        "fuel": "гибрид", "drive": "полный",
        "price_usd": 32000,
        "is_under_160_hp": False, "is_available": True, "priority": False,
        "url": "https://che168.com",
        "comment": "Премиальный гибрид. Большой внедорожник."
    },
]

user_histories: Dict[int, List[Dict[str, str]]] = {}
user_profiles: Dict[int, Dict[str, Any]] = {}

GET_NAME, GET_PHONE, CHAT = range(3)

SYSTEM_PROMPT = """Ты — AI-ассистент компании CARFIRE по пригону автомобилей из-за рубежа.
Тебя зовут Игорь. Ты настоящий ИИ-консультант, не просто бот.

Тон: уверенный, спокойный, дружелюбный. Без воды и навязчивости. Живой язык.

Что умеешь:
1. Подбирать авто под запрос клиента из базы
2. Рассчитывать стоимость под ключ и показывать вилку цены
3. Объяснять нюансы — до 160 л.с., таможня, сроки, документы
4. Передавать клиента менеджеру когда он готов

Жёсткие правила:
1. Используй только данные из контекста — не придумывай
2. Комиссию не называй если клиент не спросил
3. Не гони к менеджеру при каждом вопросе — сначала помоги сам
4. К менеджеру только если: готов купить, просит точный расчёт, нестандартный кейс
5. Не здоровайся повторно — просто продолжай разговор
6. Показывай 2–3 варианта авто если есть подходящие
7. 3–5 предложений в ответе
8. Только русский язык
9. Если спросят кто ты — честно скажи что ИИ-ассистент

Когда показываешь расчёт стоимости — используй данные из контекста.
Показывай вилку: от минимума до максимума.
Разбивай по статьям чтобы клиент видел из чего складывается цена.

Передача менеджеру:
"Передаю тебя менеджеру Евгению — он сделает точный расчёт: @superluxxx"
"""

client = Groq(api_key=GROQ_API_KEY)


# -----------------------------
# КУРС ЦБ
# -----------------------------
_usd_rate_cache: Dict[str, Any] = {"rate": None, "ts": 0}

async def get_usd_rate() -> float:
    import time
    now = time.time()
    if _usd_rate_cache["rate"] and now - _usd_rate_cache["ts"] < 3600:
        return _usd_rate_cache["rate"]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json(content_type=None)
                rate = data["Valute"]["USD"]["Value"]
                _usd_rate_cache["rate"] = rate
                _usd_rate_cache["ts"] = now
                return rate
    except Exception as e:
        logging.error(f"Ошибка получения курса ЦБ: {e}")
        return 90.0


# -----------------------------
# ТАМОЖЕННЫЙ КАЛЬКУЛЯТОР
# -----------------------------
def calc_customs(price_eur: float, engine_cc: int, age_years: int, power_hp: int) -> Dict[str, float]:
    """
    Расчёт таможенных платежей для физлиц (ЕАЭС).
    Возраст 3-5 лет — ставки для подержанных авто.
    """
    if age_years <= 3:
        # Новые авто (до 3 лет)
        if price_eur <= 8500:
            rate = max(price_eur * 0.54, engine_cc * 2.5)
        elif price_eur <= 16700:
            rate = max(price_eur * 0.48, engine_cc * 3.5)
        elif price_eur <= 42300:
            rate = max(price_eur * 0.48, engine_cc * 5.5)
        elif price_eur <= 84500:
            rate = max(price_eur * 0.48, engine_cc * 7.5)
        elif price_eur <= 169000:
            rate = max(price_eur * 0.48, engine_cc * 15.0)
        else:
            rate = max(price_eur * 0.48, engine_cc * 20.0)
    else:
        # Б/у 3-5 лет
        if engine_cc <= 1000:
            rate = engine_cc * 1.5
        elif engine_cc <= 1500:
            rate = engine_cc * 1.7
        elif engine_cc <= 1800:
            rate = engine_cc * 2.5
        elif engine_cc <= 2300:
            rate = engine_cc * 2.7
        elif engine_cc <= 3000:
            rate = engine_cc * 3.0
        else:
            rate = engine_cc * 3.6

    # Утилизационный сбор (физлица, б/у)
    base = 20000
    if engine_cc <= 1000:
        util = base * 0.17
    elif engine_cc <= 2000:
        util = base * 0.17
    elif engine_cc <= 3000:
        util = base * 0.17
    else:
        util = base * 0.17

    # Акциз (рублей за л.с.)
    if power_hp <= 90:
        excise = 0
    elif power_hp <= 150:
        excise = power_hp * 55
    elif power_hp <= 200:
        excise = power_hp * 531
    elif power_hp <= 300:
        excise = power_hp * 869
    else:
        excise = power_hp * 1063

    return {
        "customs_duty_eur": rate,
        "util_rub": util,
        "excise_rub": excise,
    }


async def calc_total(car: Dict, usd_rate: float) -> Dict[str, Any]:
    rate = usd_rate + 2  # курс ЦБ + 2 рубля
    eur_rate = rate * 0.93  # примерный курс евро

    price_rub = car["price_usd"] * rate
    china_processing_rub = COMPANY_DATA["china_processing_usd"] * rate

    # База для комиссии за перевод = цена авто + оформление в Китае
    transfer_base_rub = price_rub + china_processing_rub
    transfer_commission_rub = transfer_base_rub * COMPANY_DATA["transfer_commission_pct"]

    logistics_rub = COMPANY_DATA["logistics_usd"] * rate

    # Таможня
    price_eur = car["price_usd"] * 0.93
    age = 2025 - car["year"]
    customs = calc_customs(price_eur, car["engine_cc"], age, car["power_hp"])
    customs_duty_rub = customs["customs_duty_eur"] * eur_rate
    util_rub = customs["util_rub"]
    excise_rub = customs["excise_rub"]

    sbkts_rub = COMPANY_DATA["sbkts_epts_rus_rub"]
    our_commission_rub = COMPANY_DATA["commission_rub"]
    hidden_margin_rub = COMPANY_DATA["hidden_margin_rub"]

    # Итог (с учётом скрытой маржи)
    total = (
        price_rub
        + china_processing_rub
        + transfer_commission_rub
        + logistics_rub
        + customs_duty_rub
        + util_rub
        + excise_rub
        + sbkts_rub
        + our_commission_rub
        + hidden_margin_rub
    )

    margin = 50000
    return {
        "price_rub": price_rub,
        "china_processing_rub": china_processing_rub,
        "transfer_commission_rub": transfer_commission_rub,
        "logistics_rub": logistics_rub,
        "customs_duty_rub": customs_duty_rub,
        "util_rub": util_rub,
        "excise_rub": excise_rub,
        "sbkts_rub": sbkts_rub,
        "our_commission_rub": our_commission_rub,
        "total_min": total - margin,
        "total_max": total + margin,
        "usd_rate": rate,
    }


def format_calc(car: Dict, calc: Dict) -> str:
    def r(x): return f"{int(round(x)):,}".replace(",", " ")
    lines = [
        f"💰 Расчёт стоимости под ключ — {car['brand']} {car['model']} {car['year']}",
        f"",
        f"🚗 Цена авто в Китае: {r(calc['price_rub'])} ₽",
        f"📦 Оформление в Китае: {r(calc['china_processing_rub'])} ₽",
        f"💳 Комиссия за перевод (2%): {r(calc['transfer_commission_rub'])} ₽",
        f"🚢 Доставка до России: {r(calc['logistics_rub'])} ₽",
        f"🛃 Таможенная пошлина: {r(calc['customs_duty_rub'])} ₽",
        f"♻️ Утилизационный сбор: {r(calc['util_rub'])} ₽",
        f"⚡ Акциз: {r(calc['excise_rub'])} ₽",
        f"📋 СБКТС + ЭПТС + русификация: {r(calc['sbkts_rub'])} ₽",
        f"🤝 Комиссия CARFIRE: {r(calc['our_commission_rub'])} ₽",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📌 Итого под ключ: от {r(calc['total_min'])} до {r(calc['total_max'])} ₽",
        f"",
        f"Курс USD: {calc['usd_rate']:.2f} ₽",
        f"Расчёт ориентировочный. Точную сумму подтвердит менеджер Евгений: @superluxxx",
    ]
    return "\n".join(lines)


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

def wants_calc(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in ["посчитай", "рассчитай", "сколько стоит под ключ",
                                  "итого", "расчёт", "расчет", "под ключ", "цена под ключ"])

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

def search_cars(query: str, budget_rub: Optional[int], countries: List[str],
                under_160: bool, usd_rate: float = 90.0) -> List[Dict]:
    q = normalize(query)
    results = []
    for car in CARS_DATABASE:
        if not car.get("is_available"):
            continue
        if countries and car["country"] not in countries:
            continue
        if under_160 and not car.get("is_under_160_hp"):
            continue
        if budget_rub:
            approx_price = car["price_usd"] * (usd_rate + 2) * 1.5
            if approx_price > budget_rub:
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

def build_context(user_id: int, user_text: str, usd_rate: float) -> str:
    profile = user_profiles.get(user_id, {})
    name = profile.get("name", "")
    budget = extract_budget(user_text)
    countries = detect_countries(user_text)
    under_160 = detect_under_160(user_text)
    show_commission = asked_commission(user_text)
    cars = search_cars(user_text, budget, countries, under_160, usd_rate)

    lines = [
        f"Компания: {COMPANY_DATA['name']}",
        f"Основные направления: {', '.join(COMPANY_DATA['main_directions'])}",
        f"По запросу: {', '.join(COMPANY_DATA['extra_directions'])}",
        f"Предоплата: {COMPANY_DATA['prepayment_policy']}",
        f"Расчёт: {COMPANY_DATA['customs_note']}",
        f"Текущий курс USD: {usd_rate + 2:.2f} ₽ (ЦБ + 2 ₽)",
    ]

    if name:
        lines.append(f"Имя клиента: {name}")
    if budget:
        lines.append(f"Бюджет клиента: до {budget:,} ₽".replace(",", " "))
    if countries:
        lines.append(f"Интересующие страны: {', '.join(countries)}")
    if under_160:
        lines.append("Клиент ищет авто до 160 л.с.")

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
            approx_rub = int(car["price_usd"] * (usd_rate + 2))
            lines.append(
                f"  • {car['brand']} {car['model']} {car['year']} | "
                f"{car['power_hp']} л.с. | ~{approx_rub:,} ₽ цена авто | "
                f"{'✅ до 160 л.с.' if car['is_under_160_hp'] else '⚠️ выше 160 л.с.'} | "
                f"{car['url']} | {car['comment']}"
            )
    else:
        lines.append("  Подходящих авто в базе не найдено. Предложи связаться с менеджером.")

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
        [KeyboardButton("🚗 Подобрать авто"), KeyboardButton("💰 Рассчитать стоимость")],
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
        "Помогу подобрать авто из-за рубежа, рассчитать стоимость под ключ "
        "и ответить на все вопросы по пригону.\n\n"
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
        f"когда дойдёт до конкретики.",
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
        f"Могу сразу рассчитать стоимость под ключ по актуальному курсу ЦБ 👇",
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
        "💰 Рассчитать стоимость": "Рассчитай стоимость под ключ для подходящего авто из базы.",
        "⚡ До 160 л.с.": "Покажи варианты авто до 160 л.с. и рассчитай стоимость под ключ.",
        "🌍 Из каких стран везёте?": "Из каких стран вы привозите автомобили и какие особенности?",
        "⏱ Сроки доставки": "Какие сроки доставки по разным направлениям?",
    }
    llm_input = quick_map.get(user_text, user_text)

    if needs_manager(llm_input):
        await update.message.reply_text(
            "Понял, передаю тебя менеджеру Евгению: @superluxxx",
            reply_markup=main_keyboard()
        )
        return CHAT

    usd_rate = await get_usd_rate()

    # Если клиент просит расчёт — считаем для первого подходящего авто
    if wants_calc(llm_input):
        budget = extract_budget(llm_input)
        countries = detect_countries(llm_input)
        under_160 = detect_under_160(llm_input)
        cars = search_cars(llm_input, budget, countries, under_160, usd_rate)
        if cars:
            car = cars[0]
            calc = await calc_total(car, usd_rate)
            calc_text = format_calc(car, calc)
            await update.message.reply_text(calc_text, reply_markup=main_keyboard())
            return CHAT

    user_histories.setdefault(user_id, [])
    user_histories[user_id].append({"role": "user", "content": llm_input})
    user_histories[user_id] = user_histories[user_id][-14:]

    context_block = build_context(user_id, llm_input, usd_rate)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": "Бизнес-контекст:\n" + context_block},
            ] + user_histories[user_id],
            temperature=0.35,
            max_tokens=600,
        )

        reply = response.choices[0].message.content.strip()
        if not reply:
            reply = "Напиши что именно ищешь — марку, модель, бюджет или страну."

        user_histories[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply, reply_markup=main_keyboard())

    except Exception as e:
        logging.exception(f"Ошибка LLM: {e}")
        await update.message.reply_text("Что-то пошло не так. Попробуй ещё раз.", reply_markup=main_keyboard())

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
