import os
import logging
import asyncio
import requests
import re
from flask import Flask
from threading import Thread
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = '8754460428:AAFGxRB1B4-DuL-QXxgd4fWWh0okPiznGhM'

app = Flask('')

@app.route('/')
def home():
    return "ok"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

# Cobalt Public API သုံးပြီး Rednote Block ကို ကျော်ဖြတ်ခြင်း
def extract_via_cobalt(url):
    try:
        api_url = "https://api.cobalt.tools/api/json"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "filenamePattern": "basic"
        }
        
        res = requests.post(api_url, json=payload, headers=headers, timeout=15)
        data = res.json()
        
        if data.get("status") == "stream" or data.get("status") == "redirect":
            return {"type": "video", "url": data.get("url")}
        elif data.get("status") == "picker":
            picker_items = data.get("picker", [])
            urls = [item.get("url") for item in picker_items if item.get("type") == "photo" or item.get("url")]
            if urls:
                return {"type": "images", "urls": urls}
    except Exception as e:
        logger.error(f"Cobalt API error: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! Rednote လင့်ခ် ပို့ပေးရင် ဗီဒီယို သို့မဟုတ် ပုံများကို ဒေါင်းလုဒ်လုပ်ပေးပါမယ်ဗျာ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    urls = re.findall(r'(https?://[^\s]+)', text)
    rednote_url = None
    for url in urls:
        if is_rednote_link(url):
            rednote_url = url
            break

    if rednote_url:
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ မီဒီယာများကို ဒေါင်းလုဒ်လုပ်နေပါတယ်...")
        try:
            media = extract_via_cobalt(rednote_url)
            if media:
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="Here is your video!")
                elif media["type"] == "images":
                    if len(media["urls"]) == 1:
                        await update.message.reply_photo(photo=media["urls"][0], caption="Here is your image!")
                    else:
                        media_group = [InputMediaPhoto(media=img_url) for img_url in media["urls"][:10]]
                        await update.message.reply_media_group(media=media_group)
                await waiting_msg.delete()
            else:
                await waiting_msg.edit_text("ဒေတာရှာမတွေ့ပါဘူးဗျာ 🥺 လင့်ခ်အပြည့်အစုံ (Direct Link) ကို ပြောင်းပို့ကြည့်ပေးပါနော်။")
        except Exception as e:
            logger.error(f"Handler error: {e}")
            await waiting_msg.edit_text("လုပ်ဆောင်ချက် မှားယွင်းသွားပါသည်။")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး Rednote လင့်ခ် ပို့ပေးပါ။")

async def keep_alive():
    await asyncio.sleep(15)
    while True:
        try:
            requests.get("https://nnhzk.onrender.com/", timeout=5)
            logger.info("Self-ping successful.")
        except Exception as e:
            logger.error(f"Self-ping error: {e}")
        await asyncio.sleep(720)

async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        print("Bot is running...")
        await bot_app.updater.start_polling()
        await keep_alive()

if __name__ == '__main__':
    asyncio.run(main())
