import sys

file_path = r'c:\Users\Shega Insights\Documents\GitHub\Book-Downloader-Bot\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken multiline strings
content = content.replace("response_text = '🔍 *Search Results:*", "response_text = '🔍 *Search Results:*\\n'")
content = content.replace("response_text += '━━━━━━━━━━━━━━━━━━", "response_text += '━━━━━━━━━━━━━━━━━━\\n\\n'")
content = content.replace("response_text += f'*{i + 1}\\\\. {title}*'", "response_text += f'*{i + 1}\\\\. {title}*\\n'")
content = content.replace("response_text += f'👤 _{author}_'", "response_text += f'👤 _{author}_\\n'")
content = content.replace("response_text += f'📦 `{size}` \\\\| 📅 `{year}` \\\\| 🗂 `{fmt}`'", "response_text += f'📦 `{size}` \\\\| 📅 `{year}` \\\\| 🗂 `{fmt}`\\n\\n'")
content = content.replace("response_text += '━━━━━━━━━━━━━━━━━━", "response_text += '━━━━━━━━━━━━━━━━━━\\n'")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed syntax errors")
