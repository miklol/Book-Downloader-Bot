"""
Book Downloader Bot
Searches LibGen for books and sends them directly to Telegram users.

Uses python-telegram-bot v20 (async) — compatible with Python 3.13+.
Storage: local db.json file (no external service required).
"""
import os
import math
import json
import html
import traceback
import asyncio
import re
from datetime import datetime
from uuid import uuid4 as uuid

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    filters,
)
from dotenv import load_dotenv
import httpx
from bs4 import BeautifulSoup

def escape_md(text: str) -> str:
    """Escapes reserved characters for Telegram MarkdownV2."""
    # Backslash must be escaped first
    text = text.replace('\\', '\\\\')
    reserved = r'_*[]()~`>#+-=|{}.!'
    for char in reserved:
        text = text.replace(char, f'\\{char}')
    return text

# ── env ──────────────────────────────────────────────────────────────────────
load_dotenv(override=True)

TOKEN = os.getenv('TOKEN')
if not TOKEN:
    raise ValueError("TOKEN is not set in .env")

ADMIN_ID = [1697562512]  # replace with your own Telegram user id

# ── local JSON database ───────────────────────────────────────────────────────
DB_FILE = 'db.json'


def _load_db() -> dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'total_downloads': 0, 'users': {}}


def _save_db(data: dict):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def db_get_total_downloads() -> int:
    return _load_db().get('total_downloads', 0)


def db_add_downloads(mb: int):
    data = _load_db()
    data['total_downloads'] = data.get('total_downloads', 0) + mb
    _save_db(data)


def db_create_user(user_info: dict):
    uid = str(user_info.get('id', ''))
    data = _load_db()
    if uid not in data.get('users', {}):
        data.setdefault('users', {})[uid] = user_info
        _save_db(data)


def db_get_all_users() -> list:
    return list(_load_db().get('users', {}).values())


# ── libgen config ─────────────────────────────────────────────────────────────
LIBGEN_URL = 'https://libgen.li/index.php'
LIBGEN_MIRRORS = [
    'https://libgen.li/index.php',
    'https://libgen.la/index.php',
    'https://libgen.gl/index.php',
    'https://libgen.bz/index.php',
    'https://libgen.vg/index.php',
]

# ── messages ──────────────────────────────────────────────────────────────────
WELCOME_MESSAGE = (
    "✨ *Welcome to Book Hunter v2\\.1* ✨\n\n"
    "I can find almost any book for you on LibGen\\.\n"
    "Simply send me a **Book Title** or **Author Name**\\.\n\n"
    "💡 *Advanced Search:*\n"
    "• `/title Python` — Search only by title\n"
    "• `/author Orwell` — Search only by author\n\n"
    "⚠️ *Note: Files \\> 50 MB are filtered for speed\\.*\n\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🛠 *Created by @itsmiklol by the nudge of @dagem008*\n"
    "📢 *Join [Habesha Base](https://t.me/habeshabase) for updates*"
)

