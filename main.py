from flask import Flask, request
import requests
import os
import logging

app = Flask(__name__)

BOT_TOKEN = "8290419596:AAGMpsQ1xu-2H53_3L6herkqD1oIu2NwVbo"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def index():
    return "Bot is live!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    app.logger.info(f"📩 Received: {data}")

    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')

        reply = "Welcome!" if text == "/start" else f"You said: {text}"

        res = requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": reply
        })

        app.logger.info(f"✅ Sent: {res.status_code}, {res.text}")

    return "ok"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Render sets this dynamically
    app.run(host='0.0.0.0', port=port)
