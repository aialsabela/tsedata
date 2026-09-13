import requests
import pandas as pd
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# هدرهای کاملاً طبیعی برای جلوگیری از بلاک شدن توسط فایروال TSETMC
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://main.tsetmc.com/',
    'Origin': 'https://main.tsetmc.com'
}

def send_telegram_message(text):
    """ارسال پیام به تلگرام"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("تنظیمات تلگرام یافت نشد.")
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
        print(f"خطا در ارسال به تلگرام: {e}")

def calculate_fast_rsi(prices, rsi_period=14, ma_period=9):
    """محاسبه دقیق RSI و MaRSI مطابق فرمول شما"""
    if len(prices) < rsi_period + ma_period + 5:
        return None

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

def process_single_stock(item):
    """دریافت سابقه ۶۰ روزه با کنترل سرعت درخواست‌ها"""
    ins_code = item.get('insCode')
    symbol = item.get('lVal18AFC')
    title = item.get('lVal30')
    last_price = item.get('pDrCSec')

    if not ins_code or not symbol:
        return None

    try:
        history_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ins_code}/60"
        
        # ارسال درخواست مستقیم
        res = requests.get(history_url, headers=HEADERS, timeout=10)
        
        if res.status_code != 200:
            return None

        daily_data = res.json().get('closingPriceDaily', [])
        if len(daily_data) < 40:
            return None

        daily_data.sort(key=lambda x: x['dEven'])
        prices = [d['pClosing'] for d in daily_data if d['pClosing'] > 0]

        result = calculate_fast_rsi(prices)
        if not result:
            return None

        rsi = result['rsi']
        ma_rsi = result['ma_rsi']

        # شرط فیلتر: RSI > MaRSI و RSI < 50
        if rsi > ma_rsi and rsi < 50:
            return {
                'symbol': symbol,
                'title': title,
                'rsi': rsi,
                'ma_rsi': ma_rsi,
                'last_price': last_price
            }

    except Exception:
        return None

def main():
    print("در حال دریافت دیده‌بان بازار از CDN اصلی TSETMC...")
    mw_url = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&organ=0"
    
    try:
        res = requests.get(mw_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"خطا در دریافت دیده‌بان: کد {res.status_code}")
            sys.exit(1)

        data = res.json()
        items = data.get('marketWatch', [])
        print(f"تعداد کل نمادهای دریافتی: {len(items)}")

        # فیلتر کردن نمادهای غیر سهمی
        ignored_keywords = ['ح', 'صندوق', 'اخزا', 'اراد', 'گام', 'ض', 'ج', 'سکه', 'مرابحه', 'تسه']
        valid_items = []
        
        for item in items:
            sym = item.get('lVal18AFC', '')
            if sym and not any(sym.endswith(kw) or sym.startswith(kw) for kw in ignored_keywords):
                valid_items.append(item)

        print(f"تعداد {len(valid_items)} سهم انتخاب شد. محاسبه بدون فشار به سرور...")

        filtered_list = []
        # کاهش سرعت درخواست‌ها به ۵ درخواست همزمان جهت جلوگیری از مسدود شدن IP
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(process_single_stock, valid_items)
            for r in results:
                if r:
                    filtered_list.append(r)

        print(f"پردازش با موفقیت تمام شد! تعداد سیگنال‌ها: {len(filtered_list)}")

        if not filtered_list:
            send_telegram_message("🤖 <b>فیلتر RSI بورس (۶۰ روزه):</b>\nامروز هیچ سهمی واجد شرایط فیلتر نشد.")
            return

        # ساخت پیام تلگرام
        msg = f"🎯 <b>سیگنال فیلتر RSI بورس (۶۰ روزه):</b>\n"
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

    except Exception as e:
        print(f"خطای کلی: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
