import os
import re
import logging
from typing import Dict, List, Any, Optional

import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, Bot
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes, ConversationHandler,
)
from groq import Groq

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MANAGER_IDS = [7328478138, 295158168]

COMPANY_DATA: Dict[str, Any] = {
    "name": "CARFIRE",
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
    "prepayment_policy": "По ряду вариантов можем работать без полной предоплаты.",
    "delivery_terms": {
        "Китай": "3–6 недель",
        "США": "6–10 недель",
        "Европа": "Индивидуально",
        "Канада": "Индивидуально",
        "Япония": "Индивидуально",
        "Корея": "Индивидуально",
    },
    "lead_handoff_triggers": [
        "хочу купить", "готов купить", "нужен точный расчет", "нужен точный расчёт",
        "давай оформлять", "оформить заявку", "готов к покупке", "как оформить",
    ],
}

CARS_DATABASE: List[Dict[str, Any]] = [
    {"brand": "Mazda", "model": "CX-5", "year": 2025, "country": "Китай",
     "power_hp": 155, "engine_cc": 1500, "price_usd": 18000,
     "is_under_160_hp": True, "is_available": True, "priority": True,
     "url": "https://che168.com", "comment": "Проходной кроссовер до 160 л.с."},
    {"brand": "Volkswagen", "model": "Tiguan L", "year": 2024, "country": "Китай",
     "power_hp": 160, "engine_cc": 1400, "price_usd": 20000,
     "is_under_160_hp": True, "is_available": True, "priority": True,
     "url": "https://che168.com", "comment": "Семейный кроссовер с хорошей ликвидностью."},
    {"brand": "Toyota", "model": "Camry", "year": 2024, "country": "Китай",
     "power_hp": 173, "engine_cc": 2000, "price_usd": 22000,
     "is_under_160_hp": False, "is_available": True, "priority": False,
     "url": "https://che168.com", "comment": "Популярная модель, выше 160 л.с."},
    {"brand": "Haval", "model": "H6", "year": 2025, "country": "Китай",
     "power_hp": 150, "engine_cc": 1500, "price_usd": 15000,
     "is_under_160_hp": True, "is_available": True, "priority": True,
     "url": "https://che168.com", "comment": "Бюджетный кроссовер с хорошим оснащением."},
    {"brand": "Li Auto", "model": "L6", "year": 2024, "country": "Китай",
     "power_hp": 330, "engine_cc": 1500, "price_usd": 32000,
     "is_under_160_hp": False, "is_available": True, "priority": False,
     "url": "https://che168.com", "comment": "Премиальный гибрид."},
]

