import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, CONSUMER_KEY, CONSUMER_SECRET
from requests_oauthlib import OAuth1Session

BLOCK_LIST_FILE = "block_list.txt"
logging.basicConfig(level=logging.INFO)
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! برای بلاک‌کردن لیست، اول باید وارد توییتر بشی. لطفاً دستور /login رو بزن.")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri='oob')
    request_token_response = oauth.fetch_request_token("https://api.twitter.com/oauth/request_token")

    user_sessions[user_id] = {
        "oauth_token": request_token_response.get("oauth_token"),
        "oauth_token_secret": request_token_response.get("oauth_token_secret")
    }

    auth_url = oauth.authorization_url("https://api.twitter.com/oauth/authorize")
    await update.message.reply_text(f"وارد لینک شو و کد PIN رو بفرست:\n{auth_url}")

async def handle_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pin = update.message.text.strip()

    if user_id not in user_sessions:
        await update.message.reply_text("لطفاً اول /login رو بزن.")
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

        with open(BLOCK_LIST_FILE, "r") as f:
            usernames = [line.strip().lstrip("@") for line in f if line.strip() and not line.startswith("#")]

        count = 0
        for username in usernames:
            resp = oauth.post(
                "https://api.twitter.com/1.1/blocks/create.json",
                params={"screen_name": username}
            )
            if resp.status_code == 200:
                count += 1
            else:
                logging.warning(f"❌ خطا در بلاک {username} → {resp.status_code} - {resp.text}")

        await update.message.reply_text(f"✅ عملیات بلاک انجام شد.\nتعداد بلاک موفق: {count}")

    except Exception as e:
        logging.exception("❌ خطا در پردازش PIN:", exc_info=e)
        await update.message.reply_text("مشکلی پیش اومد. دوباره /login رو بزن یا کد رو چک کن.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pin))

    print("✅ Bot is running...")
    app.run_polling()
