import os
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- (၁) Telegram Bot ရဲ့ Token ---
TOKEN = '8754460428:AAFGxRB1B4-DuL-QXxgd4fWWh0okPiznGhM'

# --- (၂) Flask Web Server ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- (၃) Bot Function များ ---
def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def extract_rednote_media(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, allow_redirects=True)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ဗီဒီယိုလင့်ခ် ရှာဖွေခြင်း
        video_meta = soup.find("meta", property="og:video")
        if video_meta and video_meta.get("content"):
            return {"type": "video", "url": video_meta["content"]}
            
        # ပုံလင့်ခ် ရှာဖွေခြင်း
        image_meta = soup.find("meta", property="og:image")
        if image_meta and image_meta.get("content"):
            return {"type": "image", "url": image_meta["content"]}
            
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
    return None

# --- (၄) Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "မင်္ဂလာပါ! NyiNyi + K 's OASIS လေးက ကြိုဆိုပါတယ်ဗျာ။\n\n"
        "Rednote (Xiaohongshu) link ပို့ပေးရင် watermark မပါတဲ့ video ပြန်ဒေါင်းပေးပါမယ်။"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    if is_rednote_link(text):
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ မီဒီယာကို ရှာဖွေနေပါတယ်...")
        media = extract_rednote_media(text)
        
        if media:
            try:
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="Here is your video!")
                elif media["type"] == "image":
                    await update.message.reply_photo(photo=media["url"], caption="Here is your image!")
                await waiting_msg.delete()
            except Exception as e:
                await waiting_msg.edit_text("မီဒီယာကို ပို့လို့မရဖြစ်နေပါတယ်။ လင့်ခ်မှားနေတာမျိုး ဖြစ်နိုင်ပါတယ်။")
                logger.error(f"Sending error: {e}")
        else:
            await waiting_msg.edit_text("စိတ်မရှိပါနဲ့၊ မီဒီယာကို ဆွဲထုတ်လို့ မရပါဘူးခင်ဗျာ။")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး မှန်ကန်တဲ့ Rednote (Xiaohongshu) link တစ်ခုကို ပို့ပေးပါနော်။")

# --- (၅) Main Async Runner ---
async def main():
    # Flask ကို Background thread မှာ တင်ထားမယ်
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Bot ကို တည်ဆောက်မယ်
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Bot ကို စနစ်တကျ Initialize လုပ်ပြီး Run မယ်
    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        print("Bot is starting up successfully with Flask helper on Render...")
        await bot_app.updater.start_polling()
        
        # Render ပိတ်မသွားအောင် loop အမြဲပတ်ထားမယ်
        while True:
            await asyncio.sleep(3600)

if __name__ == '__main__':
    # Asyncio loop ကို ပတ်မောင်းနှင်ခြင်း
    asyncio.run(main())