# Словарь популярных авто — все варианты написания рус/англ
KNOWN_CARS: Dict[str, Dict] = {
    # Audi
    "audi a1": {"brand": "Audi", "model": "A1", "engine_cc": 1000, "power_hp": 116, "price_usd": 18000},
    "audi a3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 27000},
    "ауди а3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 27000},
    "ауди а 3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 27000},
    "audi a 3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 27000},
    "a3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 27000},
    "а3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 27000},
    "audi a4": {"brand": "Audi", "model": "A4", "engine_cc": 2000, "power_hp": 190, "price_usd": 35000},
    "ауди а4": {"brand": "Audi", "model": "A4", "engine_cc": 2000, "power_hp": 190, "price_usd": 35000},
    "а4": {"brand": "Audi", "model": "A4", "engine_cc": 2000, "power_hp": 190, "price_usd": 35000},
    "audi a5": {"brand": "Audi", "model": "A5", "engine_cc": 2000, "power_hp": 190, "price_usd": 40000},
    "ауди а5": {"brand": "Audi", "model": "A5", "engine_cc": 2000, "power_hp": 190, "price_usd": 40000},
    "а5": {"brand": "Audi", "model": "A5", "engine_cc": 2000, "power_hp": 190, "price_usd": 40000},
    "audi a6": {"brand": "Audi", "model": "A6", "engine_cc": 2000, "power_hp": 204, "price_usd": 45000},
    "ауди а6": {"brand": "Audi", "model": "A6", "engine_cc": 2000, "power_hp": 204, "price_usd": 45000},
    "а6": {"brand": "Audi", "model": "A6", "engine_cc": 2000, "power_hp": 204, "price_usd": 45000},
    "audi a7": {"brand": "Audi", "model": "A7", "engine_cc": 3000, "power_hp": 340, "price_usd": 65000},
    "audi a8": {"brand": "Audi", "model": "A8", "engine_cc": 3000, "power_hp": 340, "price_usd": 85000},
    "audi q3": {"brand": "Audi", "model": "Q3", "engine_cc": 1500, "power_hp": 150, "price_usd": 32000},
    "ауди q3": {"brand": "Audi", "model": "Q3", "engine_cc": 1500, "power_hp": 150, "price_usd": 32000},
    "audi q5": {"brand": "Audi", "model": "Q5", "engine_cc": 2000, "power_hp": 204, "price_usd": 50000},
    "ауди q5": {"brand": "Audi", "model": "Q5", "engine_cc": 2000, "power_hp": 204, "price_usd": 50000},
    "audi q7": {"brand": "Audi", "model": "Q7", "engine_cc": 3000, "power_hp": 249, "price_usd": 70000},
    "ауди q7": {"brand": "Audi", "model": "Q7", "engine_cc": 3000, "power_hp": 249, "price_usd": 70000},
    "audi q8": {"brand": "Audi", "model": "Q8", "engine_cc": 3000, "power_hp": 340, "price_usd": 90000},
    # BMW
    "bmw 1": {"brand": "BMW", "model": "1 Series", "engine_cc": 1500, "power_hp": 140, "price_usd": 22000},
    "бмв 1": {"brand": "BMW", "model": "1 Series", "engine_cc": 1500, "power_hp": 140, "price_usd": 22000},
    "bmw 3": {"brand": "BMW", "model": "3 Series", "engine_cc": 2000, "power_hp": 184, "price_usd": 35000},
    "бмв 3": {"brand": "BMW", "model": "3 Series", "engine_cc": 2000, "power_hp": 184, "price_usd": 35000},
    "bmw 5": {"brand": "BMW", "model": "5 Series", "engine_cc": 2000, "power_hp": 190, "price_usd": 50000},
    "бмв 5": {"brand": "BMW", "model": "5 Series", "engine_cc": 2000, "power_hp": 190, "price_usd": 50000},
    "bmw 7": {"brand": "BMW", "model": "7 Series", "engine_cc": 3000, "power_hp": 340, "price_usd": 85000},
    "бмв 7": {"brand": "BMW", "model": "7 Series", "engine_cc": 3000, "power_hp": 340, "price_usd": 85000},
    "bmw x1": {"brand": "BMW", "model": "X1", "engine_cc": 1500, "power_hp": 136, "price_usd": 28000},
    "бмв х1": {"brand": "BMW", "model": "X1", "engine_cc": 1500, "power_hp": 136, "price_usd": 28000},
    "bmw x3": {"brand": "BMW", "model": "X3", "engine_cc": 2000, "power_hp": 184, "price_usd": 45000},
    "бмв х3": {"brand": "BMW", "model": "X3", "engine_cc": 2000, "power_hp": 184, "price_usd": 45000},
    "bmw x5": {"brand": "BMW", "model": "X5", "engine_cc": 3000, "power_hp": 249, "price_usd": 60000},
    "бмв х5": {"brand": "BMW", "model": "X5", "engine_cc": 3000, "power_hp": 249, "price_usd": 60000},
    "bmw x6": {"brand": "BMW", "model": "X6", "engine_cc": 3000, "power_hp": 249, "price_usd": 65000},
    "бмв х6": {"brand": "BMW", "model": "X6", "engine_cc": 3000, "power_hp": 249, "price_usd": 65000},
    "bmw x7": {"brand": "BMW", "model": "X7", "engine_cc": 3000, "power_hp": 340, "price_usd": 90000},
    "бмв х7": {"brand": "BMW", "model": "X7", "engine_cc": 3000, "power_hp": 340, "price_usd": 90000},
    # Mercedes
    "mercedes a": {"brand": "Mercedes", "model": "A-Class", "engine_cc": 1300, "power_hp": 136, "price_usd": 25000},
    "мерседес а": {"brand": "Mercedes", "model": "A-Class", "engine_cc": 1300, "power_hp": 136, "price_usd": 25000},
    "mercedes c": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 38000},
    "мерседес с": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 38000},
    "мерс с": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 38000},
    "мерс c": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 38000},
    "mercedes e": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 55000},
    "мерседес е": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 55000},
    "мерс е": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 55000},
    "мерс e": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 55000},
    "mercedes s": {"brand": "Mercedes", "model": "S-Class", "engine_cc": 3000, "power_hp": 340, "price_usd": 100000},
    "mercedes glc": {"brand": "Mercedes", "model": "GLC", "engine_cc": 2000, "power_hp": 204, "price_usd": 55000},
    "mercedes gle": {"brand": "Mercedes", "model": "GLE", "engine_cc": 3000, "power_hp": 330, "price_usd": 80000},
    "mercedes gls": {"brand": "Mercedes", "model": "GLS", "engine_cc": 3000, "power_hp": 330, "price_usd": 95000},
    "mercedes g": {"brand": "Mercedes", "model": "G-Class", "engine_cc": 4000, "power_hp": 422, "price_usd": 130000},
    "гелендваген": {"brand": "Mercedes", "model": "G-Class", "engine_cc": 4000, "power_hp": 422, "price_usd": 130000},
    # Toyota
    "toyota camry": {"brand": "Toyota", "model": "Camry", "engine_cc": 2000, "power_hp": 173, "price_usd": 22000},
    "camry": {"brand": "Toyota", "model": "Camry", "engine_cc": 2000, "power_hp": 173, "price_usd": 22000},
    "камри": {"brand": "Toyota", "model": "Camry", "engine_cc": 2000, "power_hp": 173, "price_usd": 22000},
    "toyota rav4": {"brand": "Toyota", "model": "RAV4", "engine_cc": 2000, "power_hp": 175, "price_usd": 28000},
    "rav4": {"brand": "Toyota", "model": "RAV4", "engine_cc": 2000, "power_hp": 175, "price_usd": 28000},
    "рав4": {"brand": "Toyota", "model": "RAV4", "engine_cc": 2000, "power_hp": 175, "price_usd": 28000},
    "toyota land cruiser": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 70000},
    "land cruiser": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 70000},
    "ленд крузер": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 70000},
    "крузак": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 70000},
    "toyota highlander": {"brand": "Toyota", "model": "Highlander", "engine_cc": 2500, "power_hp": 238, "price_usd": 40000},
    "highlander": {"brand": "Toyota", "model": "Highlander", "engine_cc": 2500, "power_hp": 238, "price_usd": 40000},
    "хайлендер": {"brand": "Toyota", "model": "Highlander", "engine_cc": 2500, "power_hp": 238, "price_usd": 40000},
    "toyota corolla": {"brand": "Toyota", "model": "Corolla", "engine_cc": 1600, "power_hp": 122, "price_usd": 18000},
    "corolla": {"brand": "Toyota", "model": "Corolla", "engine_cc": 1600, "power_hp": 122, "price_usd": 18000},
    "королла": {"brand": "Toyota", "model": "Corolla", "engine_cc": 1600, "power_hp": 122, "price_usd": 18000},
    # Lexus
    "lexus rx": {"brand": "Lexus", "model": "RX", "engine_cc": 2000, "power_hp": 238, "price_usd": 45000},
    "лексус rx": {"brand": "Lexus", "model": "RX", "engine_cc": 2000, "power_hp": 238, "price_usd": 45000},
    "лексус рх": {"brand": "Lexus", "model": "RX", "engine_cc": 2000, "power_hp": 238, "price_usd": 45000},
    "lexus lx": {"brand": "Lexus", "model": "LX", "engine_cc": 3500, "power_hp": 415, "price_usd": 90000},
    "лексус lx": {"brand": "Lexus", "model": "LX", "engine_cc": 3500, "power_hp": 415, "price_usd": 90000},
    "lexus es": {"brand": "Lexus", "model": "ES", "engine_cc": 2500, "power_hp": 218, "price_usd": 35000},
    "лексус es": {"brand": "Lexus", "model": "ES", "engine_cc": 2500, "power_hp": 218, "price_usd": 35000},
    "lexus gx": {"brand": "Lexus", "model": "GX", "engine_cc": 4000, "power_hp": 296, "price_usd": 60000},
    # Volkswagen
    "volkswagen passat": {"brand": "Volkswagen", "model": "Passat", "engine_cc": 2000, "power_hp": 150, "price_usd": 25000},
    "пассат": {"brand": "Volkswagen", "model": "Passat", "engine_cc": 2000, "power_hp": 150, "price_usd": 25000},
    "volkswagen tiguan": {"brand": "Volkswagen", "model": "Tiguan", "engine_cc": 1400, "power_hp": 150, "price_usd": 28000},
    "тигуан": {"brand": "Volkswagen", "model": "Tiguan", "engine_cc": 1400, "power_hp": 150, "price_usd": 28000},
    "volkswagen golf": {"brand": "Volkswagen", "model": "Golf", "engine_cc": 1400, "power_hp": 150, "price_usd": 22000},
    "гольф": {"brand": "Volkswagen", "model": "Golf", "engine_cc": 1400, "power_hp": 150, "price_usd": 22000},
    "volkswagen polo": {"brand": "Volkswagen", "model": "Polo", "engine_cc": 1000, "power_hp": 110, "price_usd": 16000},
    "поло": {"brand": "Volkswagen", "model": "Polo", "engine_cc": 1000, "power_hp": 110, "price_usd": 16000},
    "volkswagen touareg": {"brand": "Volkswagen", "model": "Touareg", "engine_cc": 3000, "power_hp": 249, "price_usd": 55000},
    "туарег": {"brand": "Volkswagen", "model": "Touareg", "engine_cc": 3000, "power_hp": 249, "price_usd": 55000},
    # Hyundai
    "hyundai tucson": {"brand": "Hyundai", "model": "Tucson", "engine_cc": 1600, "power_hp": 150, "price_usd": 22000},
    "туксон": {"brand": "Hyundai", "model": "Tucson", "engine_cc": 1600, "power_hp": 150, "price_usd": 22000},
    "hyundai palisade": {"brand": "Hyundai", "model": "Palisade", "engine_cc": 2500, "power_hp": 196, "price_usd": 38000},
    "палисейд": {"brand": "Hyundai", "model": "Palisade", "engine_cc": 2500, "power_hp": 196, "price_usd": 38000},
    "hyundai santafe": {"brand": "Hyundai", "model": "Santa Fe", "engine_cc": 2000, "power_hp": 180, "price_usd": 30000},
    "санта фе": {"brand": "Hyundai", "model": "Santa Fe", "engine_cc": 2000, "power_hp": 180, "price_usd": 30000},
    "hyundai sonata": {"brand": "Hyundai", "model": "Sonata", "engine_cc": 2000, "power_hp": 150, "price_usd": 22000},
    "соната": {"brand": "Hyundai", "model": "Sonata", "engine_cc": 2000, "power_hp": 150, "price_usd": 22000},
    # Kia
    "kia sportage": {"brand": "Kia", "model": "Sportage", "engine_cc": 1600, "power_hp": 150, "price_usd": 22000},
    "спортейдж": {"brand": "Kia", "model": "Sportage", "engine_cc": 1600, "power_hp": 150, "price_usd": 22000},
    "kia sorento": {"brand": "Kia", "model": "Sorento", "engine_cc": 2500, "power_hp": 196, "price_usd": 35000},
    "соренто": {"brand": "Kia", "model": "Sorento", "engine_cc": 2500, "power_hp": 196, "price_usd": 35000},
    "kia stinger": {"brand": "Kia", "model": "Stinger", "engine_cc": 2000, "power_hp": 255, "price_usd": 30000},
    "стингер": {"brand": "Kia", "model": "Stinger", "engine_cc": 2000, "power_hp": 255, "price_usd": 30000},
    "kia k5": {"brand": "Kia", "model": "K5", "engine_cc": 1600, "power_hp": 180, "price_usd": 22000},
    "kia telluride": {"brand": "Kia", "model": "Telluride", "engine_cc": 3500, "power_hp": 291, "price_usd": 40000},
    # Mazda
    "mazda cx-5": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 18000},
    "мазда cx-5": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 18000},
    "mazda cx5": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 18000},
    "мазда сх5": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 18000},
    "mazda cx-9": {"brand": "Mazda", "model": "CX-9", "engine_cc": 2500, "power_hp": 228, "price_usd": 32000},
    "mazda 6": {"brand": "Mazda", "model": "6", "engine_cc": 2000, "power_hp": 165, "price_usd": 20000},
    "мазда 6": {"brand": "Mazda", "model": "6", "engine_cc": 2000, "power_hp": 165, "price_usd": 20000},
    "мазда": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 18000},
    # Chinese brands
    "haval h6": {"brand": "Haval", "model": "H6", "engine_cc": 1500, "power_hp": 150, "price_usd": 15000},
    "haval h9": {"brand": "Haval", "model": "H9", "engine_cc": 2000, "power_hp": 218, "price_usd": 28000},
    "geely atlas": {"brand": "Geely", "model": "Atlas", "engine_cc": 1500, "power_hp": 150, "price_usd": 14000},
    "chery tiggo": {"brand": "Chery", "model": "Tiggo 7", "engine_cc": 1500, "power_hp": 150, "price_usd": 14000},
    "byd han": {"brand": "BYD", "model": "Han", "engine_cc": 1500, "power_hp": 218, "price_usd": 25000},
    "byd seal": {"brand": "BYD", "model": "Seal", "engine_cc": 1500, "power_hp": 313, "price_usd": 22000},
    "li auto l6": {"brand": "Li Auto", "model": "L6", "engine_cc": 1500, "power_hp": 330, "price_usd": 32000},
    "li auto l9": {"brand": "Li Auto", "model": "L9", "engine_cc": 1500, "power_hp": 449, "price_usd": 50000},
    "exeed": {"brand": "Exeed", "model": "TXL", "engine_cc": 1500, "power_hp": 150, "price_usd": 16000},
    "omoda": {"brand": "Omoda", "model": "C5", "engine_cc": 1600, "power_hp": 147, "price_usd": 15000},
    "jaecoo": {"brand": "Jaecoo", "model": "J7", "engine_cc": 1500, "power_hp": 147, "price_usd": 16000},
    # Porsche
    "porsche cayenne": {"brand": "Porsche", "model": "Cayenne", "engine_cc": 3000, "power_hp": 340, "price_usd": 85000},
    "кайен": {"brand": "Porsche", "model": "Cayenne", "engine_cc": 3000, "power_hp": 340, "price_usd": 85000},
    "порше кайен": {"brand": "Porsche", "model": "Cayenne", "engine_cc": 3000, "power_hp": 340, "price_usd": 85000},
    "porsche macan": {"brand": "Porsche", "model": "Macan", "engine_cc": 2000, "power_hp": 265, "price_usd": 60000},
    "макан": {"brand": "Porsche", "model": "Macan", "engine_cc": 2000, "power_hp": 265, "price_usd": 60000},
    "porsche panamera": {"brand": "Porsche", "model": "Panamera", "engine_cc": 3000, "power_hp": 330, "price_usd": 90000},
    # Land Rover
    "range rover": {"brand": "Land Rover", "model": "Range Rover", "engine_cc": 3000, "power_hp": 350, "price_usd": 90000},
    "рейндж ровер": {"brand": "Land Rover", "model": "Range Rover", "engine_cc": 3000, "power_hp": 350, "price_usd": 90000},
    "range rover sport": {"brand": "Land Rover", "model": "Range Rover Sport", "engine_cc": 3000, "power_hp": 300, "price_usd": 70000},
    "defender": {"brand": "Land Rover", "model": "Defender", "engine_cc": 2000, "power_hp": 300, "price_usd": 55000},
    "дефендер": {"brand": "Land Rover", "model": "Defender", "engine_cc": 2000, "power_hp": 300, "price_usd": 55000},
    # Volvo
    "volvo xc90": {"brand": "Volvo", "model": "XC90", "engine_cc": 2000, "power_hp": 249, "price_usd": 60000},
    "volvo xc60": {"brand": "Volvo", "model": "XC60", "engine_cc": 2000, "power_hp": 190, "price_usd": 45000},
    "volvo xc40": {"brand": "Volvo", "model": "XC40", "engine_cc": 1500, "power_hp": 156, "price_usd": 35000},
    # Skoda
    "skoda octavia": {"brand": "Skoda", "model": "Octavia", "engine_cc": 1400, "power_hp": 150, "price_usd": 22000},
    "октавия": {"brand": "Skoda", "model": "Octavia", "engine_cc": 1400, "power_hp": 150, "price_usd": 22000},
    "skoda kodiaq": {"brand": "Skoda", "model": "Kodiaq", "engine_cc": 2000, "power_hp": 190, "price_usd": 32000},
    "кодиак": {"brand": "Skoda", "model": "Kodiaq", "engine_cc": 2000, "power_hp": 190, "price_usd": 32000},
    # Nissan
    "nissan x-trail": {"brand": "Nissan", "model": "X-Trail", "engine_cc": 1500, "power_hp": 163, "price_usd": 25000},
    "иксрейл": {"brand": "Nissan", "model": "X-Trail", "engine_cc": 1500, "power_hp": 163, "price_usd": 25000},
    "nissan patrol": {"brand": "Nissan", "model": "Patrol", "engine_cc": 4000, "power_hp": 275, "price_usd": 55000},
    "патрол": {"brand": "Nissan", "model": "Patrol", "engine_cc": 4000, "power_hp": 275, "price_usd": 55000},
    "nissan qashqai": {"brand": "Nissan", "model": "Qashqai", "engine_cc": 1300, "power_hp": 140, "price_usd": 22000},
    "кашкай": {"brand": "Nissan", "model": "Qashqai", "engine_cc": 1300, "power_hp": 140, "price_usd": 22000},
    # Honda
    "honda cr-v": {"brand": "Honda", "model": "CR-V", "engine_cc": 1500, "power_hp": 193, "price_usd": 28000},
    "honda pilot": {"brand": "Honda", "model": "Pilot", "engine_cc": 3500, "power_hp": 285, "price_usd": 38000},
    "honda accord": {"brand": "Honda", "model": "Accord", "engine_cc": 1500, "power_hp": 192, "price_usd": 24000},
    "аккорд": {"brand": "Honda", "model": "Accord", "engine_cc": 1500, "power_hp": 192, "price_usd": 24000},
    # Subaru
    "subaru outback": {"brand": "Subaru", "model": "Outback", "engine_cc": 2500, "power_hp": 175, "price_usd": 28000},
    "аутбэк": {"brand": "Subaru", "model": "Outback", "engine_cc": 2500, "power_hp": 175, "price_usd": 28000},
    "subaru forester": {"brand": "Subaru", "model": "Forester", "engine_cc": 2000, "power_hp": 150, "price_usd": 22000},
    "форестер": {"brand": "Subaru", "model": "Forester", "engine_cc": 2000, "power_hp": 150, "price_usd": 22000},
    # Ford/Dodge/American
    "ford mustang": {"brand": "Ford", "model": "Mustang", "engine_cc": 5000, "power_hp": 450, "price_usd": 35000},
    "мустанг": {"brand": "Ford", "model": "Mustang", "engine_cc": 5000, "power_hp": 450, "price_usd": 35000},
    "ford explorer": {"brand": "Ford", "model": "Explorer", "engine_cc": 3000, "power_hp": 300, "price_usd": 40000},
    "dodge charger": {"brand": "Dodge", "model": "Charger", "engine_cc": 5700, "power_hp": 370, "price_usd": 30000},
    "dodge challenger": {"brand": "Dodge", "model": "Challenger", "engine_cc": 5700, "power_hp": 375, "price_usd": 30000},
    "dodge durango": {"brand": "Dodge", "model": "Durango", "engine_cc": 3600, "power_hp": 290, "price_usd": 38000},
    "jeep grand cherokee": {"brand": "Jeep", "model": "Grand Cherokee", "engine_cc": 3600, "power_hp": 290, "price_usd": 42000},
    "гранд чероки": {"brand": "Jeep", "model": "Grand Cherokee", "engine_cc": 3600, "power_hp": 290, "price_usd": 42000},
    "cadillac escalade": {"brand": "Cadillac", "model": "Escalade", "engine_cc": 6200, "power_hp": 420, "price_usd": 75000},
    "эскалейд": {"brand": "Cadillac", "model": "Escalade", "engine_cc": 6200, "power_hp": 420, "price_usd": 75000},
    # Mitsubishi
    "mitsubishi outlander": {"brand": "Mitsubishi", "model": "Outlander", "engine_cc": 2000, "power_hp": 145, "price_usd": 22000},
    "аутлендер": {"brand": "Mitsubishi", "model": "Outlander", "engine_cc": 2000, "power_hp": 145, "price_usd": 22000},
    "mitsubishi pajero": {"brand": "Mitsubishi", "model": "Pajero", "engine_cc": 3000, "power_hp": 178, "price_usd": 35000},
    "паджеро": {"brand": "Mitsubishi", "model": "Pajero", "engine_cc": 3000, "power_hp": 178, "price_usd": 35000},
}

