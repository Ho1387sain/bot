from flask import Flask, request
import requests
import pandas as pd
import jdatetime

TOKEN = "127184142:t8EC5x45a2aXInYYgz4L2EeVny7PBb1uiqwgeIpc"
API_URL = f"https://tapi.bale.ai/bot{TOKEN}"
EXCEL_FILE = "data_fixed.xlsx"

app = Flask(__name__)

@app.route("/callback")
def callback():
    chat_id = request.args.get("chat_id")
    amount_rial = int(request.args.get("amount"))   # مبلغ واقعی که از bot.py اومده (به ریال)
    national_id = int(request.args.get("id"))
    name = request.args.get("name")
    authority = request.args.get("Authority")
    status = request.args.get("Status")

    amount_toman = amount_rial // 10  # ریال → تومان برای ذخیره در اکسل

    if status == "OK":
        # verify payment (با ریال)
        url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
        data = {
            "merchant_id": "00000000-0000-0000-0000-000000000000",
            "amount": amount_rial,   # ⚠️ اینجا باید همون ریال بمونه
            "authority": authority
        }
        res = requests.post(url, json=data).json()

        if res.get("data") and res["data"].get("code") == 100:
            # خواندن فایل
            df = pd.read_excel(EXCEL_FILE, sheet_name="دانشجویان")
            payments = pd.read_excel(EXCEL_FILE, sheet_name="پرداخت‌ها")

            # تاریخ شمسی
            shamsi_date = jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M")

            # ثبت پرداخت جدید
            new_row = {
                "تاریخ": shamsi_date,
                "نام": name,
                "مبلغ (تومان)": amount_toman,
                "وضعیت": "موفق"
            }
            payments = pd.concat([payments, pd.DataFrame([new_row])], ignore_index=True)

            # کم کردن از شهریه (به تومان)
            df.loc[df['کد ملی'] == national_id, 'شهریه'] -= amount_toman
            remaining = int(df.loc[df['کد ملی'] == national_id, 'شهریه'].values[0])

            # ذخیره در اکسل
            with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="w") as writer:
                df.to_excel(writer, index=False, sheet_name="دانشجویان")
                payments.to_excel(writer, index=False, sheet_name="پرداخت‌ها")

            # پیام موفقیت به کاربر (به تومان)
            msg = f"✅ پرداخت {amount_toman} تومان با موفقیت ثبت شد.\nمبلغ باقی‌مانده شهریه: {remaining} تومان"
            requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": msg})

            return "پرداخت موفق بود ✅"
        else:
            msg = "❌ پرداخت ناموفق بود."
            requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": msg})
            return "پرداخت ناموفق بود ❌"
    else:
        msg = "❌ پرداخت توسط کاربر لغو شد."
        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": msg})
        return "پرداخت لغو شد ❌"

if __name__ == "__main__":
    app.run(port=5000)
