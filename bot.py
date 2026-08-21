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
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, chat_id INTEGER, symbol TEXT, price REAL, type TEXT, active INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

# ========== الأسعار ==========
def get_price(symbol):
    symbol = symbol.upper().strip()
    
    # ذهب وفضة
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
    
    # عملات رقمية
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
    
    # عملات أجنبية
    forex_map = {
        "EURUSD": "EUR", "GBPUSD": "GBP", "USDJPY": "JPY",
        "USDCHF": "CHF", "USDCAD": "CAD", "AUDUSD": "AUD",
        "NZDUSD": "NZD"
    }
    
    if symbol in forex_map:
        try:
            r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
            data = r.json()
            if "rates" in data:
                return float(data["rates"][forex_map[symbol]])
        except:
            pass
    
    return None

# ========== تحليل فني ==========
def get_analysis(symbol):
    price = get_price(symbol)
    if not price:
        return None
    
    # بيانات تاريخية من Binance
    try:
        crypto = {
            "XAUUSD": "PAXGUSDT", "BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT",
            "SOLUSD": "SOLUSDT", "DOGEUSD": "DOGEUSDT"
        }
        bin_symbol = crypto.get(symbol, symbol.replace("USD", "USDT"))
        
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={bin_symbol}&interval=1h&limit=50", timeout=5)
        klines = r.json()
        
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        
        # RSI
        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(c, 0) for c in changes[-14:]]
        losses = [max(-c, 0) for c in changes[-14:]]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        
        rsi = 50
        if avg_loss != 0:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        elif avg_gain > 0:
            rsi = 100
        
        # المتوسطات
        ma20 = sum(closes[-20:]) / 20
        ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else ma20
        
        # دعم ومقاومة
        resistance = max(highs[-20:])
        support = min(lows[-20:])
        
        # توصية
        signal = "محايد ⚖️"
        if rsi < 30 and price > ma20:
            signal = "شراء قوي 🟢"
        elif rsi < 40 and price > ma20:
            signal = "شراء 🟢"
        elif rsi > 70 and price < ma20:
            signal = "بيع قوي 🔴"
        elif rsi > 60 and price < ma20:
            signal = "بيع 🔴"
        elif price > ma20 and ma20 > ma50:
            signal = "اتجاه صاعد 📈"
        elif price < ma20 and ma20 < ma50:
            signal = "اتجاه هابط 📉"
        
        analysis = f"""
📊 **تحليل {symbol}**

💰 **السعر:** {price:.2f}
⚡ **التحديث:** {datetime.now().strftime('%H:%M:%S')}

📈 **المؤشرات:**
• RSI: {rsi:.1f}
• MA20: {ma20:.2f}
• MA50: {ma50:.2f}

🎯 **المستويات:**
• مقاومة: {resistance:.2f}
• دعم: {support:.2f}

💡 **التوصية:**
{signal}
"""
        return analysis
        
    except:
        return f"💰 **{symbol}:** {price:.2f}"

# ========== Grok ==========
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
                    {"role": "system", "content": "أنت محلل مالي محترف. حلل الأسواق وأعط توصيات واضحة. أجب بالعربية."},
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

# ========== التنبيهات ==========
def check_alerts():
    while True:
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('SELECT id, chat_id, symbol, price, type FROM alerts WHERE active = 1')
            
            for alert_id, chat_id, symbol, price, type in c.fetchall():
                current = get_price(symbol)
                if current:
                    if type == "above" and current >= price:
                        send(chat_id, f"🔔 {symbol} وصل {current:.2f}")
                        c.execute('UPDATE alerts SET active = 0 WHERE id = ?', (alert_id,))
                    elif type == "below" and current <= price:
                        send(chat_id, f"🔔 {symbol} وصل {current:.2f}")
                        c.execute('UPDATE alerts SET active = 0 WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(10)

# ========== الردود ==========
def handle(chat_id, text):
    t = text.strip()
    
    # تنبيه سهل
    if any(word in t for word in ["نبيه", "نبهني", "خبرني", "قلي", "علمني"]):
        numbers = re.findall(r'\d+\.?\d*', t)
        
        symbol = "XAUUSD"
        for key, val in [("فضة", "XAGUSD"), ("بيتكوين", "BTCUSD"), ("إيثيريوم", "ETHUSD"), ("سولانا", "SOLUSD")]:
            if key in t:
                symbol = val
        
        if numbers:
            price = float(numbers[0])
            type = "below" if any(w in t for w in ["نزل", "تحت", "below"]) else "above"
            
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO alerts (chat_id, symbol, price, type) VALUES (?, ?, ?, ?)', (chat_id, symbol, price, type))
            conn.commit()
            conn.close()
            
            return f"✅ تمام! رح نبعتلك لما {symbol} يوصل {price}"
    
    # تحليل
    if "تحليل" in t or "توصية" in t or "توقع" in t or "طلوع" in t or "نزول" in t:
        if "ذهب" in t:
            return get_analysis("XAUUSD")
        elif "فضة" in t:
            return get_analysis("XAGUSD")
        elif "بيتكوين" in t or "btc" in t.lower():
            return get_analysis("BTCUSD")
        elif "إيثيريوم" in t or "eth" in t.lower():
            return get_analysis("ETHUSD")
        elif "سولانا" in t or "sol" in t.lower():
            return get_analysis("SOLUSD")
        else:
            reply = ask_grok(t)
            if reply:
                return reply
    
    # أسعار
    if "سعر" in t or "كم" in t:
        if "ذهب" in t:
            p = get_price("XAUUSD")
            if p: return f"💰 الذهب: {p:.2f} دولار"
        elif "فضة" in t:
            p = get_price("XAGUSD")
            if p: return f"💰 الفضة: {p:.2f} دولار"
        elif "بيتكوين" in t or "btc" in t.lower():
            p = get_price("BTCUSD")
            if p: return f"💰 بيتكوين: {p:.2f} دولار"
        elif "إيثيريوم" in t or "eth" in t.lower():
            p = get_price("ETHUSD")
            if p: return f"💰 إيثيريوم: {p:.2f} دولار"
        elif "سولانا" in t or "sol" in t.lower():
            p = get_price("SOLUSD")
            if p: return f"💰 سولانا: {p:.2f} دولار"
        elif "دوج" in t or "doge" in t.lower():
            p = get_price("DOGEUSD")
            if p: return f"💰 دوجكوين: {p:.2f} دولار"
    
    # أوامر
    if t == "/alerts":
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('SELECT symbol, price, type FROM alerts WHERE chat_id = ? AND active = 1', (chat_id,))
        alerts = c.fetchall()
        conn.close()
        
        if alerts:
            return "🔔 تنبيهاتك:\n" + "\n".join([f"• {s} عند {p} ({t})" for s, p, t in alerts])
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