user_histories: Dict[int, List[Dict[str, str]]] = {}
user_profiles: Dict[int, Dict[str, Any]] = {}
GET_NAME, GET_PHONE, CHAT = range(3)

SYSTEM_PROMPT = """Ты — AI-ассистент компании CARFIRE по пригону автомобилей из-за рубежа.
Тебя зовут Игорь. Ты настоящий ИИ-консультант, не просто бот.

Тон: уверенный, спокойный, дружелюбный. Без воды. Живой язык.

Правила:
1. ВСЕГДА слушай запрос — если клиент назвал конкретную марку/модель, работай именно с ней
2. Не придумывай данные — используй только контекст
3. Комиссию не упоминай пока не спросят
4. К менеджеру только если клиент готов купить или просит оформить
5. Не здоровайся повторно — продолжай разговор
6. 3–5 предложений в ответе
7. Только русский язык
8. Если спросят кто ты — честно скажи что ИИ-ассистент CARFIRE

Передача менеджеру: "Передаю тебя менеджеру Евгению: @superluxxx"
"""

client = Groq(api_key=GROQ_API_KEY)
_usd_cache: Dict[str, Any] = {"rate": None, "ts": 0}


async def get_usd_rate() -> float:
    import time
    now = time.time()
    if _usd_cache["rate"] and now - _usd_cache["ts"] < 3600:
        return _usd_cache["rate"]
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://www.cbr-xml-daily.ru/daily_json.js",
                             timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json(content_type=None)
                rate = data["Valute"]["USD"]["Value"]
                _usd_cache.update({"rate": rate, "ts": now})
                return rate
    except Exception as e:
        logging.error(f"Курс ЦБ: {e}")
        return 90.0


