from flask import Flask, request
import logging
import os
import requests
from bs4 import BeautifulSoup
import time
import threading
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ======= CONFIGURATION =======

URL = "https://www.marukyu-koyamaen.co.jp/english/shop/products/catalog/matcha?viewall=1"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SHEET_NAME = "MatchaStock"
CREDENTIALS_FILE = "/etc/secrets/credentials.json"

# ======= LOGGING =======

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# ======= GOOGLE SHEETS SETUP =======

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).worksheet("Sheet1")

def get_subscriber_sheet():
    try:
        return client.open(SHEET_NAME).worksheet("Subscribers")
    except Exception as e:
        logging.error(f"❌ Could not access Subscribers sheet: {e}")
        return None

def load_subscribers():
    try:
        sheet_subs = get_subscriber_sheet()
        if sheet_subs:
            return [row[0] for row in sheet_subs.get_all_values()[1:]]
    except Exception as e:
        logging.error(f"❌ Failed to load subscribers: {e}")
    return []

def add_subscriber(user_id):
    user_id = str(user_id)
    existing = load_subscribers()
    if user_id not in existing:
        try:
            sheet_subs = get_subscriber_sheet()
            if sheet_subs:
                sheet_subs.append_row([user_id])
                logging.info(f"✅ Added subscriber: {user_id}")
        except Exception as e:
            logging.error(f"❌ Failed to add subscriber: {e}")

def remove_subscriber(user_id):
    user_id = str(user_id)
    try:
        sheet_subs = get_subscriber_sheet()
        if sheet_subs:
            records = sheet_subs.get_all_values()
            for idx, row in enumerate(records[1:], start=2):  # skip header
                if row[0] == user_id:
                    sheet_subs.delete_rows(idx)
                    logging.info(f"✅ Removed subscriber: {user_id}")
                    return
    except Exception as e:
        logging.error(f"❌ Failed to remove subscriber: {e}")

def send_telegram_message(message, user_ids=None):
    user_ids = user_ids or load_subscribers()
    for user_id in user_ids:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()
            logging.info(f"✅ Telegram message sent to {user_id}")
        except Exception as e:
            logging.error(f"❌ Failed to send message to {user_id}: {e}")

def fetch_page():
    try:
        res = requests.get(URL, headers=HEADERS, timeout=10)
        res.raise_for_status()
        return res.text
    except Exception as e:
        logging.error(f"Failed to fetch page: {e}")
        return None

def extract_product_status(html):
    soup = BeautifulSoup(html, "html.parser")
    product_list = soup.select_one("ul.products")
    status_dict = {}

    if not product_list:
        logging.warning("Could not find product list.")
        return status_dict

    for li in product_list.find_all("li", class_="product"):
        class_list = li.get("class", [])
        a_tag = li.find("a", class_="woocommerce-loop-product__link")
        name = a_tag["title"] if a_tag else "Unnamed Product"
        link = a_tag["href"] if a_tag else "#"
        status = "instock" if "instock" in class_list else "outofstock"
        status_dict[name] = {"status": status, "link": link}

    return status_dict

def load_previous_status():
    try:
        data = sheet.get_all_records()
        return {
            row["Product Name"]: {
                "status": row["Status"],
                "link": row["Link"]
            } for row in data
        }
    except Exception as e:
        logging.error(f"Failed to load data from Google Sheets: {e}")
        return {}

def save_current_status(status_dict):
    try:
        sheet.resize(rows=1)
        sheet.update("A1:C1", [["Product Name", "Status", "Link"]])
        rows = [[name, data["status"], data["link"]] for name, data in status_dict.items()]
        sheet.append_rows(rows)
        logging.info("✅ Synced data to Google Sheets")
    except Exception as e:
        logging.error(f"❌ Failed to save data to Google Sheets: {e}")

def notify_on_status_changes():
    html = fetch_page()
    if not html:
        return

    current_status = extract_product_status(html)
    previous_status = load_previous_status()

    restocked_products = []

    for name, data in current_status.items():
        new_status = data["status"]
        old_status = previous_status.get(name, {}).get("status", "unknown")

        if old_status != "instock" and new_status == "instock":
            restocked_products.append((name, data["link"]))

    if restocked_products:
        message = "*🍵 Matcha Back in Stock:*\n\n"
        for name, link in restocked_products:
            message += f"• [{name}]({link})\n"
        send_telegram_message(message)
    else:
        logging.info("No new restocks.")

    save_current_status(current_status)

# ============ FLASK APP ============

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Matcha Notifier is Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        message = data["message"]
        text = message.get("text", "").strip().lower()
        user_id = message.get("from", {}).get("id")

        if text == "/start":
            add_subscriber(user_id)
            send_telegram_message("👋 *Welcome!* You'll now receive matcha stock updates. Send `/stop` to unsubscribe.", [str(user_id)])

        elif text == "/stop":
            remove_subscriber(user_id)
            send_telegram_message("👋 You've been unsubscribed. Send `/start` again if you change your mind.", [str(user_id)])

    return "ok", 200

# ============ RUN APP AND LOOP ============

def start_notifier():
    while True:
        notify_on_status_changes()
        time.sleep(90)

if __name__ == "__main__":
    threading.Thread(target=start_notifier, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
