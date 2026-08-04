import os
import re
import logging
import requests
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = '8754460428:AAFGxRB1B4-DuL-QXxgd4fWWh0okPiznGhM'

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ ✌️ NyiNyi + K 's OASIS 🍀🌎 လေးက ကြိုဆိုပါတယ်ဗျာ💕")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    urls = re.findall(r'(https?://[^\s]+)', text)
    rednote_url = next((url for url in urls if is_rednote_link(url)), None)

    if rednote_url:
        waiting_msg = await update.message.reply_text("ခဏလေးစောင့်ပေးပါနော် ⏳ media ကိုရှာဖွေနေပါတယ်❤️...")
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
                await waiting_msg.edit_text("midea ကို ရှာမတွေ့ပါဘူးဗျ 🥺 link မှားနေတာဖြစ်နိုင်ပါတယ်။")
        except Exception as e:
            logger.error(f"Handler error: {e}")
            await waiting_msg.edit_text("စိတ်မရှိပါနဲ့၊ မီဒီယာကို ဆွဲထုတ်လို့ မရပါဘူးခင်ဗျာ 🥺 ")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး မှန်ကန်တဲ့ Rednote link တစ်ခုကို ပို့ပေးပါနော် 🫶🏻")

# Vercel Webhook Handler
async def process_update(request_json):
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await application.initialize()
    update = Update.de_json(request_json, application.bot)
    await application.process_update(update)

def handler(request):
    import json
    if request.method == "POST":
        request_json = json.loads(request.body)
        asyncio.run(process_update(request_json))
        return "OK", 200
    return "Bot is alive", 200