def calc_duty(price_eur: float, cc: int, age: int) -> float:
    if age < 3:
        if price_eur <= 8500:    return max(price_eur * 0.54, cc * 2.5)
        elif price_eur <= 16700: return max(price_eur * 0.48, cc * 3.5)
        elif price_eur <= 42300: return max(price_eur * 0.48, cc * 5.5)
        elif price_eur <= 84500: return max(price_eur * 0.48, cc * 7.5)
        elif price_eur <= 169000:return max(price_eur * 0.48, cc * 15.0)
        else:                    return max(price_eur * 0.48, cc * 20.0)
    elif age <= 5:
        if cc <= 1000:   return cc * 1.5
        elif cc <= 1500: return cc * 1.7
        elif cc <= 1800: return cc * 2.5
        elif cc <= 2300: return cc * 2.7
        elif cc <= 3000: return cc * 3.0
        else:            return cc * 3.6
    else:
        if cc <= 1000:   return cc * 3.0
        elif cc <= 1500: return cc * 3.2
        elif cc <= 1800: return cc * 3.5
        elif cc <= 2300: return cc * 4.8
        elif cc <= 3000: return cc * 5.0
        else:            return cc * 5.7


def calc_excise(hp: int) -> float:
    if hp <= 90:   return 0
    elif hp <= 150: return hp * 55
    elif hp <= 200: return hp * 531
    elif hp <= 300: return hp * 869
    else:           return hp * 1063


