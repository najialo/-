import os
import requests
from flask import Flask, request, jsonify
import sqlite3
import threading
import time

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_PATH = "trading_bot.db"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, symbol TEXT, price_level REAL, alert_type TEXT, is_active BOOLEAN DEFAULT TRUE)''')
    conn.commit()
    conn.close()

def get_price(symbol):
    symbol = symbol.upper()
    try:
        if symbol in ["XAUUSD", "GOLD"]:
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=5)
            return float(r.json()["price"])
        elif symbol in ["XAGUSD", "SILVER"]:
            r = requests.get("https://api.gold-api.com/price/XAG", timeout=5)
            return float(r.json()["price"])
    except:
        pass
    return None

def send_message(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message")
    if not message:
        return "ok"
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    if text in ["/start", "/help"]:
        send_message(chat_id, "🤖 بوت الأسعار\n\n/gold - سعر الذهب\n/silver - سعر الفضة")
    elif text == "/gold":
        price = get_price("XAUUSD")
        send_message(chat_id, f"💰 الذهب: {price:.2f}" if price else "❌ خطأ")
    elif text == "/silver":
        price = get_price("XAGUSD")
        send_message(chat_id, f"💰 الفضة: {price:.2f}" if price else "❌ خطأ")
    
    return "ok"

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "running"})

if __name__ == "__main__":
    init_database()
    app.run()
