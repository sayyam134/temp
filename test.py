from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Replace with your bot token
TOKEN = "8290419596:AAGMpsQ1xu-2H53_3L6herkqD1oIu2NwVbo"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # Example: echo command
        if text == "/start":
            reply = "Welcome to the bot! 😊"
        else:
            reply = f"You said: {text}"

        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": reply
        })

    return "ok"

if __name__ == '__main__':
    app.run(debug=True)

