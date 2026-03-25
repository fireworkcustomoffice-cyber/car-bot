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

KNOWN_CARS: Dict[str, Dict] = {
    "audi a1": {"brand": "Audi", "model": "A1", "engine_cc": 1000, "power_hp": 116, "price_usd": 14000},
    "audi a3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 19000},
    "ауди а3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 19000},
    "ауди а 3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 19000},
    "a3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 19000},
    "а3": {"brand": "Audi", "model": "A3", "engine_cc": 1400, "power_hp": 150, "price_usd": 19000},
    "audi a4": {"brand": "Audi", "model": "A4", "engine_cc": 2000, "power_hp": 190, "price_usd": 28000},
    "ауди а4": {"brand": "Audi", "model": "A4", "engine_cc": 2000, "power_hp": 190, "price_usd": 28000},
    "а4": {"brand": "Audi", "model": "A4", "engine_cc": 2000, "power_hp": 190, "price_usd": 28000},
    "audi a5": {"brand": "Audi", "model": "A5", "engine_cc": 2000, "power_hp": 190, "price_usd": 32000},
    "ауди а5": {"brand": "Audi", "model": "A5", "engine_cc": 2000, "power_hp": 190, "price_usd": 32000},
    "а5": {"brand": "Audi", "model": "A5", "engine_cc": 2000, "power_hp": 190, "price_usd": 32000},
    "audi a6": {"brand": "Audi", "model": "A6", "engine_cc": 2000, "power_hp": 204, "price_usd": 38000},
    "ауди а6": {"brand": "Audi", "model": "A6", "engine_cc": 2000, "power_hp": 204, "price_usd": 38000},
    "а6": {"brand": "Audi", "model": "A6", "engine_cc": 2000, "power_hp": 204, "price_usd": 38000},
    "audi a7": {"brand": "Audi", "model": "A7", "engine_cc": 3000, "power_hp": 340, "price_usd": 55000},
    "audi a8": {"brand": "Audi", "model": "A8", "engine_cc": 3000, "power_hp": 340, "price_usd": 72000},
    "audi q3": {"brand": "Audi", "model": "Q3", "engine_cc": 1500, "power_hp": 150, "price_usd": 25000},
    "ауди q3": {"brand": "Audi", "model": "Q3", "engine_cc": 1500, "power_hp": 150, "price_usd": 25000},
    "ку3": {"brand": "Audi", "model": "Q3", "engine_cc": 1500, "power_hp": 150, "price_usd": 25000},
    "q3": {"brand": "Audi", "model": "Q3", "engine_cc": 1500, "power_hp": 150, "price_usd": 25000},
    "audi q5": {"brand": "Audi", "model": "Q5", "engine_cc": 2000, "power_hp": 204, "price_usd": 42000},
    "ауди q5": {"brand": "Audi", "model": "Q5", "engine_cc": 2000, "power_hp": 204, "price_usd": 42000},
    "ку5": {"brand": "Audi", "model": "Q5", "engine_cc": 2000, "power_hp": 204, "price_usd": 42000},
    "q5": {"brand": "Audi", "model": "Q5", "engine_cc": 2000, "power_hp": 204, "price_usd": 42000},
    "audi q7": {"brand": "Audi", "model": "Q7", "engine_cc": 3000, "power_hp": 249, "price_usd": 58000},
    "ауди q7": {"brand": "Audi", "model": "Q7", "engine_cc": 3000, "power_hp": 249, "price_usd": 58000},
    "ку7": {"brand": "Audi", "model": "Q7", "engine_cc": 3000, "power_hp": 249, "price_usd": 58000},
    "q7": {"brand": "Audi", "model": "Q7", "engine_cc": 3000, "power_hp": 249, "price_usd": 58000},
    "audi q8": {"brand": "Audi", "model": "Q8", "engine_cc": 3000, "power_hp": 340, "price_usd": 75000},
    "bmw 1": {"brand": "BMW", "model": "1 Series", "engine_cc": 1500, "power_hp": 140, "price_usd": 18000},
    "бмв 1": {"brand": "BMW", "model": "1 Series", "engine_cc": 1500, "power_hp": 140, "price_usd": 18000},
    "bmw 3": {"brand": "BMW", "model": "3 Series", "engine_cc": 2000, "power_hp": 184, "price_usd": 30000},
    "бмв 3": {"brand": "BMW", "model": "3 Series", "engine_cc": 2000, "power_hp": 184, "price_usd": 30000},
    "bmw 5": {"brand": "BMW", "model": "5 Series", "engine_cc": 2000, "power_hp": 190, "price_usd": 42000},
    "бмв 5": {"brand": "BMW", "model": "5 Series", "engine_cc": 2000, "power_hp": 190, "price_usd": 42000},
    "bmw 7": {"brand": "BMW", "model": "7 Series", "engine_cc": 3000, "power_hp": 340, "price_usd": 70000},
    "бмв 7": {"brand": "BMW", "model": "7 Series", "engine_cc": 3000, "power_hp": 340, "price_usd": 70000},
    "bmw x1": {"brand": "BMW", "model": "X1", "engine_cc": 1500, "power_hp": 136, "price_usd": 22000},
    "бмв х1": {"brand": "BMW", "model": "X1", "engine_cc": 1500, "power_hp": 136, "price_usd": 22000},
    "х1": {"brand": "BMW", "model": "X1", "engine_cc": 1500, "power_hp": 136, "price_usd": 22000},
    "bmw x3": {"brand": "BMW", "model": "X3", "engine_cc": 2000, "power_hp": 184, "price_usd": 38000},
    "бмв х3": {"brand": "BMW", "model": "X3", "engine_cc": 2000, "power_hp": 184, "price_usd": 38000},
    "х3": {"brand": "BMW", "model": "X3", "engine_cc": 2000, "power_hp": 184, "price_usd": 38000},
    "bmw x5": {"brand": "BMW", "model": "X5", "engine_cc": 3000, "power_hp": 249, "price_usd": 52000},
    "бмв х5": {"brand": "BMW", "model": "X5", "engine_cc": 3000, "power_hp": 249, "price_usd": 52000},
    "х5": {"brand": "BMW", "model": "X5", "engine_cc": 3000, "power_hp": 249, "price_usd": 52000},
    "bmw x6": {"brand": "BMW", "model": "X6", "engine_cc": 3000, "power_hp": 249, "price_usd": 55000},
    "бмв х6": {"brand": "BMW", "model": "X6", "engine_cc": 3000, "power_hp": 249, "price_usd": 55000},
    "х6": {"brand": "BMW", "model": "X6", "engine_cc": 3000, "power_hp": 249, "price_usd": 55000},
    "bmw x7": {"brand": "BMW", "model": "X7", "engine_cc": 3000, "power_hp": 340, "price_usd": 75000},
    "бмв х7": {"brand": "BMW", "model": "X7", "engine_cc": 3000, "power_hp": 340, "price_usd": 75000},
    "х7": {"brand": "BMW", "model": "X7", "engine_cc": 3000, "power_hp": 340, "price_usd": 75000},
    "mercedes c": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 32000},
    "мерседес с": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 32000},
    "мерс с": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 32000},
    "мерс c": {"brand": "Mercedes", "model": "C-Class", "engine_cc": 1500, "power_hp": 170, "price_usd": 32000},
    "mercedes e": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 45000},
    "мерседес е": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 45000},
    "мерс е": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 45000},
    "мерс e": {"brand": "Mercedes", "model": "E-Class", "engine_cc": 2000, "power_hp": 197, "price_usd": 45000},
    "mercedes s": {"brand": "Mercedes", "model": "S-Class", "engine_cc": 3000, "power_hp": 340, "price_usd": 85000},
    "mercedes glc": {"brand": "Mercedes", "model": "GLC", "engine_cc": 2000, "power_hp": 204, "price_usd": 48000},
    "mercedes gle": {"brand": "Mercedes", "model": "GLE", "engine_cc": 3000, "power_hp": 330, "price_usd": 68000},
    "mercedes g": {"brand": "Mercedes", "model": "G-Class", "engine_cc": 4000, "power_hp": 422, "price_usd": 110000},
    "гелендваген": {"brand": "Mercedes", "model": "G-Class", "engine_cc": 4000, "power_hp": 422, "price_usd": 110000},
    "toyota camry": {"brand": "Toyota", "model": "Camry", "engine_cc": 2000, "power_hp": 173, "price_usd": 20000},
    "camry": {"brand": "Toyota", "model": "Camry", "engine_cc": 2000, "power_hp": 173, "price_usd": 20000},
    "камри": {"brand": "Toyota", "model": "Camry", "engine_cc": 2000, "power_hp": 173, "price_usd": 20000},
    "toyota rav4": {"brand": "Toyota", "model": "RAV4", "engine_cc": 2000, "power_hp": 175, "price_usd": 24000},
    "rav4": {"brand": "Toyota", "model": "RAV4", "engine_cc": 2000, "power_hp": 175, "price_usd": 24000},
    "рав4": {"brand": "Toyota", "model": "RAV4", "engine_cc": 2000, "power_hp": 175, "price_usd": 24000},
    "toyota land cruiser": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 60000},
    "land cruiser": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 60000},
    "ленд крузер": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 60000},
    "крузак": {"brand": "Toyota", "model": "Land Cruiser", "engine_cc": 3500, "power_hp": 275, "price_usd": 60000},
    "toyota highlander": {"brand": "Toyota", "model": "Highlander", "engine_cc": 2500, "power_hp": 238, "price_usd": 35000},
    "хайлендер": {"brand": "Toyota", "model": "Highlander", "engine_cc": 2500, "power_hp": 238, "price_usd": 35000},
    "toyota corolla": {"brand": "Toyota", "model": "Corolla", "engine_cc": 1600, "power_hp": 122, "price_usd": 15000},
    "королла": {"brand": "Toyota", "model": "Corolla", "engine_cc": 1600, "power_hp": 122, "price_usd": 15000},
    "lexus rx": {"brand": "Lexus", "model": "RX", "engine_cc": 2000, "power_hp": 238, "price_usd": 38000},
    "лексус rx": {"brand": "Lexus", "model": "RX", "engine_cc": 2000, "power_hp": 238, "price_usd": 38000},
    "лексус рх": {"brand": "Lexus", "model": "RX", "engine_cc": 2000, "power_hp": 238, "price_usd": 38000},
    "lexus lx": {"brand": "Lexus", "model": "LX", "engine_cc": 3500, "power_hp": 415, "price_usd": 75000},
    "лексус lx": {"brand": "Lexus", "model": "LX", "engine_cc": 3500, "power_hp": 415, "price_usd": 75000},
    "lexus es": {"brand": "Lexus", "model": "ES", "engine_cc": 2500, "power_hp": 218, "price_usd": 30000},
    "лексус es": {"brand": "Lexus", "model": "ES", "engine_cc": 2500, "power_hp": 218, "price_usd": 30000},
    "volkswagen passat": {"brand": "Volkswagen", "model": "Passat", "engine_cc": 2000, "power_hp": 150, "price_usd": 20000},
    "пассат": {"brand": "Volkswagen", "model": "Passat", "engine_cc": 2000, "power_hp": 150, "price_usd": 20000},
    "volkswagen tiguan": {"brand": "Volkswagen", "model": "Tiguan", "engine_cc": 1400, "power_hp": 150, "price_usd": 22000},
    "тигуан": {"brand": "Volkswagen", "model": "Tiguan", "engine_cc": 1400, "power_hp": 150, "price_usd": 22000},
    "volkswagen golf": {"brand": "Volkswagen", "model": "Golf", "engine_cc": 1400, "power_hp": 150, "price_usd": 18000},
    "гольф": {"brand": "Volkswagen", "model": "Golf", "engine_cc": 1400, "power_hp": 150, "price_usd": 18000},
    "volkswagen touareg": {"brand": "Volkswagen", "model": "Touareg", "engine_cc": 3000, "power_hp": 249, "price_usd": 45000},
    "туарег": {"brand": "Volkswagen", "model": "Touareg", "engine_cc": 3000, "power_hp": 249, "price_usd": 45000},
    "hyundai tucson": {"brand": "Hyundai", "model": "Tucson", "engine_cc": 1600, "power_hp": 150, "price_usd": 18000},
    "туксон": {"brand": "Hyundai", "model": "Tucson", "engine_cc": 1600, "power_hp": 150, "price_usd": 18000},
    "hyundai palisade": {"brand": "Hyundai", "model": "Palisade", "engine_cc": 2500, "power_hp": 196, "price_usd": 32000},
    "палисейд": {"brand": "Hyundai", "model": "Palisade", "engine_cc": 2500, "power_hp": 196, "price_usd": 32000},
    "hyundai sonata": {"brand": "Hyundai", "model": "Sonata", "engine_cc": 2000, "power_hp": 150, "price_usd": 18000},
    "соната": {"brand": "Hyundai", "model": "Sonata", "engine_cc": 2000, "power_hp": 150, "price_usd": 18000},
    "kia sportage": {"brand": "Kia", "model": "Sportage", "engine_cc": 1600, "power_hp": 150, "price_usd": 18000},
    "спортейдж": {"brand": "Kia", "model": "Sportage", "engine_cc": 1600, "power_hp": 150, "price_usd": 18000},
    "kia sorento": {"brand": "Kia", "model": "Sorento", "engine_cc": 2500, "power_hp": 196, "price_usd": 28000},
    "соренто": {"brand": "Kia", "model": "Sorento", "engine_cc": 2500, "power_hp": 196, "price_usd": 28000},
    "kia stinger": {"brand": "Kia", "model": "Stinger", "engine_cc": 2000, "power_hp": 255, "price_usd": 25000},
    "стингер": {"brand": "Kia", "model": "Stinger", "engine_cc": 2000, "power_hp": 255, "price_usd": 25000},
    "mazda cx-5": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 16000},
    "мазда cx-5": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 16000},
    "mazda cx5": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 16000},
    "мазда": {"brand": "Mazda", "model": "CX-5", "engine_cc": 1500, "power_hp": 155, "price_usd": 16000},
    "mazda 6": {"brand": "Mazda", "model": "6", "engine_cc": 2000, "power_hp": 165, "price_usd": 17000},
    "мазда 6": {"brand": "Mazda", "model": "6", "engine_cc": 2000, "power_hp": 165, "price_usd": 17000},
    "haval h6": {"brand": "Haval", "model": "H6", "engine_cc": 1500, "power_hp": 150, "price_usd": 13000},
    "haval h9": {"brand": "Haval", "model": "H9", "engine_cc": 2000, "power_hp": 218, "price_usd": 24000},
    "geely atlas": {"brand": "Geely", "model": "Atlas", "engine_cc": 1500, "power_hp": 150, "price_usd": 12000},
    "chery tiggo": {"brand": "Chery", "model": "Tiggo 7", "engine_cc": 1500, "power_hp": 150, "price_usd": 12000},
    "byd han": {"brand": "BYD", "model": "Han", "engine_cc": 1500, "power_hp": 218, "price_usd": 22000},
    "byd seal": {"brand": "BYD", "model": "Seal", "engine_cc": 1500, "power_hp": 313, "price_usd": 20000},
    "li auto l6": {"brand": "Li Auto", "model": "L6", "engine_cc": 1500, "power_hp": 330, "price_usd": 28000},
    "omoda": {"brand": "Omoda", "model": "C5", "engine_cc": 1600, "power_hp": 147, "price_usd": 13000},
    "jaecoo": {"brand": "Jaecoo", "model": "J7", "engine_cc": 1500, "power_hp": 147, "price_usd": 14000},
    "porsche cayenne": {"brand": "Porsche", "model": "Cayenne", "engine_cc": 3000, "power_hp": 340, "price_usd": 72000},
    "кайен": {"brand": "Porsche", "model": "Cayenne", "engine_cc": 3000, "power_hp": 340, "price_usd": 72000},
    "порше кайен": {"brand": "Porsche", "model": "Cayenne", "engine_cc": 3000, "power_hp": 340, "price_usd": 72000},
    "porsche macan": {"brand": "Porsche", "model": "Macan", "engine_cc": 2000, "power_hp": 265, "price_usd": 50000},
    "макан": {"brand": "Porsche", "model": "Macan", "engine_cc": 2000, "power_hp": 265, "price_usd": 50000},
    "range rover": {"brand": "Land Rover", "model": "Range Rover", "engine_cc": 3000, "power_hp": 350, "price_usd": 78000},
    "рейндж ровер": {"brand": "Land Rover", "model": "Range Rover", "engine_cc": 3000, "power_hp": 350, "price_usd": 78000},
    "defender": {"brand": "Land Rover", "model": "Defender", "engine_cc": 2000, "power_hp": 300, "price_usd": 48000},
    "дефендер": {"brand": "Land Rover", "model": "Defender", "engine_cc": 2000, "power_hp": 300, "price_usd": 48000},
    "volvo xc90": {"brand": "Volvo", "model": "XC90", "engine_cc": 2000, "power_hp": 249, "price_usd": 50000},
    "volvo xc60": {"brand": "Volvo", "model": "XC60", "engine_cc": 2000, "power_hp": 190, "price_usd": 38000},
    "skoda octavia": {"brand": "Skoda", "model": "Octavia", "engine_cc": 1400, "power_hp": 150, "price_usd": 18000},
    "октавия": {"brand": "Skoda", "model": "Octavia", "engine_cc": 1400, "power_hp": 150, "price_usd": 18000},
    "skoda kodiaq": {"brand": "Skoda", "model": "Kodiaq", "engine_cc": 2000, "power_hp": 190, "price_usd": 26000},
    "кодиак": {"brand": "Skoda", "model": "Kodiaq", "engine_cc": 2000, "power_hp": 190, "price_usd": 26000},
    "nissan patrol": {"brand": "Nissan", "model": "Patrol", "engine_cc": 4000, "power_hp": 275, "price_usd": 48000},
    "патрол": {"brand": "Nissan", "model": "Patrol", "engine_cc": 4000, "power_hp": 275, "price_usd": 48000},
    "nissan qashqai": {"brand": "Nissan", "model": "Qashqai", "engine_cc": 1300, "power_hp": 140, "price_usd": 18000},
    "кашкай": {"brand": "Nissan", "model": "Qashqai", "engine_cc": 1300, "power_hp": 140, "price_usd": 18000},
    "honda cr-v": {"brand": "Honda", "model": "CR-V", "engine_cc": 1500, "power_hp": 193, "price_usd": 22000},
    "honda accord": {"brand": "Honda", "model": "Accord", "engine_cc": 1500, "power_hp": 192, "price_usd": 20000},
    "аккорд": {"brand": "Honda", "model": "Accord", "engine_cc": 1500, "power_hp": 192, "price_usd": 20000},
    "subaru outback": {"brand": "Subaru", "model": "Outback", "engine_cc": 2500, "power_hp": 175, "price_usd": 24000},
    "аутбэк": {"brand": "Subaru", "model": "Outback", "engine_cc": 2500, "power_hp": 175, "price_usd": 24000},
    "subaru forester": {"brand": "Subaru", "model": "Forester", "engine_cc": 2000, "power_hp": 150, "price_usd": 18000},
    "форестер": {"brand": "Subaru", "model": "Forester", "engine_cc": 2000, "power_hp": 150, "price_usd": 18000},
    "ford mustang": {"brand": "Ford", "model": "Mustang", "engine_cc": 5000, "power_hp": 450, "price_usd": 32000},
    "мустанг": {"brand": "Ford", "model": "Mustang", "engine_cc": 5000, "power_hp": 450, "price_usd": 32000},
    "ford explorer": {"brand": "Ford", "model": "Explorer", "engine_cc": 3000, "power_hp": 300, "price_usd": 35000},
    "dodge charger": {"brand": "Dodge", "model": "Charger", "engine_cc": 5700, "power_hp": 370, "price_usd": 28000},
    "dodge challenger": {"brand": "Dodge", "model": "Challenger", "engine_cc": 5700, "power_hp": 375, "price_usd": 28000},
    "jeep grand cherokee": {"brand": "Jeep", "model": "Grand Cherokee", "engine_cc": 3600, "power_hp": 290, "price_usd": 35000},
    "гранд чероки": {"brand": "Jeep", "model": "Grand Cherokee", "engine_cc": 3600, "power_hp": 290, "price_usd": 35000},
    "cadillac escalade": {"brand": "Cadillac", "model": "Escalade", "engine_cc": 6200, "power_hp": 420, "price_usd": 65000},
    "эскалейд": {"brand": "Cadillac", "model": "Escalade", "engine_cc": 6200, "power_hp": 420, "price_usd": 65000},
    "mitsubishi outlander": {"brand": "Mitsubishi", "model": "Outlander", "engine_cc": 2000, "power_hp": 145, "price_usd": 18000},
    "аутлендер": {"brand": "Mitsubishi", "model": "Outlander", "engine_cc": 2000, "power_hp": 145, "price_usd": 18000},
    "mitsubishi pajero": {"brand": "Mitsubishi", "model": "Pajero", "engine_cc": 3000, "power_hp": 178, "price_usd": 28000},
    "паджеро": {"brand": "Mitsubishi", "model": "Pajero", "engine_cc": 3000, "power_hp": 178, "price_usd": 28000},
}

