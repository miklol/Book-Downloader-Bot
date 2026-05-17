import os
import sys
from flask import Flask, request, jsonify, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix
from telegram import Update
from main import create_bot_app, TOKEN

# Initialize Flask app
app = Flask(__name__)
# Tell Flask it is behind a proxy (like Render) to correctly resolve https:// for webhooks
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize Telegram Bot Application
# Note: We don't run_polling here; we use webhooks.
bot_app = create_bot_app()

@app.before_request
async def startup():
    if not bot_app.running:
        await bot_app.initialize()
        await bot_app.start()

@app.route('/')
def index():
    """Serves the status page."""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Status page (index.html) not found.", 404

@app.route('/stats.json')
def stats():
    """Serves the stats.json file."""
    try:
        with open('stats.json', 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'application/json'}
    except FileNotFoundError:
        return jsonify({"error": "Stats not generated yet"}), 404

@app.route(f'/{TOKEN}', methods=['POST'])
async def webhook():
    """Handles Telegram webhook updates."""
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        await bot_app.process_update(update)
        return "OK", 200
    return "Forbidden", 403

# Helper to set webhook
@app.route('/set_webhook')
async def set_webhook():
    webhook_url = request.url_root + TOKEN
    success = await bot_app.bot.set_webhook(url=webhook_url)
    if success:
        return f"Webhook set to: {webhook_url}", 200
    return "Failed to set webhook", 500

if __name__ == '__main__':
    # Local testing or direct execution fallback
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