BOOK_TEXT_TEMPLATE = (
    "👤 *Author:* {author}\n"
    "📖 *Title:* {title}\n"
    "📦 *Size:* {size}\n"
    "🗂 *Format:* {file}\n"
    "📅 *Year:* {year}\n"
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ── helpers ───────────────────────────────────────────────────────────────────

async def send_request(url, url_params=None, referer=None) -> str | None:
    headers = HEADERS.copy()
    if referer:
        headers['Referer'] = referer
        
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        try:
            res = await client.get(url, params=url_params)
            if res.status_code == 200:
                return res.text
            else:
                print(f"Request to {url} failed with status {res.status_code}")
        except Exception as e:
            print(f"Request to {url} failed: {e}")

    return None


async def get_file_url(mirror: str) -> tuple[str | None, str | None]:
    print(f"Fetching mirror page: {mirror}")
    # Use the mirror itself as referer
    page = await send_request(mirror, referer=mirror)
    if not page:
        print("Failed to fetch mirror page.")
        return None, None
    
    # Determine base URL from the mirror link
    from urllib.parse import urlparse, urljoin
    parsed = urlparse(mirror)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Use regex to find the download link (get.php?md5=...&key=...)
    # Handles & or &amp;
    m = re.search(r'href=[\'"](get\.php\?md5=[a-f0-9]{32}(?:&|&amp;)key=[A-Za-z0-9]+)[\'"]', page)
    if m:
        path = m.group(1).replace('&amp;', '&')
        url = urljoin(base_url, path)
        print(f"Found download URL via regex: {url}")
    else:
        # Fallback to BeautifulSoup
        soup = BeautifulSoup(page, features='html.parser')
        # Common patterns for LibGen download links
        a_get = soup.find('a', string=lambda s: s and "GET" in s.upper())
        if not a_get:
            a_get = soup.find('a', href=lambda h: h and "get.php" in h)
        if not a_get:
            # Look for button/id="info"
            a_get = soup.find('a', id='info')
        
        url = a_get.get('href') if a_get else None
        if url and 'get.php' in url:
            url = urljoin(base_url, url)
        print(f"Found download URL via BS4: {url}")

    if not url:
        return None, None

    soup = BeautifulSoup(page, features='html.parser')
    h1 = soup.find('h1')
    file_name = h1.get_text(strip=True) if h1 else 'book'
    
    # Sanitize filename for Windows
    file_name = re.sub(r'[\\/*?:"<>|]', "", file_name)
    
    return url, file_name


def get_books(page_html: str) -> list:
    books = []
    soup = BeautifulSoup(page_html, features='html.parser')
    
    tables = soup.find_all('table')
    if not tables:
        return books
    
    # Find table with at least 5 rows
    data_table = None
    for t in tables:
        if len(t.find_all('tr')) > 5:
            data_table = t
            break
    
    if not data_table:
        data_table = max(tables, key=lambda t: len(t.find_all('tr')))

    rows = data_table.find_all('tr')
    for i, row in enumerate(rows):
        if len(books) >= 10:
            break
        tds = row.find_all('td')
        if not tds or len(tds) < 5:
            continue
            
        book = {}
        
        # Try to find the mirror link first
        a_mirror = row.find('a', href=re.compile(r'ads\.php\?md5='))
        if not a_mirror:
            a_mirror = row.find('a', href=re.compile(r'get\.php\?md5='))
        if not a_mirror:
            a_mirror = row.find('a', href=lambda h: h and 'library.lol' in h)
            
        if not a_mirror:
            continue

        link = a_mirror.get('href', '')
        if 'md5=' in link:
            # We found a valid book entry
            # Now extract metadata based on typical column order
            # Usually: Title is the one with the link that isn't the mirror link
            all_links = row.find_all('a')
            title_a = None
            for a in all_links:
                if a != a_mirror and len(a.get_text(strip=True)) > 3:
                    title_a = a
                    break
            
            book['title'] = title_a.get_text(strip=True) if title_a else tds[0].get_text(strip=True)
            book['author'] = tds[1].get_text(strip=True) if len(tds) > 1 else 'Unknown'
            # Sizes and types are usually in the last few columns
            book['size'] = tds[-3].get_text(strip=True) if len(tds) > 3 else 'N/A'
            book['file'] = tds[-2].get_text(strip=True) if len(tds) > 2 else 'pdf'
            book['year'] = tds[-7].get_text(strip=True) if len(tds) > 7 else 'N/A'
            book['link'] = link
            
            # Size filter
            size_str = book.get('size', '').lower()
            if 'mb' in size_str:
                try:
                    size_val = float(size_str.replace('mb', '').strip())
                    if size_val > 50: continue
                except: pass
            elif 'gb' in size_str: continue

            if book not in books:
                books.append(book)

    return books[:10]


async def search_book(name: str, column: str = 'def') -> list:
    url_params = {
        'req': name,
        'open': 0,
        'res': 25,
        'view': 'simple',
        'phrase': 1,
        'column': column,
    }
    
    # Try multiple mirrors for search
    for mirror in LIBGEN_MIRRORS:
        print(f"Searching on mirror: {mirror}")
        response = await send_request(mirror, url_params)
        if response:
            books = get_books(response)
            if books:
                return books
    
    return []


async def download_book(url: str, file_name: str, status_message, timeout: int = 120):
    await status_message.edit_text('⬇️ Starting download...')
    print(f"Downloading from: {url}")
    total = 0
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=HEADERS) as client:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                print(f"Download stream failed with status {response.status_code}")
                raise Exception(f"Server returned status {response.status_code}")
                
            total = int(response.headers.get("Content-Length", 0))
            prev = -1
            with open(file_name, 'wb') as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
                    if total:
                        percent = (response.num_bytes_downloaded / total) * 100
                        step = int((percent // 10) * 10)
                        if step != prev:
                            try:
                                await status_message.edit_text(f'⬇️ Downloading... {step}%')
                            except Exception:
                                pass
                            prev = step

    try:
        await status_message.edit_text('✅ Download complete!')
    except Exception as e:
        print('Error updating status:', e)

    if total:
        total_mb = math.ceil(total / 1024 / 1024)
        db_add_downloads(total_mb)


# ── handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.today()
    # keyboard = [[InlineKeyboardButton("☕ Buy me a coffee", url='https://www.buymeacoffee.com/chapimenge')]]
    # reply_markup = InlineKeyboardMarkup(keyboard)
    reply_markup = None

    if today.day % 2 == 0:
        total = escape_md(str(db_get_total_downloads()))
        text = WELCOME_MESSAGE + f'\n\n📊 Total downloads so far: *{total} MB*'
    else:
        text = WELCOME_MESSAGE

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

    user_info = update.message.from_user.to_dict()
    db_create_user(user_info)


async def search_book_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await update.message.reply_text('🔍 Searching...')
    
    # Handle commands /title and /author
    text = update.message.text
    column = 'def'
    query = text
    
    if text.startswith('/title '):
        query = text.replace('/title ', '', 1).strip()
        column = 'title'
    elif text.startswith('/author '):
        query = text.replace('/author ', '', 1).strip()
        column = 'author'
    
    if not query:
        await status.edit_text('❌ Please provide a search term. Example: `/title Python`', parse_mode=ParseMode.MARKDOWN_V2)
        return

    books = await search_book(query, column=column)

    if not books:
        await status.edit_text('❌ No books found. Try a different search term.')
        return

    response_text = '🔍 *Search Results:*\n'
    response_text += '━━━━━━━━━━━━━━━━━━\n\n'
    
    keyboards = []
    row = []
    for i, book in enumerate(books):
        # escape for MarkdownV2
        author = escape_md(book.get('author', 'N/A'))
        title = escape_md(book.get('title', 'Unknown'))
        size = escape_md(book.get('size', 'N/A'))
        year = escape_md(book.get('year', 'N/A'))
        fmt = escape_md(book.get('file', 'N/A')).upper()

        response_text += f'*{i + 1}\\. {title}*\n'
        response_text += f'👤 _{author}_\n'
        response_text += f'📦 `{size}` \\| 📅 `{year}` \\| 🗂 `{fmt}`\n\n'

        # Extract MD5 for callback
        link = book.get('link', '')
        md5 = ''
        if 'md5=' in link:
            m = re.search(r'md5=([a-f0-9]{32})', link)
            if m: md5 = m.group(1)
        
        if not md5:
            md5 = f"idx{i}"

        ext = book.get('file', 'pdf')[:5]
        # Callback data: dl_[MD5]_[EXT]
        button_data = f'dl_{md5}_{ext}'
        row.append(InlineKeyboardButton(f"📥 Get #{i + 1}", callback_data=button_data))
        
        if len(row) == 2:
            keyboards.append(row)
            row = []
            
    if row:
        keyboards.append(row)

    # Navigation buttons
    keyboards.append([InlineKeyboardButton("🔄 Search Again", callback_data="search_again")])

    response_text += '━━━━━━━━━━━━━━━━━━\n'
    response_text += 'Tap a button below to download 👇'

    await status.delete()
    await update.message.reply_text(
        response_text,
        reply_markup=InlineKeyboardMarkup(keyboards),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def send_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "search_again":
        await query.message.reply_text("Please send me the book title or author name you want to search for.")
        return

    # Callback format: dl_MD5_EXT
    parts = query.data.split('_')
    if len(parts) < 3 or parts[0] != 'dl':
        await query.edit_message_text('❌ Invalid selection. Please search again.')
        return
        
    md5 = parts[1]
    file_type = parts[2]
    
    status = await query.edit_message_text(text='🔍 Locating file on mirrors...')
    
    url = None
    file_name = None
    
    # Try multiple mirrors for the download link
    download_bases = [
        'https://libgen.li',
        'https://libgen.la',
        'https://libgen.gl',
        'https://libgen.bz',
        'https://libgen.vg',
    ]
    
    for base in download_bases:
        mirror_link = f'{base}/ads.php?md5={md5}'
        url, file_name = await get_file_url(mirror_link)
        if url and file_name:
            break
            
    if not url or not file_name:
        await query.edit_message_text('❌ Could not retrieve download link. Try another book.')
        return

    unique = str(uuid())[:8]
    slug = '-'.join(file_name.lower().split())[:80]
    os.makedirs('books', exist_ok=True)
    unique_file_name = f'books/{slug}-{unique}.{file_type}'

    try:
        await download_book(url, unique_file_name, status)
    except Exception as e:
        await status.edit_text(f'❌ Download failed: {e}')
        return

    display_name = file_name if file_name.lower().endswith(f'.{file_type.lower()}') else f'{file_name}.{file_type}'

    try:
        await status.edit_text('📤 Sending the file...')
    except Exception:
        pass

    await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)

    with open(unique_file_name, 'rb') as f:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=f,
            filename=display_name,
            caption='📚 Enjoy your book! 😊',
        )

    try:
        os.remove(unique_file_name)
    except Exception:
        pass


async def get_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_ID:
        return
    total_downloads = escape_md(str(db_get_total_downloads()))
    all_users = db_get_all_users()
    num_users = escape_md(str(len(all_users)))
    await update.message.reply_text(
        f'📊 *Stats*\n\nTotal downloads: *{total_downloads} MB*\nTotal users: *{num_users}*',
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)
    print("Exception:\n", tb_string)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f'<b>An exception occurred</b>\n\n'
        f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n'
        f'<pre>{html.escape(tb_string)}</pre>'
    )

    for admin in ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=admin, text=message[:4000], parse_mode=ParseMode.HTML)
        except Exception:
            pass

    if isinstance(update, Update) and update.message:
        await update.message.reply_text('Sorry, something went wrong. Please try again.')