async def do_calc(price_usd: float, cc: int, hp: int, year: int, usd_rate: float) -> Dict:
    rate = usd_rate + 2
    eur_rate = rate * 0.93
    age = 2025 - year
    price_rub = price_usd * rate
    china = COMPANY_DATA["china_processing_usd"] * rate
    transfer = (price_rub + china) * COMPANY_DATA["transfer_commission_pct"]
    logistics = COMPANY_DATA["logistics_usd"] * rate
    duty = calc_duty(price_usd * 0.93, cc, age) * eur_rate
    util = 20000 * (0.17 if age < 3 else 0.26)
    excise = calc_excise(hp)
    sbkts = COMPANY_DATA["sbkts_epts_rus_rub"]
    comm = COMPANY_DATA["commission_rub"]
    hidden = COMPANY_DATA["hidden_margin_rub"]
    total = price_rub + china + transfer + logistics + duty + util + excise + sbkts + comm + hidden
    return {
        "price_rub": price_rub, "china": china, "transfer": transfer,
        "logistics": logistics, "duty": duty, "util": util, "excise": excise,
        "sbkts": sbkts, "comm": comm,
        "total_min": total - 50000, "total_max": total + 50000,
        "rate": rate, "age": age,
    }


def format_calc(label: str, c: Dict) -> str:
    def r(x): return f"{int(round(x)):,}".replace(",", " ")
    age_str = "новый" if c["age"] < 3 else f"б/у {c['age']} лет"
    return (
        f"💰 Расчёт под ключ — {label} ({age_str})\n\n"
        f"🚗 Цена авто: {r(c['price_rub'])} ₽\n"
        f"📦 Оформление в стране: {r(c['china'])} ₽\n"
        f"💳 Комиссия за перевод (2%): {r(c['transfer'])} ₽\n"
        f"🚢 Доставка до России: {r(c['logistics'])} ₽\n"
        f"🛃 Таможенная пошлина: {r(c['duty'])} ₽\n"
        f"♻️ Утилизационный сбор: {r(c['util'])} ₽\n"
        f"⚡ Акциз: {r(c['excise'])} ₽\n"
        f"📋 СБКТС + ЭПТС + русификация: {r(c['sbkts'])} ₽\n"
        f"🤝 Комиссия CARFIRE: {r(c['comm'])} ₽\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Итого под ключ: от {r(c['total_min'])} до {r(c['total_max'])} ₽\n\n"
        f"Курс USD: {c['rate']:.2f} ₽\n"
        f"Расчёт ориентировочный. Точную сумму подтвердит менеджер: @superluxxx"
    )


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def asked_commission(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in ["комиссия", "сколько берете", "сколько берёте",
                                  "стоимость услуг", "ваши услуги", "что входит"])

