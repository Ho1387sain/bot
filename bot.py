import requests
import pandas as pd
import jdatetime
from time import sleep

# ======== تنظیمات ========
TOKEN = "127184142:t8EC5x45a2aXInYYgz4L2EeVny7PBb1uiqwgeIpc"
API_URL = f"https://tapi.bale.ai/bot{TOKEN}"
EXCEL_FILE = "data_fixed.xlsx"

# ======== خواندن اکسل ========
try:
    df = pd.read_excel(EXCEL_FILE, sheet_name="دانشجویان")
    print("فایل اکسل با موفقیت بارگذاری شد!")
except Exception as e:
    print("خطا در خواندن اکسل:", e)
    exit()

# ======== آخرین آپدیت ========
last_update_id = None
user_states = {}  # وضعیت کاربران (برای دنبال کردن مراحل)

print("ربات فعال شد! منتظر پیام‌ها هستم...")

# ======== تابع ساخت لینک پرداخت زرین‌پال ========
def create_test_payment(amount, description, callback_url):
    url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
    data = {
        "merchant_id": "00000000-0000-0000-0000-000000000000",  # مرچنت تستی
        "amount": amount,  # به ریال
        "description": description,
        "callback_url": callback_url
    }
    try:
        res = requests.post(url, json=data).json()
        if res.get("data") and res["data"].get("authority"):
            authority = res["data"]["authority"]
            return f"https://sandbox.zarinpal.com/pg/StartPay/{authority}", authority
    except Exception as e:
        print("خطا در ایجاد لینک پرداخت:", e)
    return None, None


while True:
    try:
        res = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id + 1 if last_update_id else None}, timeout=10)
        data = res.json()

        if "result" in data:
            for update in data["result"]:
                update_id = update["update_id"]
                last_update_id = update_id

                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"].get("text", "").strip()

                    print(f"پیام از {chat_id}: {text}")

                    # 🔹 گزارش مدیر
                    if text == "3861804190":
                        try:
                            df_students = pd.read_excel(EXCEL_FILE, sheet_name="دانشجویان")
                            df_payments = pd.read_excel(EXCEL_FILE, sheet_name="پرداخت‌ها")

                            # جمع مانده شهریه
                            total_remaining = df_students['شهریه'].sum()

                            # جمع پرداخت‌های ماه جاری
                            this_month = jdatetime.datetime.now().strftime("%Y/%m")
                            df_payments['تاریخ'] = df_payments['تاریخ'].astype(str)
                            monthly_payments = df_payments[df_payments['تاریخ'].str.startswith(this_month)]
                            total_paid = monthly_payments['مبلغ (تومان)'].sum()

                            report = (
                                f"📊 گزارش ماه جاری ({this_month})\n"
                                f"💰 مجموع پرداختی‌ها: {int(total_paid)} تومان\n"
                                f"🏷 مانده کل شهریه‌ها: {int(total_remaining)} تومان"
                            )
                        except Exception as e:
                            report = f"⚠️ خطا در تهیه گزارش: {e}"

                        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": report})
                        continue

                    # مرحله شروع
                    if text == "/start":
                        msg = "سلام! لطفاً کد ملی خود را وارد کنید."
                        user_states[chat_id] = {"step": "waiting_national_id"}
                        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": msg})

                    # دریافت کد ملی
                    elif user_states.get(chat_id, {}).get("step") == "waiting_national_id" and text.isdigit():
                        national_id = int(text)
                        row = df[df['کد ملی'] == national_id]
                        if not row.empty:
                            name = row.iloc[0]['نام']
                            tuition = row.iloc[0]['شهریه']

                            if tuition <= 0:
                                reply = f"کد ملی: {national_id}\nنام: {name}\n✅ شهریه شما تسویه شده است."
                                user_states[chat_id] = {}
                            else:
                                user_states[chat_id] = {"step": "ask_payment", "id": national_id, "name": name}
                                reply = f"کد ملی: {national_id}\nنام: {name}\nمبلغ شهریه: {tuition} تومان\n\nآیا می‌خواهید مبلغی پرداخت کنید؟ (بله/خیر)"
                        else:
                            reply = "کد ملی شما یافت نشد!"
                        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": reply})

                    # پرسش برای پرداخت
                    elif user_states.get(chat_id, {}).get("step") == "ask_payment":
                        if text in ["بله", "بلی", "Yes", "yes"]:
                            user_states[chat_id]["step"] = "waiting_amount"
                            msg = "لطفاً مبلغ پرداختی خود را به ریال وارد کنید:"
                        else:
                            msg = "پرداختی ثبت نشد. برای شروع دوباره /start را بزنید."
                            user_states[chat_id] = {}
                        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": msg})

                    # دریافت مبلغ → ساخت لینک پرداخت
                    elif user_states.get(chat_id, {}).get("step") == "waiting_amount" and text.isdigit():
                        amount_rial = int(text)  # مبلغ ورودی به ریال
                        name = user_states[chat_id]["name"]
                        national_id = user_states[chat_id]["id"]

                        # ایجاد لینک پرداخت تستی
                        payment_url, authority = create_test_payment(
                            amount_rial, f"پرداخت شهریه توسط {name}",
                            f"https://bot-xma5.onrender.com/callback?chat_id={chat_id}&amount={amount_rial}&id={national_id}&name={name}"

                        )

                        if payment_url:
                            msg = f"✅ مبلغ {amount_rial // 10} تومان ثبت شد.\nبرای پرداخت روی لینک زیر کلیک کنید:\n{payment_url}\n\n🔹 توجه: این لینک آزمایشی است."
                        else:
                            msg = "⚠️ خطا در ایجاد لینک پرداخت!"
                        user_states[chat_id] = {}
                        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": msg})

                    else:
                        msg = "لطفاً کد ملی معتبر وارد کنید یا /start بزنید."
                        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": msg})

        sleep(2)

    except Exception as e:
        print("خطا:", e)
        sleep(5)
