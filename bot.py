import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import sqlite3
import threading
import time
import re

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
DATABASE_PATH = "bot.db"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, chat_id INTEGER, symbol TEXT, price REAL, alert_type TEXT, active INTEGER DEFAULT 1)''')
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
    
    crypto = {
        "BTC": "BTCUSDT", "BTCUSD": "BTCUSDT", "بيتكوين": "BTCUSDT",
        "ETH": "ETHUSDT", "ETHUSD": "ETHUSDT", "إيثيريوم": "ETHUSDT",
        "SOL": "SOLUSDT", "SOLUSD": "SOLUSDT", "سولانا": "SOLUSDT",
        "DOGE": "DOGEUSDT", "DOGEUSD": "DOGEUSDT", "دوج": "DOGEUSDT",
        "BNB": "BNBUSDT", "BNBUSD": "BNBUSDT",
        "XRP": "XRPUSDT", "XRPUSD": "XRPUSDT",
        "ADA": "ADAUSDT", "ADAUSD": "ADAUSDT",
        "DOT": "DOTUSDT", "DOTUSD": "DOTUSDT",
        "LTC": "LTCUSDT", "LTCUSD": "LTCUSDT",
        "BCH": "BCHUSDT", "BCHUSD": "BCHUSDT",
        "LINK": "LINKUSDT", "LINKUSD": "LINKUSDT",
        "AVAX": "AVAXUSDT", "AVAXUSD": "AVAXUSDT",
        "MATIC": "MATICUSDT", "MATICUSD": "MATICUSDT",
        "UNI": "UNIUSDT", "UNIUSD": "UNIUSDT",
        "ATOM": "ATOMUSDT", "ATOMUSD": "ATOMUSDT",
        "XLM": "XLMUSDT", "XLMUSD": "XLMUSDT",
        "NEAR": "NEARUSDT", "NEARUSD": "NEARUSDT",
        "APT": "APTUSDT", "APTUSD": "APTUSDT",
        "ARB": "ARBUSDT", "ARBUSD": "ARBUSDT",
        "OP": "OPUSDT", "OPUSD": "OPUSDT",
        "FIL": "FILUSDT", "FILUSD": "FILUSDT",
        "ICP": "ICPUSDT", "ICPUSD": "ICPUSDT",
        "ETC": "ETCUSDT", "ETCUSD": "ETCUSDT",
        "HBAR": "HBARUSDT", "HBARUSD": "HBARUSDT",
        "VET": "VETUSDT", "VETUSD": "VETUSDT",
        "GRT": "GRTUSDT", "GRTUSD": "GRTUSDT",
        "SAND": "SANDUSDT", "SANDUSD": "SANDUSDT",
        "MANA": "MANAUSDT", "MANAUSD": "MANAUSDT",
        "AAVE": "AAVEUSDT", "AAVEUSD": "AAVEUSDT",
        "MKR": "MKRUSDT", "MKRUSD": "MKRUSDT",
        "SNX": "SNXUSDT", "SNXUSD": "SNXUSDT",
        "COMP": "COMPUSDT", "COMPUSD": "COMPUSDT",
        "CRV": "CRVUSDT", "CRVUSD": "CRVUSDT",
        "LDO": "LDOUSDT", "LDOUSD": "LDOUSDT",
        "IMX": "IMXUSDT", "IMXUSD": "IMXUSDT",
        "RNDR": "RNDRUSDT", "RNDRUSD": "RNDRUSDT",
        "INJ": "INJUSDT", "INJUSD": "INJUSDT",
        "SUI": "SUIUSDT", "SUIUSD": "SUIUSDT",
        "PEPE": "PEPEUSDT", "PEPEUSD": "PEPEUSDT",
        "SHIB": "SHIBUSDT", "SHIBUSD": "SHIBUSDT",
        "FLOKI": "FLOKIUSDT", "FLOKIUSD": "FLOKIUSDT",
        "BONK": "BONKUSDT", "BONKUSD": "BONKUSDT",
        "WIF": "WIFUSDT", "WIFUSD": "WIFUSDT"
    }
    
    if symbol in crypto:
        try:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={crypto[symbol]}", timeout=5)
            return float(r.json()["price"])
        except:
            pass
    
    return None

def ask_grok(text):
    if not GROK_API_KEY:
        return None
    
    try:
        r = requests.post(
            GROK_API_URL,
            headers={"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "grok-beta",
                "messages": [
                    {"role": "system", "content": "أنت محلل مالي. أجب بالعربية. أعط توصيات واضحة."},
                    {"role": "user", "content": text}
                ],
                "max_tokens": 800
            },
            timeout=30
        )
        data = r.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        return None
    except:
        return None

def check_alerts():
    while True:
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('SELECT id, chat_id, symbol, price, alert_type FROM alerts WHERE active = 1')
            
            for alert_id, chat_id, symbol, price, alert_type in c.fetchall():
                current = get_price(symbol)
                if current:
                    if alert_type == "above" and current >= price:
                        send(chat_id, f"🔔 {symbol} وصل {current:.2f}")
                        c.execute('UPDATE alerts SET active = 0 WHERE id = ?', (alert_id,))
                    elif alert_type == "below" and current <= price:
                        send(chat_id, f"🔔 {symbol} وصل {current:.2f}")
                        c.execute('UPDATE alerts SET active = 0 WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(10)

def handle(chat_id, text):
    t = text.strip()
    
    if any(word in t for word in ["نبيه", "نبهني", "خبرني", "قلي", "علمني"]):
        numbers = re.findall(r'\d+\.?\d*', t)
        
        symbol = "XAUUSD"
        if "فضة" in t: symbol = "XAGUSD"
        elif "بيتكوين" in t: symbol = "BTCUSD"
        elif "إيثيريوم" in t: symbol = "ETHUSD"
        elif "سولانا" in t: symbol = "SOLUSD"
        elif "دوج" in t: symbol = "DOGEUSD"
        
        if numbers:
            price = float(numbers[0])
            alert_type = "below" if any(w in t for w in ["نزل", "تحت"]) else "above"
            
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO alerts (chat_id, symbol, price, alert_type) VALUES (?, ?, ?, ?)', (chat_id, symbol, price, alert_type))
            conn.commit()
            conn.close()
            
            return f"✅ تمام! رح نبعتلك لما {symbol} يوصل {price}"
    
    if "ذهب" in t:
        p = get_price("XAUUSD")
        if p:
            if any(w in t for w in ["تحليل", "توقع", "توصية", "طلع", "نزل"]):
                reply = ask_grok(f"حلل الذهب XAUUSD سعره الحالي {p} دولار. هل سيطلع أم ينزل؟ أعط توصية واضحة.")
                if reply:
                    return f"📊 **تحليل الذهب**\n💰 السعر: {p:.2f}\n\n{reply}"
            return f"💰 الذهب: {p:.2f} دولار"
    
    if "فضة" in t:
        p = get_price("XAGUSD")
        if p:
            return f"💰 الفضة: {p:.2f} دولار"
    
    if "بيتكوين" in t or "btc" in t.lower():
        p = get_price("BTCUSD")
        if p:
            if any(w in t for w in ["تحليل", "توقع", "توصية", "طلع", "نزل"]):
                reply = ask_grok(f"حلل بيتكوين BTC سعرها الحالي {p} دولار. هل ستطلع أم تنزل؟ أعط توصية واضحة.")
                if reply:
                    return f"📊 **تحليل بيتكوين**\n💰 السعر: {p:.2f}\n\n{reply}"
            return f"💰 بيتكوين: {p:.2f} دولار"
    
    if "إيثيريوم" in t or "eth" in t.lower():
        p = get_price("ETHUSD")
        if p:
            return f"💰 إيثيريوم: {p:.2f} دولار"
    
    if "سولانا" in t or "sol" in t.lower():
        p = get_price("SOLUSD")
        if p:
            return f"💰 سولانا: {p:.2f} دولار"
    
    if "دوج" in t or "doge" in t.lower():
        p = get_price("DOGEUSD")
        if p:
            return f"💰 دوجكوين: {p:.2f} دولار"
    
    if t == "/alerts":
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('SELECT symbol, price, alert_type FROM alerts WHERE chat_id = ? AND active = 1', (chat_id,))
        alerts = c.fetchall()
        conn.close()
        
        if alerts:
            return "🔔 تنبيهاتك:\n" + "\n".join([f"• {s} عند {p}" for s, p, t in alerts])
        return "لا توجد تنبيهات"
    
    if t in ["/start", "/help"]:
        return """🤖 **بوت التحليل الشامل**

💰 **اكتب:**
سعر الذهب / سعر بيتكوين

📊 **تحليل:**
تحليل الذهب / تحليل بيتكوين

🔔 **تنبيه:**
نبهني على الذهب 2500

💬 **أو اسألني أي سؤال**"""
    
    reply = ask_grok(t)
    if reply:
        return reply
    
    return None

def send(chat_id, text):
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
            send(chat_id, response)
    
    return "ok"

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "running"})

if __name__ == "__main__":
    init_db()
    threading.Thread(target=check_alerts, daemon=True).start()
    app.run()