def needs_manager(text: str) -> bool:
    t = normalize(text)
    return any(p in t for p in COMPANY_DATA["lead_handoff_triggers"])

def wants_calc(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in [
        "посчитай", "рассчитай", "посчитать", "рассчитать",
        "сколько стоит под ключ", "итого", "расчёт", "расчет",
        "под ключ", "цена под ключ", "стоимость под ключ",
        "сколько выйдет", "во сколько обойдётся", "во сколько обойдется",
        "сколько стоит привезти", "сколько будет стоить",
    ])

def extract_year(text: str) -> Optional[int]:
    m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", text)
    return int(m.group(1)) if m else None

def extract_budget(text: str) -> Optional[int]:
    t = normalize(text).replace("₽", "").replace("рублей", "").replace("руб", "")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*млн", t)
    if m: return int(float(m.group(1).replace(",", ".")) * 1_000_000)
    m = re.search(r"\b(\d{6,8})\b", t)
    if m: return int(m.group(1))
    return None

def detect_countries(text: str) -> List[str]:
    t = normalize(text)
    return [c for c in COMPANY_DATA["main_directions"] + COMPANY_DATA["extra_directions"]
            if c.lower() in t]

def detect_under_160(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in ["до 160", "проходной", "проходная", "проходные",
                                  "до налоговой", "160 сил", "160 лс"])

