import os
import re
import asyncio
import logging
import requests
from flask import Flask, request
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = '8754460428:AAFGxRB1B4-DuL-QXxgd4fWWh0okPiznGhM'

app = Flask(__name__)

def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def extract_via_cobalt(url):
    try:
        api_url = "https://api.cobalt.tools/api/json"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {"url": url, "filenamePattern": "basic"}
        
        res = requests.post(api_url, json=payload, headers=headers, timeout=15)
        data = res.json()
        
        if data.get("status") in ["stream", "redirect"]:
            return {"type": "video", "url": data.get("url")}
        elif data.get("status") == "picker":
            picker_items = data.get("picker", [])
            urls = [item.get("url") for item in picker_items if item.get("url")]
            if urls:
                return {"type": "images", "urls": urls}
    except Exception as e:
        logger.error(f"Cobalt error: {e}")
    return None

async def start(update: Update, context):
    await update.message.reply_text("မင်္ဂလာပါ! Rednote လင့်ခ် ပို့ပေးရင် မီဒီယာ ဒေါင်းလုဒ်လုပ်ပေးပါမယ်ဗျာ။")

async def handle_message(update: Update, context):
    text = update.message.text
    if not text:
        return

    urls = re.findall(r'(https?://[^\s]+)', text)
    rednote_url = next((url for url in urls if is_rednote_link(url)), None)

    if rednote_url:
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ မီဒီယာ ဒေါင်းလုဒ်လုပ်နေပါတယ်...")
        try:
            media = extract_via_cobalt(rednote_url)
            if media:
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="Here is your video!")
                elif media["type"] == "images":
                    if len(media["urls"]) == 1:
                        await update.message.reply_photo(photo=media["urls"][0], caption="Here is your image!")
                    else:
                        media_group = [InputMediaPhoto(media=u) for u in media["urls"][:10]]
                        await update.message.reply_media_group(media=media_group)
                await waiting_msg.delete()
            else:
                await waiting_msg.edit_text("ဒေတာရှာမတွေ့ပါဘူးဗျာ။")
        except Exception as e:
            logger.error(f"Handler error: {e}")
            await waiting_msg.edit_text("မှားယွင်းမှု ဖြစ်ပေါ်သွားပါသည်။")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး Rednote လင့်ခ် ပို့ပေးပါ။")

async def process_telegram_update(data):
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await application.initialize()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True)
        if data:
            asyncio.run(process_telegram_update(data))
        return 'OK', 200
    return 'Bot is active on Vercel!', 200
