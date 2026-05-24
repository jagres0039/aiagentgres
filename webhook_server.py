import os

from flask import Flask, jsonify, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0"))

@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """Terima alert dari TradingView"""
    try:
        data = request.json
        if not data:
            data = {"message": request.data.decode('utf-8')}

        alert_msg = data.get('message', str(data))

        import requests
        msg = f"🔔 TRADINGVIEW ALERT!\n\n{alert_msg}"
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": OWNER_ID, "text": msg}
        )
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "running"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