async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_ID:
        await update.message.reply_text('Unrecognized command')
        return ConversationHandler.END
    await update.message.reply_text('Enter the message to broadcast:')
    return 1


async def send_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast'] = {
        'from_chat_id': update.message.chat_id,
        'message_id': update.message.message_id,
    }
    context.application.create_task(run_broadcast(context))
    await update.message.reply_text('Broadcasting message...')
    return ConversationHandler.END


async def run_broadcast(context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get('broadcast', {})
    all_users = db_get_all_users()
    sent = 0
    for user in all_users:
        try:
            await context.bot.copy_message(chat_id=int(user['id']), **data)
            sent += 1
        except Exception as e:
            print(f"Failed to send to {user.get('id')}: {e}")
        await asyncio.sleep(0.3)
    for admin in ADMIN_ID:
        await context.bot.send_message(
            chat_id=admin,
            text=f'✅ Broadcast done. Sent to {sent}/{len(all_users)} users.',
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Cancelled.')
    return ConversationHandler.END


async def clean_files(context: ContextTypes.DEFAULT_TYPE):
    print('Cleaning stale book files...')
    books_dir = 'books'
    if not os.path.exists(books_dir):
        return
    now = datetime.now()
    for fname in os.listdir(books_dir):
        fpath = os.path.join(books_dir, fname)
        age_seconds = (now - datetime.fromtimestamp(os.path.getmtime(fpath))).total_seconds()
        if age_seconds > 3600:
            try:
                os.remove(fpath)
            except Exception as e:
                print(f"Could not delete {fpath}: {e}")


async def update_web_stats(context: ContextTypes.DEFAULT_TYPE):
    """Generates a non-sensitive stats.json for the public status page."""
    data = _load_db()
    users_list = []
    for uid, uinfo in data.get('users', {}).items():
        users_list.append({
            'name': uinfo.get('first_name', 'Unknown'),
            'username': uinfo.get('username', 'N/A')
        })
    
    stats = {
        'total_downloads': data.get('total_downloads', 0),
        'total_users': len(users_list),
        'users': users_list[-10:],  # Show last 10 users
        'last_heartbeat': datetime.now().isoformat(),
        'server_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def create_bot_app():
    """Initializes the Telegram bot application."""
    os.makedirs('books', exist_ok=True)
    app = Application.builder().token(TOKEN).build()

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler('broadcast', broadcast_message)],
        states={1: [MessageHandler(filters.ALL, send_broadcast_message)]},
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('stat', get_stat))
    app.add_handler(CommandHandler('title', search_book_handler))
    app.add_handler(CommandHandler('author', search_book_handler))
    app.add_handler(broadcast_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_book_handler))
    app.add_handler(CallbackQueryHandler(send_file))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(clean_files, interval=3600, first=10)
    app.job_queue.run_repeating(update_web_stats, interval=60, first=0)
    
    return app


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    app = create_bot_app()
    print('Bot is running... (Polling Mode)')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