user_histories: Dict[int, List[Dict[str, str]]] = {}
user_profiles: Dict[int, Dict[str, Any]] = {}
# Запоминаем последнее авто о котором говорили
last_car_discussed: Dict[int, Dict] = {}

GET_NAME, GET_PHONE, CHAT = range(3)

SYSTEM_PROMPT = """Ты — Игорь, AI-ассистент компании CARFIRE. Занимаемся пригоном автомобилей из-за рубежа.

О компании CARFIRE:
— Приоритетные направления: Китай и США
— По запросу: Европа, Канада, Япония, Корея
— Из Китая: привозим новые и б/у авто, обычно более высокая комплектация чем в РФ
— Из США: работаем с аукционами битых авто (Copart, IAAI), восстанавливаем до идеального состояния — клиент получает отличную машину по выгодной цене
— Из Европы и других стран: по запросу, индивидуально
— Комиссия CARFIRE: 90 000 ₽ (не говори об этом пока не спросят)
— Сроки из Китая: 3–6 недель
— Сроки из США: 6–10 недель
— Европа и другие: индивидуально
— Менеджер Евгений: @superluxxx

Стиль:
— Живой, дружелюбный, уверенный. Как опытный консультант
— Без воды и канцелярщины
— Иногда обращайся по имени

ВАЖНЫЕ ПРАВИЛА:
1. Никогда не говори клиенту "напиши посчитай" или "дай команду" — ты сам всё считаешь
2. Никогда не говори что мы не можем что-то привезти
3. Если клиент называет авто и спрашивает цену — в контексте уже есть готовый расчёт, назови его
4. Не навязывай менеджера без причины
5. Не здоровайся повторно
6. Максимум 4–5 предложений
7. Только русский язык
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
        if price_eur <= 8500:     return max(price_eur * 0.54, cc * 2.5)
        elif price_eur <= 16700:  return max(price_eur * 0.48, cc * 3.5)
        elif price_eur <= 42300:  return max(price_eur * 0.48, cc * 5.5)
        elif price_eur <= 84500:  return max(price_eur * 0.48, cc * 7.5)
        elif price_eur <= 169000: return max(price_eur * 0.48, cc * 15.0)
        else:                     return max(price_eur * 0.48, cc * 20.0)
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
    if hp <= 90:    return 0
    elif hp <= 150: return hp * 55
    elif hp <= 200: return hp * 531
    elif hp <= 300: return hp * 869
    else:           return hp * 1063


async def do_calc(price_usd: float, cc: int, hp: int, year: int, usd_rate: float) -> Dict:
    rate = usd_rate + 2
    eur_rate = rate * 0.93
    age = 2025 - year
    price_rub = price_usd * rate
    china = 1700 * rate
    transfer = (price_rub + china) * 0.02
    logistics = 2500 * rate
    duty = calc_duty(price_usd * 0.93, cc, age) * eur_rate
    util = 20000 * (0.17 if age < 3 else 0.26)
    excise = calc_excise(hp)
    total = price_rub + china + transfer + logistics + duty + util + excise + 75000 + 90000 + 200000
    return {
        "price_rub": price_rub, "china": china, "transfer": transfer,
        "logistics": logistics, "duty": duty, "util": util, "excise": excise,
        "total_min": total - 50000, "total_max": total + 50000,
        "rate": rate, "age": age,
    }


def format_calc(label: str, c: Dict) -> str:
    def r(x): return f"{int(round(x)):,}".replace(",", " ")
    age_str = "до 3 лет" if c["age"] < 3 else f"б/у {c['age']} лет"
    return (
        f"Расчёт под ключ — {label} ({age_str})\n"
        f"Курс USD: {c['rate']:.2f} ₽\n\n"
        f"Цена авто:              {r(c['price_rub'])} ₽\n"
        f"Оформление в стране:    {r(c['china'])} ₽\n"
        f"Перевод (2%):           {r(c['transfer'])} ₽\n"
        f"Доставка до России:     {r(c['logistics'])} ₽\n"
        f"Таможенная пошлина:     {r(c['duty'])} ₽\n"
        f"Утилизационный сбор:    {r(c['util'])} ₽\n"
        f"Акциз:                  {r(c['excise'])} ₽\n"
        f"СБКТС + ЭПТС + рус-я:  75 000 ₽\n"
        f"Комиссия CARFIRE:       90 000 ₽\n\n"
        f"Итого под ключ:\n"
        f"от {r(c['total_min'])} до {r(c['total_max'])} ₽\n\n"
        f"Расчёт ориентировочный. Точную сумму уточнит менеджер: @superluxxx"
    )


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def extract_year(text: str) -> Optional[int]:
    m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", text)
    return int(m.group(1)) if m else None

def find_car(text: str) -> Optional[Dict]:
    t = normalize(text)
    best_key, best_len = None, 0
    for key in KNOWN_CARS:
        k = key.strip()
        if k in t and len(k) > best_len:
            best_key = key
            best_len = len(k)
    return KNOWN_CARS[best_key] if best_key else None

def is_price_question(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in [
        "сколько", "цена", "стоимость", "почём", "почем",
        "посчитай", "рассчитай", "под ключ", "расчёт", "расчет",
        "сколько стоит", "сколько будет", "сколько выйдет",
        "во сколько", "итого", "выйдет",
    ])

def needs_manager(text: str) -> bool:
    t = normalize(text)
    return any(p in t for p in [
        "хочу купить", "готов купить", "нужен точный расчет",
        "давай оформлять", "оформить заявку", "готов к покупке",
    ])

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
            f"{name}, без номера не получится передать тебя менеджеру когда придёт время 🙂\n\nНажми кнопку ниже 👇",
            reply_markup=phone_keyboard()
        )
        return GET_PHONE
    user_profiles[user_id]["phone"] = phone
    logging.info(f"Лид | {name} | {phone} | @{username} | {user_id}")
    await notify_managers(context.bot, name, phone, user_id, username)
    await update.message.reply_text(
        f"Отлично, {name}!\n\nСпрашивай что интересует — марку, модель, страну, бюджет.\n"
        f"Назови авто — сразу рассчитаю стоимость под ключ 👇",
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
        "🚗 Подобрать авто": "Хочу подобрать автомобиль для пригона.",
        "💰 Рассчитать стоимость": "Хочу рассчитать стоимость автомобиля под ключ.",
        "⚡ До 160 л.с.": "Интересуют авто до 160 л.с. — проходные по налогу.",
        "🌍 Из каких стран везёте?": "Из каких стран вы привозите автомобили?",
        "⏱ Сроки доставки": "Какие сроки доставки?",
    }
    llm_input = quick_map.get(user_text, user_text)

    if needs_manager(llm_input):
        await update.message.reply_text(
            "Передаю тебя менеджеру Евгению: @superluxxx",
            reply_markup=main_keyboard()
        )
        return CHAT

    usd_rate = await get_usd_rate()
    profile = user_profiles.get(user_id, {})
    name = profile.get("name", "")

    # Ищем авто в сообщении
    car = find_car(llm_input)
    year = extract_year(llm_input)

    # Если нашли авто — запоминаем его
    if car:
        last_car_discussed[user_id] = {"car": car, "year": year}
    # Если авто не назвали но спрашивают цену — берём последнее обсуждаемое
    elif is_price_question(llm_input) and user_id in last_car_discussed:
        car = last_car_discussed[user_id]["car"]
        year = year or last_car_discussed[user_id].get("year")

    # Если есть авто и вопрос о цене — сразу считаем
    if car and is_price_question(llm_input):
        calc_year = year or 2023
        calc = await do_calc(car["price_usd"], car["engine_cc"], car["power_hp"], calc_year, usd_rate)
        label = f"{car['brand']} {car['model']} {calc_year}"
        await update.message.reply_text(format_calc(label, calc), reply_markup=main_keyboard())
        return CHAT

    # Если просто назвали авто без вопроса о цене — LLM отвечает с контекстом цены
    car_context = ""
    if car:
        calc_year = year or 2023
        approx = await do_calc(car["price_usd"], car["engine_cc"], car["power_hp"], calc_year, usd_rate)
        car_context = (
            f"\n\nАвто в запросе: {car['brand']} {car['model']} {calc_year} | "
            f"{car['power_hp']} л.с. | {car['engine_cc']} куб.см\n"
            f"Готовый расчёт под ключ: от {int(approx['total_min']):,} до {int(approx['total_max']):,} ₽\n"
            f"Курс USD: {approx['rate']:.2f} ₽\n"
            f"Используй эти цифры если клиент спрашивает о цене — называй их сам, не проси клиента что-то писать."
        ).replace(",", " ")

    system = SYSTEM_PROMPT
    if name:
        system += f"\n\nИмя клиента: {name}"
    system += car_context

    user_histories.setdefault(user_id, [])
    user_histories[user_id].append({"role": "user", "content": llm_input})
    user_histories[user_id] = user_histories[user_id][-14:]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system}] + user_histories[user_id],
            temperature=0.4,
            max_tokens=500,
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
