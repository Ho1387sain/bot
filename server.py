from flask import Flask, request
import requests
import pandas as pd
import jdatetime
import os

TOKEN = "127184142:t8EC5x45a2aXInYYgz4L2EeVny7PBb1uiqwgeIpc"
API_URL = f"https://tapi.bale.ai/bot{TOKEN}"
EXCEL_FILE = "data_fixed.xlsx"

app = Flask(__name__)

@app.route("/")
def home():
    return "ربات شهریه‌یار فعال است ✅"

@app.route("/callback")
def callback():
    chat_id = request.args.get("chat_id")
    amount_rial = int(request.args.get("amount"))   # مبلغ ورودی از bot.py (ریال)
    national_id = request.args.get("id").strip()   # رشته نگه می‌داریم
    name = request.args.get("name")
    authority = request.args.get("Authority")
    status = request.args.get("Status")

    amount_toman = amount_rial // 10  # ریال → تومان

    if status == "OK":
        # verify payment
        url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
        data = {
            "merchant_id": "00000000-0000-0000-0000-000000000000",
            "amount": amount_rial,
            "authority": authority
        }
        res = requests.post(url, json=data).json()

        if res.get("data") and res["data"].get("code") == 100:
            # خواندن همه شیت‌ها
            sheets = pd.read_excel(EXCEL_FILE, sheet_name=None)

            df_students = sheets["دانشجویان"]
            df_students["کد ملی"] = df_students["کد ملی"].astype(str).str.strip()

            df_payments = sheets.get("پرداخت‌ها", pd.DataFrame(columns=["تاریخ", "نام", "مبلغ (تومان)", "وضعیت"]))

            # ثبت پرداخت جدید
            shamsi_date = jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M")
            new_row = {
                "تاریخ": shamsi_date,
                "نام": name,
                "مبلغ (تومان)": amount_toman,
                "وضعیت": "موفق"
            }
            df_payments = pd.concat([df_payments, pd.DataFrame([new_row])], ignore_index=True)

            # کم کردن شهریه
            idx = df_students[df_students["کد ملی"] == national_id].index
            if not idx.empty:
                current_tuition = int(df_students.loc[idx[0], "شهریه"])
                new_tuition = max(0, current_tuition - amount_toman)
                df_students.loc[idx[0], "شهریه"] = new_tuition
            else:
                new_tuition = "نامشخص"

            # ذخیره همه شیت‌ها
            with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="w") as writer:
                df_students.to_excel(writer, index=False, sheet_name="دانشجویان")
                df_payments.to_excel(writer, index=False, sheet_name="پرداخت‌ها")

            # پیام موفقیت
            msg = f"✅ پرداخت {amount_toman} تومان با موفقیت ثبت شد.\nمبلغ باقی‌مانده شهریه: {new_tuition} تومان"
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
