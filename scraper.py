import pytse_client as tse
import pandas as pd
import requests
import os
import sys
from concurrent.futures import ThreadPoolExecutor

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    """ارسال پیام به تلگرام"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("خطا: تنظیمات تلگرام یافت نشد.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطا در ارسال پیام به تلگرام: {e}")

def calculate_fast_rsi(df, rsi_period=14, ma_period=9):
    """محاسبه RSI مطابق فرمول شما"""
    if len(df) < rsi_period + ma_period + 1:
        return None

    df = df.sort_values(by='date', ascending=True)
    prices = df['close'].tolist()

    gains = []
    losses = []

    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)

    if not gains:
        return None

    k = 2 / (rsi_period + 1)
    avg_gain = gains[0]
    avg_loss = losses[0]
    rsi_array = []

    for i in range(1, len(gains)):
        avg_gain = (gains[i] * k) + (avg_gain * (1 - k))
        avg_loss = (losses[i] * k) + (avg_loss * (1 - k))

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        rsi_array.append(rsi)

    if len(rsi_array) < ma_period:
        return None

    current_rsi = rsi_array[-1]
    recent_rsi_slice = rsi_array[-ma_period:]
    current_marsi = sum(recent_rsi_slice) / ma_period

    return {
        'rsi': round(current_rsi, 1),
        'ma_rsi': round(current_marsi, 1)
    }

def check_symbol(symbol):
    """بررسی فیلتر برای یک نماد"""
    try:
        ticker = tse.Ticker(symbol)
        df = ticker.history

        if df.empty or len(df) < 25:
            return None

        result = calculate_fast_rsi(df)
        if not result:
            return None

        rsi = result['rsi']
        ma_rsi = result['ma_rsi']

        # شرط فیلتر: RSI > MaRSI و RSI < 50
        if rsi > ma_rsi and rsi < 50:
            return {
                'symbol': symbol,
                'title': ticker.title,
                'rsi': rsi,
                'ma_rsi': ma_rsi,
                'last_price': ticker.last_price
            }
    except Exception:
        return None

def main():
    print("در حال دریافت لیست تمام نمادها...")
    all_syms = list(tse.all_symbols())
    
    # فیلتر هوشمند: حذف صندوق‌ها، اوراق قرضه، اختیار معامله و... جهت افزایش سرعت
    ignored_keywords = ['ح', 'صندوق', 'اخزا', 'اراد', 'گام', 'ض', 'ج', 'سکه', 'مرابحه', 'تسه']
    filtered_symbols = []
    
    for s in all_syms:
        if not any(s.endswith(kw) or s.startswith(kw) for kw in ignored_keywords):
            filtered_symbols.append(s)

    print(f"تعداد {len(filtered_symbols)} سهم اصلی انتخاب شد. شروع بررسی همزمان...")

    filtered_list = []
    # استفاده از ۳۰ پردازش همزمان (سرعت فوق‌العاده بالا)
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(check_symbol, filtered_symbols)
        for res in results:
            if res:
                filtered_list.append(res)

    print(f"پردازش تمام شد! تعداد سهم‌های سیگنال شده: {len(filtered_list)}")

    if not filtered_list:
        send_telegram_message("🤖 <b>فیلتر RSI بورس:</b>\nامروز هیچ سهمی واجد شرایط فیلتر نشد.")
        return

    msg = f"🎯 <b>سیگنال فیلتر RSI بورس:</b>\n"
    msg += f"📊 تعداد سهم‌های یافت شده: {len(filtered_list)}\n\n"

    for item in filtered_list:
        msg += f"🔹 <b>{item['symbol']}</b> ({item['title']})\n"
        msg += f"├ قیمت: {item['last_price']:,} ریال\n"
        msg += f"├ RSI (14): <code>{item['rsi']}</code>\n"
        msg += f"└ MaRSI (9): <code>{item['ma_rsi']}</code>\n\n"

    if len(msg) > 4000:
        for x in range(0, len(msg), 4000):
            send_telegram_message(msg[x:x+4000])
    else:
        send_telegram_message(msg)

if __name__ == "__main__":
    main()
