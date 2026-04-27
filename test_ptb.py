from telegram.ext import Application
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN')

def main():
    print(f"Testing PTB with token: {TOKEN[:10]}...")
    try:
        app = Application.builder().token(TOKEN).build()
        print("Success: Application built!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
