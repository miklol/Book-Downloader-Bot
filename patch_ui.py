import sys
import re

file_path = r'c:\Users\Shega Insights\Documents\GitHub\Book-Downloader-Bot\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern for search_book_handler
search_pattern = r'async def search_book_handler\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?await update\.message\.reply_text\(.*?response_text,.*?reply_markup=InlineKeyboardMarkup\(keyboards\),.*?parse_mode=ParseMode\.MARKDOWN_V2,.*?\)'
replacement_handler = """async def search_book_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await update.message.reply_text('🔍 Searching...')
    text = update.message.text
    books = await search_book(text)

    if not books:
        await status.edit_text('❌ No books found. Try a different search term.')
        return

    response_text = '🔍 *Search Results:*\\n'
    response_text += '━━━━━━━━━━━━━━━━━━\\n\\n'
    
    keyboards = []
    row = []
    for i, book in enumerate(books):
        # escape for MarkdownV2
        author = escape_md(book.get('author', 'N/A'))
        title = escape_md(book.get('title', 'Unknown'))
        size = escape_md(book.get('size', 'N/A'))
        year = escape_md(book.get('year', 'N/A'))
        fmt = escape_md(book.get('file', 'N/A')).upper()

        response_text += f'*{i + 1}\\\\. {title}*\\n'
        response_text += f'👤 _{author}_\\n'
        response_text += f'📦 `{size}` \\\\| 📅 `{year}` \\\\| 🗂 `{fmt}`\\n\\n'

        # Extract MD5 for callback
        link = book.get('link', '')
        md5 = ''
        if 'md5=' in link:
            import re
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

    response_text += '━━━━━━━━━━━━━━━━━━\\n'
    response_text += 'Tap a button below to download 👇'

    await status.delete()
    await update.message.reply_text(
        response_text,
        reply_markup=InlineKeyboardMarkup(keyboards),
        parse_mode=ParseMode.MARKDOWN_V2,
    )"""

new_content = re.sub(search_pattern, replacement_handler, content, flags=re.DOTALL)

# Pattern for send_file
send_file_pattern = r'async def send_file\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?await query\.answer\(\).*?query\.edit_message_text\(text=\'🔗 Getting download link\.\.\.\'\).*?url, file_name = await get_file_url\(link\)'
replacement_send_file = """async def send_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Callback format: dl_MD5_EXT
    parts = query.data.split('_')
    if len(parts) < 3 or parts[0] != 'dl':
        await query.edit_message_text('❌ Invalid selection. Please search again.')
        return
        
    md5 = parts[1]
    file_type = parts[2]
    
    # libgen.li mirror link
    mirror_link = f'http://libgen.li/ads.php?md5={md5}'

    status = await query.edit_message_text(text='🔍 Locating file on mirror...')
    url, file_name = await get_file_url(mirror_link)"""

new_content = re.sub(send_file_pattern, replacement_send_file, new_content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Regex patch applied")
