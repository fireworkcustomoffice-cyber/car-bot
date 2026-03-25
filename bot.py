import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Bot
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes, ConversationHandler,
)

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MANAGER_IDS = [7328478138, 295158168]

GET_NAME, GET_PHONE, CHAT = range(3)

# ---------------------- БАЗА АВТО ----------------------

KNOWN_CARS = {
    "audi a4": {"brand": "Audi", "model": "A4", "cc": 2000, "hp": 190, "price": 28000},
    "bmw x5": {"brand": "BMW", "model": "X5", "cc": 3000, "hp": 249, "price": 52000},
    "camry": {"brand": "Toyota", "model": "Camry", "cc": 2000, "hp": 173, "price": 20000},
    "rav4": {"brand": "Toyota", "model": "RAV4", "cc": 2000, "hp": 175, "price": 24000},
    "q5": {"brand": "Audi", "model": "Q5", "cc": 2000, "hp": 204, "price": 42000},
}

# ---------------------- УТИЛИТЫ ----------------------

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())

def find_car(text: str):
    t = normalize(text)
    for key, car in KNOWN_CARS.items():
        if key in t:
            return car
    return None

def extract_year(text: str):
    m = re.search(r"\b(20\d{2})\b", text)
    return int(m.group(1)) if m else None

def is_price(text: str):
    return any(x in text.lower() for x in ["цена", "сколько", "стоимость", "расчет", "под ключ"])

def current_year():
    return datetime.now().year

def format_rub(x):
    return f"{int(x):,}".replace(",", " ")

# ---------------------- КУРС ----------------------

usd_cache = {"rate": None, "ts": 0}

async def get_usd():
    import time
    if usd_cache["rate"] and time.time() - usd_cache["ts"] < 3600:
        return usd_cache["rate"]

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://www.cbr-xml-daily.ru/daily_json.js") as r:
                data = await r.json()
                rate = data["Valute"]["USD"]["Value"]
                usd_cache.update({"rate": rate, "ts": time.time()})
                return rate
    except:
        return 90

# ---------------------- РАСЧЕТ ----------------------

def duty(price, cc, age):
    if age < 3:
        return max(price * 0.48, cc * 5.5)
    elif age <= 5:
        return cc * 2.7
    return cc * 4.8

def excise(hp):
    if hp <= 150:
        return hp * 55
    elif hp <= 200:
        return hp * 531
    return hp * 869

async def calc(car, year):
    usd = await get_usd()
    rate = usd + 2
    age = current_year() - year

    price_rub = car["price"] * rate
    duty_rub = duty(car["price"], car["cc"], age) * rate
    exc = excise(car["hp"])

    total = price_rub + duty_rub + exc + 300000

    return {
        "total_min": total - 50000,
        "total_max": total + 50000,
        "rate": rate,
        "age": age
    }

# ---------------------- КЛАВЫ ----------------------

def main_kb():
    return ReplyKeyboardMarkup([
        ["🚗 Подобрать", "💰 Рассчитать"],
        ["📞 Менеджер"]
    ], resize_keyboard=True)

def phone_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )

# ---------------------- СТАРТ ----------------------

user_profiles = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Как тебя зовут?")
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_profiles[update.effective_user.id] = {
        "name": update.message.text
    }
    await update.message.reply_text("Оставь номер", reply_markup=phone_kb())
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone = None

    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text

    user_profiles[user_id]["phone"] = phone

    await update.message.reply_text(
        "Готово 🔥 Напиши авто — сразу скажу цену",
        reply_markup=main_kb()
    )
    return CHAT

# ---------------------- ЧАТ ----------------------

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📞 Менеджер":
        await update.message.reply_text("Пиши: @superluxxx")
        return CHAT

    car = find_car(text)
    year = extract_year(text) or 2023

    if not car:
        await update.message.reply_text(
            "Напиши авто: например BMW X5 2020 — сразу посчитаю 🔥"
        )
        return CHAT

    data = await calc(car, year)

    reply = (
        f"{car['brand']} {car['model']} {year}\n\n"
        f"Под ключ:\n"
        f"от {format_rub(data['total_min'])} ₽\n"
        f"до {format_rub(data['total_max'])} ₽\n\n"
        f"Срок: 3–6 недель"
    )

    await update.message.reply_text(reply)
    return CHAT

# ---------------------- MAIN ----------------------

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT, get_name)],
            GET_PHONE: [MessageHandler(filters.ALL, get_phone)],
            CHAT: [MessageHandler(filters.TEXT, handle)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
