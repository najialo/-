import os
import requests
from datetime import datetime
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, symbol TEXT, price_level REAL, alert_type TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_realtime_price(symbol):
    symbol = symbol.upper()
    
    if symbol in ["XAUUSD", "GOLD"]:
        try:
            response = requests.get("https://api.gold-api.com/price/XAU", timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
        except:
            pass
    
    elif symbol in ["XAGUSD", "SILVER"]:
        try:
            response = requests.get("https://api.gold-api.com/price/XAG", timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
        except:
            pass
    
    elif len(symbol) == 6:
        try:
            url = f"https://api.frankfurter.app/latest?from={symbol[:3]}&to={symbol[3:]}"
            response = requests.get(url, timeout=5)
            data = response.json()
            if "rates" in data and symbol[3:] in data["rates"]:
                return float(data["rates"][symbol[3:]])
        except:
            pass
    
    try:
        binance_symbols = {
            "BTCUSD": "BTCUSDT",
            "ETHUSD": "ETHUSDT"
        }
        if symbol in binance_symbols:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbols[symbol]}"
            response = requests.get(url, timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
    except:
        pass
    
    return None

def check_alerts():
    while True:
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT id, chat_id, symbol, price_level, alert_type FROM alerts WHERE is_active = TRUE')
            alerts = cursor.fetchall()
            
            for alert_id, chat_id, symbol, price_level, alert_type in alerts:
                current_price = get_realtime_price(symbol)
                
                if current_price:
                    if alert_type == "above" and current_price >= price_level:
                        send_telegram_message(chat_id, f"🔔 {symbol} وصل إلى {current_price:.2f}")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
                    elif alert_type == "below" and current_price <= price_level:
                        send_telegram_message(chat_id, f"🔔 {symbol} وصل إلى {current_price:.2f}")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Alert error: {e}")
        
        time.sleep(10)

def handle_command(chat_id, text):
    if text == "/gold":
        price = get_realtime_price("XAUUSD")
        return f"💰 الذهب: {price:.2f}" if price else "❌ خطأ"
    
    elif text == "/silver":
        price = get_realtime_price("XAGUSD")
        return f"💰 الفضة: {price:.2f}" if price else "❌ خطأ"
    
    elif text.startswith("/price"):
        symbol = text.replace("/price", "").strip().upper()
        if symbol:
            price = get_realtime_price(symbol)
            if price:
                return f"💰 {symbol}: {price:.2f}"
            else:
                return "❌ لا يمكن الحصول على السعر"
    
    elif text.startswith("/alert"):
        parts = text.replace("/alert", "").strip().split()
        if len(parts) >= 2:
            symbol = parts[0].upper()
            try:
                price = float(parts[1])
                alert_type = parts[2] if len(parts) > 2 else "above"
                
                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()
                cursor.execute('INSERT INTO alerts (chat_id, symbol, price_level, alert_type) VALUES (?, ?, ?, ?)',
                             (chat_id, symbol, price, alert_type))
                conn.commit()
                conn.close()
                
                return f"✅ تنبيه: {symbol} عند {price}"
            except:
                return "❌ خطأ في السعر"
    
    elif text == "/alerts":
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, price_level, alert_type FROM alerts WHERE chat_id = ? AND is_active = TRUE', (chat_id,))
        alerts = cursor.fetchall()
        conn.close()
        
        if alerts:
            response = "🔔 تنبيهاتك:\n\n"
            for symbol, price, alert_type in alerts:
                response += f"• {symbol} عند {price}\n"
            return response
        return "لا توجد تنبيهات"
    
    elif text in ["/start", "/help"]:
        return """🤖 بوت الأسعار والتنبيهات

/gold - سعر الذهب
/silver - سعر الفضة
/price XAUUSD - سعر لحظي
/alert XAUUSD 2500 above - تنبيه
/alerts - تنبيهاتك"""
    
    return None

def send_telegram_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        print(f"Error: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message")
    
    if not message:
        return "ok"
    
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    response = handle_command(chat_id, text)
    if response:
        send_telegram_message(chat_id, response)
    
    return "ok"

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "running"})

if __name__ == "__main__":
    init_database()
    alert_thread = threading.Thread(target=check_alerts, daemon=True)
    alert_thread.start()
    app.run()
