import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import sqlite3
import threading
import time

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
DATABASE_PATH = "trading_bot.db"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, symbol TEXT, price_level REAL, alert_type TEXT, is_active BOOLEAN DEFAULT TRUE)''')
    conn.commit()
    conn.close()

def get_price(symbol):
    symbol = symbol.upper().strip()
    
    if symbol in ["XAUUSD", "GOLD", "ذهب", "الذهب"]:
        try:
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=5)
            return float(r.json()["price"])
        except:
            pass
    
    if symbol in ["XAGUSD", "SILVER", "فضة", "الفضة"]:
        try:
            r = requests.get("https://api.gold-api.com/price/XAG", timeout=5)
            return float(r.json()["price"])
        except:
            pass
    
    try:
        binance_map = {
            "BTCUSD": "BTCUSDT", "BTC": "BTCUSDT", "بيتكوين": "BTCUSDT",
            "ETHUSD": "ETHUSDT", "ETH": "ETHUSDT", "إيثيريوم": "ETHUSDT",
            "SOLUSD": "SOLUSDT", "SOL": "SOLUSDT", "سولانا": "SOLUSDT",
            "DOGEUSD": "DOGEUSDT", "DOGE": "DOGEUSDT", "دوج": "DOGEUSDT",
            "BNBUSD": "BNBUSDT", "BNB": "BNBUSDT",
            "XRPUSD": "XRPUSDT", "XRP": "XRPUSDT"
        }
        if symbol in binance_map:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={binance_map[symbol]}", timeout=5)
            return float(r.json()["price"])
    except:
        pass
    
    return None

def ask_grok(text):
    if not GROK_API_KEY:
        return None
    
    try:
        response = requests.post(
            GROK_API_URL,
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-beta",
                "messages": [
                    {"role": "system", "content": "أنت مساعد ذكي. أجب بالعربية باختصار."},
                    {"role": "user", "content": text}
                ],
                "max_tokens": 1000
            },
            timeout=30,
        )
        data = response.json()
        
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
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
    t = text.strip()
    
    # تنبيه سهل
    if "نبيه" in t or "نبهني" in t or "خبرني" in t or "قلي" in t:
        # استخراج الرمز والسعر
        import re
        numbers = re.findall(r'\d+\.?\d*', t)
        
        symbol = "XAUUSD"
        if "ذهب" in t:
            symbol = "XAUUSD"
        elif "فضة" in t:
            symbol = "XAGUSD"
        elif "بيتكوين" in t or "btc" in t.lower():
            symbol = "BTCUSD"
        elif "إيثيريوم" in t or "eth" in t.lower():
            symbol = "ETHUSD"
        
        if numbers:
            price = float(numbers[0])
            alert_type = "above"
            if "نزل" in t or "تحت" in t or "below" in t:
                alert_type = "below"
            
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO alerts (chat_id, symbol, price_level, alert_type) VALUES (?, ?, ?, ?)',
                         (chat_id, symbol, price, alert_type))
            conn.commit()
            conn.close()
            
            return f"✅ تمام! رح نبعتلك رسالة لما {symbol} يوصل {price} ({alert_type})"
    
    # أسعار سهلة
    if "ذهب" in t:
        price = get_price("XAUUSD")
        if price:
            return f"💰 الذهب: {price:.2f} دولار"
    
    if "فضة" in t:
        price = get_price("XAGUSD")
        if price:
            return f"💰 الفضة: {price:.2f} دولار"
    
    if "بيتكوين" in t or "btc" in t.lower():
        price = get_price("BTCUSD")
        if price:
            return f"💰 بيتكوين: {price:.2f} دولار"
    
    if "إيثيريوم" in t or "eth" in t.lower():
        price = get_price("ETHUSD")
        if price:
            return f"💰 إيثيريوم: {price:.2f} دولار"
    
    if "سولانا" in t or "sol" in t.lower():
        price = get_price("SOLUSD")
        if price:
            return f"💰 سولانا: {price:.2f} دولار"
    
    if "دوج" in t or "doge" in t.lower():
        price = get_price("DOGEUSD")
        if price:
            return f"💰 دوجكوين: {price:.2f} دولار"
    
    # أوامر قديمة
    if t.startswith("/alert"):
        parts = t.replace("/alert", "").strip().split()
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
                pass
        return "اكتب: نبهني على الذهب 2500"
    
    if t == "/alerts":
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, price_level, alert_type FROM alerts WHERE chat_id = ? AND is_active = TRUE', (chat_id,))
        alerts = cursor.fetchall()
        conn.close()
        
        if alerts:
            response = "🔔 تنبيهاتك:\n\n"
            for symbol, price, alert_type in alerts:
                response += f"• {symbol} عند {price} ({alert_type})\n"
            return response
        return "لا توجد تنبيهات"
    
    if t in ["/start", "/help"]:
        return """🤖 **البوت الذكي**

💰 **الأسعار - اكتب:**
- سعر الذهب
- سعر الفضة
- سعر بيتكوين
- سعر إيثيريوم

🔔 **تنبيه - اكتب:**
- نبهني على الذهب 2500
- خبرني إذا بيتكوين نزل 90000

💬 **أو اسألني أي سؤال**"""
    
    reply = ask_grok(t)
    if reply:
        return reply
    
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
