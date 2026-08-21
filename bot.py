import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import sqlite3
import threading
import time

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DATABASE_PATH = "trading_bot.db"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, symbol TEXT, price_level REAL, alert_type TEXT, is_active BOOLEAN DEFAULT TRUE)''')
    conn.commit()
    conn.close()

def get_price(symbol):
    symbol = symbol.upper().strip()
    
    if symbol in ["XAUUSD", "GOLD"]:
        try:
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=5)
            return float(r.json()["price"])
        except:
            pass
    elif symbol in ["XAGUSD", "SILVER"]:
        try:
            r = requests.get("https://api.gold-api.com/price/XAG", timeout=5)
            return float(r.json()["price"])
        except:
            pass
    elif len(symbol) == 6:
        try:
            r = requests.get(f"https://api.frankfurter.app/latest?from={symbol[:3]}&to={symbol[3:]}", timeout=5)
            return float(r.json()["rates"][symbol[3:]])
        except:
            pass
    
    try:
        binance_map = {
            "BTCUSD": "BTCUSDT",
            "ETHUSD": "ETHUSDT",
            "SOLUSD": "SOLUSDT",
            "DOGEUSD": "DOGEUSDT",
        }
        if symbol in binance_map:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={binance_map[symbol]}", timeout=5)
            return float(r.json()["price"])
    except:
        pass
    
    return None

def ask_gemini(text):
    if not GEMINI_API_KEY:
        return None
    
    try:
        response = requests.post(
            GEMINI_API_URL,
            headers={
                "Authorization": f"Bearer {GEMINI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "contents": [{"role": "user", "parts": [{"text": text}]}],
            },
            timeout=30,
        )
        data = response.json()
        
        if response.status_code == 200 and "candidates" in data:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return None
    except:
        return None

def check_alerts():
    while True:
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT id, chat_id, symbol, price_level, alert_type FROM alerts WHERE is_active = TRUE')
            alerts = cursor.fetchall()
            
            for alert_id, chat_id, symbol, price_level, alert_type in alerts:
                current_price = get_price(symbol)
                
                if current_price:
                    if alert_type == "above" and current_price >= price_level:
                        send_message(chat_id, f"🔔 {symbol} وصل إلى {current_price:.2f}")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
                    elif alert_type == "below" and current_price <= price_level:
                        send_message(chat_id, f"🔔 {symbol} وصل إلى {current_price:.2f}")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(10)

def handle(chat_id, text):
    
    if text == "/gold":
        price = get_price("XAUUSD")
        if price:
            return f"📊 تحليل الذهب\n\n💰 السعر: {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
    
    elif text == "/silver":
        price = get_price("XAGUSD")
        if price:
            return f"📊 تحليل الفضة\n\n💰 السعر: {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
    
    elif text == "/btc":
        price = get_price("BTCUSD")
        if price:
            return f"📊 تحليل بيتكوين\n\n💰 السعر: {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
    
    elif text == "/eth":
        price = get_price("ETHUSD")
        if price:
            return f"📊 تحليل إيثيريوم\n\n💰 السعر: {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
    
    elif text.startswith("/price"):
        symbol = text.replace("/price", "").strip().upper()
        if symbol:
            price = get_price(symbol)
            if price:
                return f"💰 {symbol}: {price:.2f}"
    
    elif text.startswith("/forex"):
        pair = text.replace("/forex", "").strip().upper()
        if pair:
            price = get_price(pair)
            if price:
                return f"💰 {pair}: {price:.2f}"
    
    elif text.startswith("/analysis"):
        symbol = text.replace("/analysis", "").strip().upper()
        if symbol:
            price = get_price(symbol)
            if price:
                return f"📊 تحليل {symbol}\n\n💰 السعر: {price:.2f}"
    
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
                
                return f"✅ تم إضافة تنبيه:\n• {symbol}\n• السعر: {price}\n• النوع: {alert_type}"
            except:
                pass
        return "استخدم: /alert XAUUSD 2500 above"
    
    elif text == "/alerts":
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, price_level, alert_type FROM alerts WHERE chat_id = ? AND is_active = TRUE', (chat_id,))
        alerts = cursor.fetchall()
        conn.close()
        
        if alerts:
            response = "🔔 تنبيهاتك النشطة:\n\n"
            for symbol, price, alert_type in alerts:
                response += f"• {symbol} عند {price} ({alert_type})\n"
            return response
        return "لا توجد تنبيهات نشطة"
    
    elif text in ["/start", "/help"]:
        return """🤖 بوت التحليل المالي

📊 التحليل:
/gold - تحليل الذهب
/silver - تحليل الفضة
/btc - تحليل بيتكوين
/eth - تحليل إيثيريوم
/forex EURUSD - تحليل عملات
/analysis XAUUSD - تحليل مخصص

💰 الأسعار:
/price XAUUSD - سعر لحظي

🔔 التنبيهات:
/alert XAUUSD 2500 above - تنبيه سعر
/alerts - عرض التنبيهات

💡 أمثلة:
/gold
/price XAUUSD
/alert XAUUSD 2500 above"""
    
    reply = ask_gemini(text)
    if reply:
        return reply
    
    return "عذراً، حدث خطأ"

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
    
    if text:
        response = handle(chat_id, text)
        if response:
            send_message(chat_id, response)
    
    return "ok"

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "running"})

if __name__ == "__main__":
    init_database()
    threading.Thread(target=check_alerts, daemon=True).start()
    app.run()
