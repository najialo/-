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
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, symbol TEXT, price_level REAL, alert_type TEXT, is_active BOOLEAN DEFAULT TRUE)''')
    conn.commit()
    conn.close()

# ==================== الأسعار ====================
def get_price(symbol):
    symbol = symbol.upper().strip()
    
    # الذهب
    if symbol in ["XAUUSD", "GOLD", "ذهب", "الذهب"]:
        try:
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=5)
            return float(r.json()["price"])
        except:
            pass
    
    # الفضة
    elif symbol in ["XAGUSD", "SILVER", "فضة", "الفضة"]:
        try:
            r = requests.get("https://api.gold-api.com/price/XAG", timeout=5)
            return float(r.json()["price"])
        except:
            pass
    
    # العملات الأجنبية
    elif len(symbol) == 6 and symbol.isalpha():
        try:
            r = requests.get(f"https://api.frankfurter.app/latest?from={symbol[:3]}&to={symbol[3:]}", timeout=5)
            return float(r.json()["rates"][symbol[3:]])
        except:
            pass
    
    # العملات الرقمية من Binance
    try:
        binance_map = {
            "BTCUSD": "BTCUSDT", "BTC": "BTCUSDT", "بيتكوين": "BTCUSDT",
            "ETHUSD": "ETHUSDT", "ETH": "ETHUSDT", "إيثيريوم": "ETHUSDT",
            "BNBUSD": "BNBUSDT", "BNB": "BNBUSDT",
            "XRPUSD": "XRPUSDT", "XRP": "XRPUSDT",
            "ADAUSD": "ADAUSDT", "ADA": "ADAUSDT",
            "DOGEUSD": "DOGEUSDT", "DOGE": "DOGEUSDT",
            "SOLUSD": "SOLUSDT", "SOL": "SOLUSDT",
            "DOTUSD": "DOTUSDT", "DOT": "DOTUSDT",
            "LTCUSD": "LTCUSDT", "LTC": "LTCUSDT",
            "BCHUSD": "BCHUSDT", "BCH": "BCHUSDT",
            "LINKUSD": "LINKUSDT", "LINK": "LINKUSDT",
            "MATICUSD": "MATICUSDT", "MATIC": "MATICUSDT",
            "AVAXUSD": "AVAXUSDT", "AVAX": "AVAXUSDT",
            "UNIUSD": "UNIUSDT", "UNI": "UNIUSDT",
            "ATOMUSD": "ATOMUSDT", "ATOM": "ATOMUSDT",
            "XLMUSD": "XLMUSDT", "XLM": "XLMUSDT",
            "NEARUSD": "NEARUSDT", "NEAR": "NEARUSDT",
            "APTUSD": "APTUSDT", "APT": "APTUSDT",
            "ARBUSD": "ARBUSDT", "ARB": "ARBUSDT",
            "OPUSD": "OPUSDT", "OP": "OPUSDT",
            "FILUSD": "FILUSDT", "FIL": "FILUSDT",
            "ICPUSD": "ICPUSDT", "ICP": "ICPUSDT",
            "ETCUSD": "ETCUSDT", "ETC": "ETCUSDT",
            "HBARUSD": "HBARUSDT", "HBAR": "HBARUSDT",
            "VETUSD": "VETUSDT", "VET": "VETUSDT",
            "GRTUSD": "GRTUSDT", "GRT": "GRTUSDT",
            "SANDUSD": "SANDUSDT", "SAND": "SANDUSDT",
            "MANAUSD": "MANAUSDT", "MANA": "MANAUSDT",
            "AAVEUSD": "AAVEUSDT", "AAVE": "AAVEUSDT",
            "MKRUSD": "MKRUSDT", "MKR": "MKRUSDT",
            "SNXUSD": "SNXUSDT", "SNX": "SNXUSDT",
            "COMPUSD": "COMPUSDT", "COMP": "COMPUSDT",
            "CRVUSD": "CRVUSDT", "CRV": "CRVUSDT",
            "LDOUSD": "LDOUSDT", "LDO": "LDOUSDT",
            "IMXUSD": "IMXUSDT", "IMX": "IMXUSDT",
            "RNDRUSD": "RNDRUSDT", "RNDR": "RNDRUSDT",
            "INJUSD": "INJUSDT", "INJ": "INJUSDT",
            "SUIUSD": "SUIUSDT", "SUI": "SUIUSDT",
            "PEPEUSD": "PEPEUSDT", "PEPE": "PEPEUSDT",
            "SHIBUSD": "SHIBUSDT", "SHIB": "SHIBUSDT",
            "FLOKIUSD": "FLOKIUSDT", "FLOKI": "FLOKIUSDT",
            "BONKUSD": "BONKUSDT", "BONK": "BONKUSDT",
            "WIFUSD": "WIFUSDT", "WIF": "WIFUSDT",
            "JUPUSD": "JUPUSDT", "JUP": "JUPUSDT",
            "PYTHUSD": "PYTHUSDT", "PYTH": "PYTHUSDT",
            "SEIUSD": "SEIUSDT", "SEI": "SEIUSDT",
            "TIAUSD": "TIAUSDT", "TIA": "TIAUSDT",
            "STRKUSD": "STRKUSDT", "STRK": "STRKUSDT",
            "ENAUSD": "ENAUSDT", "ENA": "ENAUSDT",
            "ETHFIUSD": "ETHFIUSDT", "ETHFI": "ETHFIUSDT",
            "ORDIUSD": "ORDIUSDT", "ORDI": "ORDIUSDT",
            "SATSUSD": "1000SATSUSDT", "SATS": "1000SATSUSDT",
        }
        
        if symbol in binance_map:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={binance_map[symbol]}", timeout=5)
            return float(r.json()["price"])
    except:
        pass
    
    return None

# ==================== Gemini ====================
def ask_gemini(text):
    if not GEMINI_API_KEY:
        return None
    
    try:
        response = requests.post(
            GEMINI_API_URL,
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": "أنت مساعد ذكي تجيب على أي سؤال بالعربية. كن مختصراً ومفيداً."}]},
                "contents": [{"role": "user", "parts": [{"text": text}]}],
            },
            timeout=30,
        )
        data = response.json()
        
        if response.status_code == 200:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return None
    except:
        return None

# ==================== التنبيهات ====================
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
                        send_message(chat_id, f"🔔 **تنبيه:** {symbol} وصل إلى {current_price:.2f} (فوق {price_level:.2f})")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
                    elif alert_type == "below" and current_price <= price_level:
                        send_message(chat_id, f"🔔 **تنبيه:** {symbol} وصل إلى {current_price:.2f} (تحت {price_level:.2f})")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
        except:
            pass
        time.sleep(10)

# ==================== الأوامر ====================
def handle(chat_id, text):
    
    # أوامر الأسعار
    if text.startswith("/price") or text.startswith("سعر"):
        if text.startswith("/price"):
            symbol = text.replace("/price", "").strip()
        else:
            symbol = text.replace("سعر", "").strip()
        
        if symbol:
            price = get_price(symbol)
            if price:
                return f"💰 **{symbol.upper()}:** {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
            return f"❌ لا يمكن الحصول على سعر {symbol}"
    
    elif text == "/gold" or "ذهب" in text:
        price = get_price("XAUUSD")
        if price:
            return f"📊 **الذهب**\n\n💰 **السعر:** {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
    
    elif text == "/silver" or "فضة" in text:
        price = get_price("XAGUSD")
        if price:
            return f"📊 **الفضة**\n\n💰 **السعر:** {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
    
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
                
                return f"✅ **تم إضافة تنبيه:**\n• {symbol}\n• السعر: {price}\n• النوع: {alert_type}"
            except:
                return "❌ خطأ. استخدم: /alert BTCUSD 100000 above"
        return "❌ استخدم: /alert BTCUSD 100000 above"
    
    elif text == "/alerts":
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, price_level, alert_type FROM alerts WHERE chat_id = ? AND is_active = TRUE', (chat_id,))
        alerts = cursor.fetchall()
        conn.close()
        
        if alerts:
            response = "🔔 **تنبيهاتك النشطة:**\n\n"
            for symbol, price, alert_type in alerts:
                response += f"• {symbol} عند {price} ({alert_type})\n"
            return response
        return "لا توجد تنبيهات نشطة"
    
    elif text in ["/start", "/help"]:
        return """🤖 **البوت الذكي**

💰 **الأسعار:**
/gold - الذهب
/silver - الفضة
/price BTC - بيتكوين
/price ETH - إيثيريوم
/price XAUUSD - ذهب

🔔 **التنبيهات:**
/alert BTCUSD 100000 above
/alerts - تنبيهاتك

💬 **أو اسألني أي سؤال!**"""
    
    # أي سؤال → Gemini
    reply = ask_gemini(text)
    if reply:
        return reply
    
    # محاولة أخيرة - إذا النص فيه اسم عملة
    price = get_price(text)
    if price:
        return f"💰 **{text.upper()}:** {price:.2f} دولار"
    
    return "اكتب /help لمعرفة الأوامر"

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
