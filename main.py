# main.py
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, CONSUMER_KEY, CONSUMER_SECRET
from requests_oauthlib import OAuth1Session
import os

# --- لیست بلاک‌شونده‌ها ---
BLOCK_LIST_FILE = "block_list.txt"

# --- تنظیمات لاگ ---
logging.basicConfig(level=logging.INFO)

# --- در حافظه نگه‌می‌داریم session توییتر هر کاربر را ---
user_sessions = {}

# مرحله اول: شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! برای اینکه لیست مشخصی از کاربران رو توی توییترت بلاک کنم، اول باید وارد توییتر بشی. لطفاً دستور /login رو بزن.")

# مرحله دوم: لاگین به توییتر
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri='oob')
    request_token_response = oauth.fetch_request_token("https://api.twitter.com/oauth/request_token")
    
    user_sessions[user_id] = {
        "oauth_token": request_token_response.get("oauth_token"),
        "oauth_token_secret": request_token_response.get("oauth_token_secret")
    }

    auth_url = oauth.authorization_url("https://api.twitter.com/oauth/authorize")
    await update.message.reply_text(f"برای ادامه وارد لینک زیر شو و کد PIN رو برام بفرست:\n{auth_url}")

# مرحله سوم: گرفتن PIN و تکمیل اتصال
async def handle_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pin = update.message.text.strip()

    if user_id not in user_sessions:
        await update.message.reply_text("اول دستور /login رو بزن تا بتونم لاگینت رو شروع کنم.")
        return

    tokens = user_sessions[user_id]
    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=tokens["oauth_token"],
        resource_owner_secret=tokens["oauth_token_secret"]
    )

    try:
        access_token_response = oauth.fetch_access_token("https://api.twitter.com/oauth/access_token", verifier=pin)
        oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=access_token_response.get("oauth_token"),
            resource_owner_secret=access_token_response.get("oauth_token_secret")
        )
        
        # بلاک کردن لیست مشخص
        with open(BLOCK_LIST_FILE, "r") as f:
            usernames = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        success, failed = [], []
        for username in usernames:
            resp = oauth.post("https://api.twitter.com/1.1/blocks/create.json", params={"screen_name": username})
            if resp.status_code == 200:
                success.append(username)
            else:
                failed.append(username)

        await update.message.reply_text(f"✅ بلاک انجام شد. موفق: {len(success)} | ناموفق: {len(failed)}")
    
    except Exception as e:
        logging.exception("خطا در پردازش PIN:", exc_info=e)
        await update.message.reply_text("مشکلی پیش اومد. مطمئن شو کد PIN رو درست وارد کردی یا دوباره /login رو بزن.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pin))

    print("✅ Bot is running...")
    app.run_polling()
