import pytse_client as tse
import pandas as pd
import sys

def get_data():
    print("در حال دریافت اطلاعات بازار از طریق pytse-client...")
    try:
        # دریافت اطلاعات کلیه نمادهای فعال بازار
        tickers = tse.all_symbols()
        print(f"تعداد کل نمادها: {len(tickers)}")
        
        # ساخت یک جدول ساده از اطلاعات نمادها
        data = []
        for symbol in tickers:
            data.append({
                'Symbol': symbol
            })
            
        df = pd.DataFrame(data)
        df.to_csv("market_data.csv", index=False, encoding='utf-8-sig')
        print("اطلاعات با موفقیت در فایل market_data.csv ذخیره شد.")

    except Exception as e:
        print(f"خطا در دریافت اطلاعات: {e}")
        sys.exit(1)

if __name__ == "__main__":
    get_data()
