import os
import sys
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update
from main import create_bot_app, TOKEN

# Initialize Telegram Bot Application
bot_app = create_bot_app()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await bot_app.initialize()
    await bot_app.start()
    yield
    # Shutdown
    await bot_app.stop()
    await bot_app.shutdown()

# Initialize FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

@app.get('/')
async def index():
    """Serves the status page."""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="Status page (index.html) not found.", status_code=404)

@app.get('/stats.json')
async def stats():
    """Serves the stats.json file."""
    try:
        with open('stats.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return JSONResponse(content=data, status_code=200)
    except FileNotFoundError:
        return JSONResponse(content={"error": "Stats not generated yet"}, status_code=404)
    except json.JSONDecodeError:
        return JSONResponse(content={"error": "Invalid JSON in stats file"}, status_code=500)

@app.post(f'/{TOKEN}')
async def webhook(request: Request):
    """Handles Telegram webhook updates."""
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return Response(content="OK", status_code=200)

# Helper to set webhook
@app.get('/set_webhook')
async def set_webhook(request: Request):
    # Ensure URL is https if deployed behind proxy
    base_url = str(request.base_url)
    if "onrender.com" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
        
    webhook_url = base_url + TOKEN
    success = await bot_app.bot.set_webhook(url=webhook_url)
    if success:
        return HTMLResponse(content=f"Webhook set to: {webhook_url}", status_code=200)
    return HTMLResponse(content="Failed to set webhook", status_code=500)

if __name__ == '__main__':
    # Local testing or direct execution fallback
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