def find_car(text: str) -> Optional[Dict]:
    """Ищем авто: сначала в базе, потом в словаре KNOWN_CARS"""
    t = normalize(text)

    # 1. Ищем в базе
    best_db, best_db_score = None, 0
    for car in CARS_DATABASE:
        score = 0
        if car["brand"].lower() in t: score += 10
        if car["model"].lower() in t: score += 8
        yr = extract_year(text)
        if yr and car["year"] == yr: score += 5
        if score > best_db_score:
            best_db_score = score
            best_db = car
    if best_db_score >= 8:
        return {"source": "db", "data": best_db}

    # 2. Ищем в словаре — берём самый длинный совпадающий ключ
    best_key, best_len = None, 0
    for key in KNOWN_CARS:
        k = key.strip()
        if k in t and len(k) > best_len:
            best_key = key
            best_len = len(k)
    if best_key:
        return {"source": "dict", "data": KNOWN_CARS[best_key]}

    return None

def search_for_context(query: str, budget: Optional[int], countries: List[str],
                        under_160: bool, usd_rate: float) -> List[Dict]:
    q = normalize(query)
    results = []
    for car in CARS_DATABASE:
        if not car.get("is_available"): continue
        if countries and car["country"] not in countries: continue
        if under_160 and not car.get("is_under_160_hp"): continue
        if budget and car["price_usd"] * (usd_rate + 2) * 1.5 > budget: continue
        score = 0
        blob = f"{car['brand']} {car['model']} {car['country']} {car['comment']}".lower()
        for word in q.split():
            if len(word) >= 3 and word in blob: score += 2
        if car.get("priority"): score += 2
        if under_160 and car.get("is_under_160_hp"): score += 3
        results.append((score, car))
    results.sort(key=lambda x: (x[0], -x[1].get("year", 0)), reverse=True)
    return [c for _, c in results[:3]]

