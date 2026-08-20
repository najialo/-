import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import sqlite3
import threading
import time
import pandas as pd
import numpy as np
import yfinance as yf
from bs4 import BeautifulSoup

app = Flask(__name__)

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DATABASE_PATH = "trading_bot.db"

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

# ==================== قاعدة البيانات ====================
def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    """الحصول على سعر لحظي من مصادر متعددة"""
    symbol = symbol.upper()
    
    # 1. العملات الرقمية من Binance
    try:
        binance_symbols = {
            "BTCUSD": "BTCUSDT",
            "ETHUSD": "ETHUSDT",
            "BNBUSD": "BNBUSDT",
            "XRPUSD": "XRPUSDT",
            "ADAUSD": "ADAUSDT",
            "DOGEUSD": "DOGEUSDT",
            "SOLUSD": "SOLUSDT",
        }
        if symbol in binance_symbols:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbols[symbol]}"
            response = requests.get(url, timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
    except:
        pass
    
    # 2. الذهب والفضة من GoldAPI
    try:
        if symbol == "XAUUSD" or symbol == "GOLD":
            response = requests.get("https://api.gold-api.com/price/XAU", timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
        elif symbol == "XAGUSD" or symbol == "SILVER":
            response = requests.get("https://api.gold-api.com/price/XAG", timeout=5)
            data = response.json()
            if "price" in data:
                return float(data["price"])
    except:
        pass
    
    # 3. العملات الأجنبية من Frankfurter
    try:
        if len(symbol) == 6 and symbol.isalpha():
            url = f"https://api.frankfurter.app/latest?from={symbol[:3]}&to={symbol[3:]}"
            response = requests.get(url, timeout=5)
            data = response.json()
            if "rates" in data and symbol[3:] in data["rates"]:
                return float(data["rates"][symbol[3:]])
    except:
        pass
    
    # 4. احتياطي: Yahoo Finance
    try:
        symbol_map = {
            "XAUUSD": "GC=F",
            "XAGUSD": "SI=F",
            "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X",
            "USDJPY": "JPY=X",
            "BTCUSD": "BTC-USD",
            "ETHUSD": "ETH-USD",
        }
        yf_symbol = symbol_map.get(symbol, symbol)
        ticker = yf.Ticker(yf_symbol)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    
    return None

# ==================== التحليل الفني ====================
def get_analysis(symbol: str) -> str:
    """تحليل فني شامل"""
    current_price = get_realtime_price(symbol)
    
    if not current_price:
        return "❌ لا يمكن الحصول على سعر لهذا الرمز"
    
    try:
        symbol_map = {
            "XAUUSD": "GC=F",
            "XAGUSD": "SI=F",
            "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X",
            "USDJPY": "JPY=X",
            "BTCUSD": "BTC-USD",
            "ETHUSD": "ETH-USD",
        }
        
        yf_symbol = symbol_map.get(symbol, symbol)
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="1d", interval="5m")
        
        if df.empty:
            return f"💰 السعر اللحظي لـ {symbol}: {current_price:.2f}"
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands
        sma = df['Close'].rolling(window=20).mean()
        std = df['Close'].rolling(window=20).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        # المتوسطات المتحركة
        ma20 = df['Close'].rolling(window=20).mean()
        ma50 = df['Close'].rolling(window=50).mean()
        
        # مستويات الدعم والمقاومة
        recent_high = df['High'].tail(20).max()
        recent_low = df['Low'].tail(20).min()
        
        analysis = f"""
📊 **تحليل {symbol}**

💰 **السعر:** {current_price:.2f}

📈 **المؤشرات الفنية:**
"""
        
        # RSI
        if not rsi.empty:
            rsi_val = rsi.iloc[-1]
            analysis += f"• RSI: {rsi_val:.2f} "
            if rsi_val > 70:
                analysis += "⚠️ تشبع شرائي\n"
            elif rsi_val < 30:
                analysis += "✅ تشبع بيعي\n"
            else:
                analysis += "📊 محايد\n"
        
        # MACD
        if not macd.empty and not signal.empty:
            analysis += f"• MACD: {macd.iloc[-1]:.4f} "
            if macd.iloc[-1] > signal.iloc[-1]:
                analysis += "✅ شراء\n"
            else:
                analysis += "❌ بيع\n"
        
        # Bollinger
        if not upper.empty and not lower.empty:
            analysis += f"• Bollinger: {upper.iloc[-1]:.2f} - {lower.iloc[-1]:.2f}\n"
        
        # المتوسطات
        if not ma20.empty and not ma50.empty:
            analysis += f"• MA20: {ma20.iloc[-1]:.2f}\n"
            analysis += f"• MA50: {ma50.iloc[-1]:.2f}\n"
            if ma20.iloc[-1] > ma50.iloc[-1]:
                analysis += "  ↳ اتجاه صاعد ✅\n"
            else:
                analysis += "  ↳ اتجاه هابط ❌\n"
        
        # مستويات
        analysis += f"""
🎯 **مستويات مهمة:**
• مقاومة: {recent_high:.2f}
• دعم: {recent_low:.2f}

⚡ **تحديث:** {datetime.now().strftime('%H:%M:%S')}
"""
        
        return analysis
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return f"💰 السعر اللحظي لـ {symbol}: {current_price:.2f}"

# ==================== نظام التنبيهات ====================
def check_alerts():
    """فحص التنبيهات كل 10 ثواني"""
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
                        message = f"🔔 **تنبيه:** {symbol} وصل إلى {current_price:.2f} (فوق {price_level:.2f})"
                        send_telegram_message(chat_id, message)
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
                    elif alert_type == "below" and current_price <= price_level:
                        message = f"🔔 **تنبيه:** {symbol} وصل إلى {current_price:.2f} (تحت {price_level:.2f})"
                        send_telegram_message(chat_id, message)
                        cursor.execute('UPDATE alerts SET is_active = FALSE WHERE id = ?', (alert_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Alert error: {e}")
        
        time.sleep(10)

# ==================== معالجة الأوامر ====================
def handle_command(chat_id: int, text: str):
    """معالجة أوامر المستخدم"""
    
    # التحليل
    if text == "/gold":
        return get_analysis("XAUUSD")
    
    elif text == "/silver":
        return get_analysis("XAGUSD")
    
    elif text == "/btc":
        return get_analysis("BTCUSD")
    
    elif text == "/eth":
        return get_analysis("ETHUSD")
    
    elif text.startswith("/forex"):
        pair = text.replace("/forex", "").strip().upper()
        if pair:
            return get_analysis(pair)
        else:
            return "استخدم: /forex EURUSD"
    
    elif text.startswith("/analysis"):
        symbol = text.replace("/analysis", "").strip().upper()
        if symbol:
            return get_analysis(symbol)
        else:
            return "استخدم: /analysis XAUUSD"
    
    # السعر اللحظي
    elif text.startswith("/price"):
        symbol = text.replace("/price", "").strip().upper()
        if symbol:
            price = get_realtime_price(symbol)
            if price:
                return f"💰 **{symbol}:** {price:.2f}\n⚡ {datetime.now().strftime('%H:%M:%S')}"
            else:
                return "❌ لا يمكن الحصول على السعر"
        else:
            return "استخدم: /price XAUUSD"
    
    # التنبيهات
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
                return "❌ خطأ في السعر"
        else:
            return "استخدم: /alert XAUUSD 2500 above"
    
    # عرض التنبيهات
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
        else:
            return "لا توجد تنبيهات نشطة"
    
    # المساعدة
    elif text == "/help" or text == "/start":
        return """🤖 **بوت التحليل المالي**

📊 **التحليل:**
/gold - تحليل الذهب
/silver - تحليل الفضة
/btc - تحليل بيتكوين
/eth - تحليل إيثيريوم
/forex EURUSD - تحليل عملات
/analysis XAUUSD - تحليل مخصص

💰 **الأسعار:**
/price XAUUSD - سعر لحظي

🔔 **التنبيهات:**
/alert XAUUSD 2500 above - تنبيه سعر
/alerts - عرض التنبيهات

💡 **أمثلة:**
/gold
/price XAUUSD
/alert XAUUSD 2500 above"""
    
    return None

# ==================== Telegram API ====================
def send_telegram_message(chat_id: int, text: str):
    """إرسال رسالة"""
    try:
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        print(f"Error sending: {e}")

# ==================== Webhook ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message")
    
    if not message:
        return "ok"
    
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    # حفظ المستخدم
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)',
                      (chat_id, message["from"].get("username", ""), message["from"].get("first_name", "")))
        conn.commit()
        conn.close()
    except:
        pass
    
    # معالجة الأمر
    response = handle_command(chat_id, text)
    if response:
        send_telegram_message(chat_id, response)
    
    return "ok"

# ==================== Routes ====================
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "running",
        "bot": "Trading Analysis Bot",
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
