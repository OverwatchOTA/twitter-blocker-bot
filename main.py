import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, CONSUMER_KEY, CONSUMER_SECRET
from requests_oauthlib import OAuth1Session

BLOCK_LIST_FILE = "block_list.txt"

# لاگ‌گیری فعال
logging.basicConfig(level=logging.INFO)
user_sessions = {}

# ✅ مرحله 1: شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! برای بلاک‌کردن لیست، اول باید وارد توییتر بشی. لطفاً دستور /login رو بزن.")

# ✅ مرحله 2: دریافت لینک لاگین و ذخیره session
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri='oob')
    request_token_response = oauth.fetch_request_token("https://api.twitter.com/oauth/request_token")

    user_sessions[user_id] = {
        "oauth_token": request_token_response.get("oauth_token"),
        "oauth_token_secret": request_token_response.get("oauth_token_secret")
    }

    auth_url = oauth.authorization_url("https://api.twitter.com/oauth/authorize")
    await update.message.reply_text(f"✅ وارد لینک زیر شو و PIN رو بفرست:\n{auth_url}")

# ✅ مرحله 3: دریافت PIN و بلاک‌کردن لیست
async def handle_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pin = update.message.text.strip()

    if user_id not in user_sessions:
        await update.message.reply_text("⛔️ لطفاً اول دستور /login رو بزن.")
        return

    tokens = user_sessions[user_id]
    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=tokens["oauth_token"],
        resource_owner_secret=tokens["oauth_token_secret"]
    )

    try:
        access_token_response = oauth.fetch_access_token(
            "https://api.twitter.com/oauth/access_token", verifier=pin
        )
        oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=access_token_response.get("oauth_token"),
            resource_owner_secret=access_token_response.get("oauth_token_secret")
        )

        with open(BLOCK_LIST_FILE, "r") as f:
            usernames = [line.strip().lstrip("@") for line in f if line.strip() and not line.startswith("#")]

        success, failed = [], []
        for username in usernames:
            resp = oauth.post(
                "https://api.twitter.com/1.1/blocks/create.json",
                params={"screen_name": username}
            )
            logging.info(f"Blocking @{username} → Status: {resp.status_code}")
            if resp.status_code == 200:
                success.append(username)
            else:
                failed.append(username)
                logging.warning(f"❌ Failed to block @{username}: {resp.text}")

        message = f"✅ عملیات بلاک کامل شد:\n🟢 موفق: {len(success)} نفر\n🔴 ناموفق: {len(failed)} نفر"
        if failed:
            message += "\n\n❌ کاربرانی که بلاک نشدن:\n" + "\n".join(failed)
        await update.message.reply_text(message)

    except Exception as e:
        logging.exception("❌ خطا در پردازش PIN:")
        await update.message.reply_text("مشکلی پیش اومد. مطمئن شو PIN رو درست وارد کردی یا دوباره /login رو بزن.")

# ✅ اجرای بات
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pin))

    print("✅ Bot is running...")
    app.run_polling()