def build_context(user_id: int, text: str, usd_rate: float) -> str:
    profile = user_profiles.get(user_id, {})
    name = profile.get("name", "")
    budget = extract_budget(text)
    countries = detect_countries(text)
    under_160 = detect_under_160(text)
    show_comm = asked_commission(text)
    cars = search_for_context(text, budget, countries, under_160, usd_rate)

    lines = [
        f"Компания: {COMPANY_DATA['name']}",
        f"Основные направления: {', '.join(COMPANY_DATA['main_directions'])}",
        f"По запросу: {', '.join(COMPANY_DATA['extra_directions'])}",
        f"Курс USD: {usd_rate + 2:.2f} ₽",
    ]
    if name: lines.append(f"Клиент: {name}")
    if budget: lines.append(f"Бюджет: до {budget:,} ₽".replace(",", " "))
    if countries: lines.append(f"Страны: {', '.join(countries)}")
    if under_160: lines.append("Фильтр: до 160 л.с.")

    lines.append("\nСроки:")
    for c, t in COMPANY_DATA["delivery_terms"].items():
        lines.append(f"  {c}: {t}")

    if show_comm:
        lines.append(f"\nКомиссия: {COMPANY_DATA['commission_text']}")
    else:
        lines.append("\nКомиссию не упоминать.")

    lines.append("\nАвто из базы:")
    if cars:
        for car in cars:
            lines.append(
                f"  • {car['brand']} {car['model']} {car['year']} | "
                f"{car['power_hp']}лс | ~{int(car['price_usd']*(usd_rate+2)):,}₽ | "
                f"{'✅до160' if car['is_under_160_hp'] else '⚠️выше160'} | "
                f"{car['comment']}"
            )
    else:
        lines.append("  Авто в базе не найдено.")

    lines.append(f"\nМенеджер: {COMPANY_DATA['manager_telegram']}")
    return "\n".join(lines)


async def notify_managers(bot: Bot, name: str, phone: str, tg_id: int, username: str):
    text = (f"🔥 Новый лид!\n\n👤 {name}\n📱 {phone}\n"
            f"💬 @{username or 'нет'}\n🆔 {tg_id}")
    for mid in MANAGER_IDS:
        try:
            await bot.send_message(chat_id=mid, text=text)
        except Exception as e:
            logging.error(f"Уведомление {mid}: {e}")


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет!\n\nЯ Игорь — AI-ассистент компании CARFIRE 🔥\n\n"
        "Помогу подобрать авто из-за рубежа, рассчитать стоимость под ключ "
        "и ответить на все вопросы по пригону.\n\nКак тебя зовут?",
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
        f"Оставь номер телефона — менеджер сможет связаться когда дойдёт до конкретики.",
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
            f"{name}, без номера не получится передать тебя менеджеру 🙂\n\nНажми кнопку ниже 👇",
            reply_markup=phone_keyboard()
        )
        return GET_PHONE
    user_profiles[user_id]["phone"] = phone
    logging.info(f"Лид | {name} | {phone} | @{username} | {user_id}")
    await notify_managers(context.bot, name, phone, user_id, username)
    await update.message.reply_text(
        f"Отлично, {name}!\n\nПиши что ищешь — марку, модель, бюджет, страну.\n"
        f"Например: «Audi A3 из Европы» или «кроссовер до 3 млн до 160 сил».\n\n"
        f"Могу сразу посчитать стоимость под ключ 👇",
        reply_markup=main_keyboard()
    )
    return CHAT

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()

    if user_text == "📞 Связаться с менеджером":
        await update.message.reply_text(
            "Передаю тебя менеджеру Евгению 💪\n\nTelegram: @superluxxx",
            reply_markup=main_keyboard()
        )
        return CHAT

    quick_map = {
        "🚗 Подобрать авто": "Помоги подобрать автомобиль для пригона. Покажи варианты и ориентир по цене.",
        "💰 Рассчитать стоимость": "Рассчитай стоимость под ключ для подходящего авто.",
        "⚡ До 160 л.с.": "Покажи варианты авто до 160 л.с. и рассчитай стоимость под ключ.",
        "🌍 Из каких стран везёте?": "Из каких стран вы привозите автомобили?",
        "⏱ Сроки доставки": "Какие сроки доставки по разным направлениям?",
    }
    llm_input = quick_map.get(user_text, user_text)

    if needs_manager(llm_input):
        await update.message.reply_text(
            "Передаю тебя менеджеру Евгению: @superluxxx",
            reply_markup=main_keyboard()
        )
        return CHAT

    usd_rate = await get_usd_rate()

    if wants_calc(llm_input):
        year_override = extract_year(llm_input)
        found = find_car(llm_input)
        if found:
            d = found["data"]
            price_usd = d["price_usd"]
            cc = d["engine_cc"]
            hp = d["power_hp"]
            year = year_override or (d.get("year") or 2023)
            label = f"{d['brand']} {d['model']} {year}"
            calc = await do_calc(price_usd, cc, hp, year, usd_rate)
            await update.message.reply_text(format_calc(label, calc), reply_markup=main_keyboard())
        else:
            await update.message.reply_text(
                "Напиши марку и модель авто — и я рассчитаю стоимость под ключ.\n"
                "Например: «посчитай BMW X5 2022» или «Audi A3 2024 под ключ».",
                reply_markup=main_keyboard()
            )
        return CHAT

    user_histories.setdefault(user_id, [])
    user_histories[user_id].append({"role": "user", "content": llm_input})
    user_histories[user_id] = user_histories[user_id][-14:]
    ctx = build_context(user_id, llm_input, usd_rate)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": "Контекст:\n" + ctx},
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
        logging.exception(f"Ошибка: {e}")
        await update.message.reply_text("Что-то пошло не так. Попробуй ещё раз.", reply_markup=main_keyboard())

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
