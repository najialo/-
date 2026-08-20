import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import sqlite3
import threading
import time

app = Flask(__name__)

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DATABASE_PATH = "trading_bot.db"

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

# ==================== نظام Gemini ====================
SYSTEM_PROMPT = """أنت "وكيل شباب"، مساعد ذكي متخصص في الأسواق المالية والتداول.

قدراتك:
- تحليل أسعار الذهب والفضة والعملات
- الإجابة على أسئلة التداول والاستثمار
- شرح المفاهيم المالية
- تقديم نصائح استثمارية
- متابعة الأسواق العالمية

أوامر خاصة:
/gold - سعر الذهب
/silver - سعر الفضة
/price [رمز] - سعر لحظي
/alert [رمز] [سعر] [above/below] - تنبيه سعر
/alerts - عرض التنبيهات
/help - المساعدة

اكتب بالعربية، وكن مختصراً ومفيداً."""

def ask_gemini(chat_id, user_message):
    """إرسال سؤال إلى Gemini"""
    try:
        response = requests.post(
            GEMINI_API_URL,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            },
            timeout=30,
        )
        
        data = response.json()
        
        if response.status_code == 200:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            error_msg = data.get("error", {}).get("message", "خطأ")
            print(f"Gemini error: {error_msg}")
            return "عذراً، حدث خطأ. حاول مرة أخرى."
            
    except Exception as e:
        print(f"Gemini exception: {e}")
        return "عذراً، حدث خطأ في الاتصال."

# ==================== قاعدة البيانات ====================
def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            symbol TEXT,
            price_level REAL,
            alert_type TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# ==================== الأسعار اللحظية ====================
def get_realtime_price(symbol: str):
    """الحصول على سعر لحظي"""
    symbol = symbol.upper()
    
    # الذهب
    if symbol in ["XAUUSD", "GOLD", "ذهب"]:
        try:
            response = requests.get("https://api.gold-api.com/price/XAU", timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
        except:
            pass
    
    # الفضة
    elif symbol in ["XAGUSD", "SILVER", "فضة"]:
        try:
            response = requests.get("https://api.gold-api.com/price/XAG", timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
        except:
            pass
    
    # العملات
    elif len(symbol) == 6 and symbol.isalpha():
        try:
            url = f"https://api.frankfurter.app/latest?from={symbol[:3]}&to={symbol[3:]}"
            response = requests.get(url, timeout=5)
            data = response.json()
            if "rates" in data and symbol[3:] in data["rates"]:
                return float(data["rates"][symbol[3:]])
        except:
            pass
    
    # العملات الرقمية
    try:
        binance_symbols = {
            "BTCUSD": "BTCUSDT",
            "ETHUSD": "ETHUSDT",
            "BNBUSD": "BNBUSDT",
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

# ==================== نظام التنبيهات ====================
def check_alerts():
    """فحص التنبيهات"""
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
                        send_telegram_message(chat_id, f"🔔 **تنبيه:** {symbol} وصل إلى {current_price:.2f} (فوق {price_level:.2f})")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
                    elif alert_type == "below" and current_price <= price_level:
                        send_telegram_message(chat_id, f"🔔 **تنبيه:** {symbol} وصل إلى {current_price:.2f} (تحت {price_level:.2f})")
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Alert error: {e}")
        
        time.sleep(10)

# ==================== معالجة الأوامر ====================
def handle_command(chat_id: int, text: str):
    """معالجة الأوامر"""
    
    # الأوامر الخاصة
    if text == "/gold" or text == "سعر الذهب" or text == "الذهب":
        price = get_realtime_price("XAUUSD")
        if price:
            return f"💰 **سعر الذهب:** {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
        return "❌ لا يمكن الحصول على السعر"
    
    elif text == "/silver" or text == "سعر الفضة" or text == "الفضة":
        price = get_realtime_price("XAGUSD")
        if price:
            return f"💰 **سعر الفضة:** {price:.2f} دولار\n⚡ {datetime.now().strftime('%H:%M:%S')}"
        return "❌ لا يمكن الحصول على السعر"
    
    elif text.startswith("/price"):
        symbol = text.replace("/price", "").strip().upper()
        if symbol:
            price = get_realtime_price(symbol)
            if price:
                return f"💰 **{symbol}:** {price:.2f}"
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
                
                return f"✅ **تم إضافة تنبيه:**\n• {symbol}\n• السعر: {price}\n• النوع: {alert_type}"
            except:
                return "❌ خطأ. استخدم: /alert XAUUSD 2500 above"
        return "❌ استخدم: /alert XAUUSD 2500 above"
    
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
    
    elif text == "/start":
        return """🤖 **مرحباً! أنا وكيل شباب**

مساعدك الذكي للأسواق المالية والتداول

💰 **أسعار لحظية:**
/gold - سعر الذهب
/silver - سعر الفضة

🔔 **تنبيهات:**
/alert XAUUSD 2500 above

💬 **أو اسألني أي سؤال!**"""
    
    elif text == "/help":
        return """📋 **الأوامر:**

💰 **الأسعار:**
/gold - الذهب
/silver - الفضة
/price XAUUSD - سعر محدد

🔔 **التنبيهات:**
/alert XAUUSD 2500 above
/alerts - عرض التنبيهات

💬 **أو اسألني أي سؤال عن التداول والأسواق!**"""
    
    return None

# ==================== Telegram ====================
def send_telegram_message(chat_id: int, text: str):
    """إرسال رسالة"""
    try:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        print(f"Error: {e}")

# ==================== Webhook ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message")
    
    if not message:
        return "ok"
    
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    if not text:
        return "ok"
    
    # معالجة الأوامر أولاً
    response = handle_command(chat_id, text)
    
    if response:
        send_telegram_message(chat_id, response)
    else:
        # إذا لم يكن أمر، اسأل Gemini
        send_telegram_message(chat_id, "🤔 جاري التفكير...")
        
        # إرسال حالة كتابة
        try:
            requests.post(
                f"{TELEGRAM_API_URL}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
                timeout=5,
            )
        except:
            pass
        
        # سؤال Gemini
        reply = ask_gemini(chat_id, text)
        send_telegram_message(chat_id, reply)
    
    return "ok"

# ==================== Routes ====================
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "running",
        "bot": "Wakil Shabab Agent",
        "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# ==================== التشغيل ====================
if __name__ == "__main__":
    init_database()
    
    # بدء فحص التنبيهات
    alert_thread = threading.Thread(target=check_alerts, daemon=True)
    alert_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
