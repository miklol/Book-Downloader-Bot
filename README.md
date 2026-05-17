# Book Hunter Bot (Book-Downloader-Bot)

Book Hunter is an asynchronous Telegram bot that searches Library Genesis (LibGen) for books and sends them directly to users on Telegram. It's built with Python using the `python-telegram-bot` (v20+) library, and features a fallback-ready mirror scraper, large-file filtering, and a live web status dashboard.

## 🌟 Features
- **Direct Downloads:** Downloads books directly from LibGen mirrors and uploads them to Telegram without third-party file sharing links.
- **Smart Search:** Search by general query, or use specific `/title` and `/author` commands for more precise results.
- **Mirror Fallbacks:** Automatically rotates through multiple LibGen mirrors to ensure high availability and bypass blocks.
- **Live Status Dashboard:** Includes a Flask-based web dashboard (`index.html`) to display real-time bot statistics (users, total downloaded MB, system status).
- **Dual Execution Modes:** 
  - **Polling Mode:** Easy local execution (`main.py`)
  - **Webhook Mode:** Production-ready Flask server setup (`app.py`)
- **Built-in Housekeeping:** Automatically cleans up temporary downloaded files and maintains local JSON database records (`db.json` & `stats.json`).

## 🛠 Tech Stack
- **Python 3.13+**
- **python-telegram-bot (v20+)** for Async Telegram Bot API
- **Flask** for webhook handling and web dashboard serving
- **BeautifulSoup4 & httpx** for async web scraping and downloading

## 💬 Bot Commands
| Command | Description |
|---|---|
| `/start` | Start the bot and see total download stats. |
| `/title <name>` | Search exclusively by book title. |
| `/author <name>` | Search exclusively by author name. |
| `/stat` | *(Admin Only)* View total bot statistics. |
| `/broadcast` | *(Admin Only)* Broadcast a message to all users. |

*Note: You can also just type any query directly to perform a general search.*

---

## 🚀 Setup & Installation

### 1. Prerequisites
Ensure you have Python installed and clone the repository. Then install dependencies:
```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
TOKEN=your_telegram_bot_token_here
```
*(Optional: Open `main.py` and update the `ADMIN_ID` list with your personal Telegram User ID to enable admin commands).*

### 3. Running the Bot

There are two ways to run the bot depending on your deployment needs:

#### Option A: Local Polling Mode (Easiest)
Ideal for local testing or running on a personal computer/VPS without setting up reverse proxies or SSL certificates.
```bash
python main.py
```
*The bot will connect to Telegram and start responding immediately.*

#### Option B: Flask Webhook Mode (Production)
Ideal for deploying to cloud platforms (like Render, Railway, or Heroku) that require an HTTP server. This mode also serves the web dashboard!
```bash
python app.py
```
*Note: To use webhooks, you must expose your server to the internet (via HTTPS) and visit `<your-url>/set_webhook` to tell Telegram where to send updates.*

## 📂 Project Structure
- `main.py` - Core bot logic, LibGen scraper, and polling executor.
- `app.py` - Flask web server for handling Telegram webhooks and serving the frontend.
- `index.html` - The frontend UI for the status dashboard.
- `db.json` - Local database tracking users and download statistics.
- `stats.json` - Periodically generated public stats consumed by the web dashboard.
- `books/` - Temporary directory for processing downloaded files before uploading to Telegram.
