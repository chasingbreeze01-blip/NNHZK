import os
import logging
import asyncio
import requests
import json
import re
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
from telegram import Update, InputMediaPhoto
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
    # စာသားအရှည်ကြီးတွေပြန်မပေးဘဲ cron-job ကောင်းကောင်းသိအောင် ok တလုံးတည်းပဲ ပြန်ခိုင်းထားပါတယ်
    return "ok"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- (၃) Scraper စနစ် ---
def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def get_real_url(short_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(short_url, headers=headers, allow_redirects=True, timeout=10)
        return response.url
    except Exception as e:
        logger.error(f"Error resolving short URL: {e}")
        return short_url

def extract_rednote_media(url):
    try:
        real_url = get_real_url(url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(real_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        state_data = None
        for script in soup.find_all("script"):
            if script.string and "window.__INITIAL_STATE__" in script.string:
                state_data = script.string
                break
                
        if state_data:
            json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})', state_data)
            if not json_text:
                json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', state_data)
                
            if json_text:
                data_json = json_text.group(1).replace("undefined", "null")
                data = json.loads(data_json)
                
                note_dict = data.get("note", {}).get("noteDetailMap", {})
                if not note_dict:
                    return None
                    
                note_id = list(note_dict.keys())[0]
                note_data = note_dict[note_id].get("note", {})
                if not note_data:
                    return None
                    
                note_type = note_data.get("type")
                
                # ဗီဒီယိုဆွဲထုတ်ခြင်း
                if note_type == "video":
                    video_info = note_data.get("video", {})
                    media_list = video_info.get("media", {}).get("stream", {}).get("h264", [])
                    if media_list and media_list[0].get("masterUrl"):
                        video_url = media_list[0].get("masterUrl")
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url
                        return {"type": "video", "url": video_url}
                            
                # ပုံများဆွဲထုတ်ခြင်း
                image_list = note_data.get("imageList", [])
                if image_list:
                    urls = []
                    for img in image_list:
                        img_url = img.get("urlDefault") or img.get("url")
                        if img_url:
                            if img_url.startswith("//"):
                                img_url = "https:" + img_url
                            urls.append(img_url)
                    if urls:
                        return {"type": "images", "urls": urls}
                        
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
    return None

# --- (၄) Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ ✌️ NyiNyi + K 's OASIS 🍀🌎 လေးက ကြိုဆိုပါတယ်ဗျာ💕")

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
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ ဗီဒီယိုနှင့် မီဒီယာများကို ဒေါင်းလုဒ်လုပ်နေပါတယ်...")
        try:
            media = extract_rednote_media(rednote_url)
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
                await waiting_msg.edit_text("ဒေတာရှာမတွေ့ပါဘူးဗျာ 🥺 လင့်ခ်မှားနေတာ ဖြစ်နိုင်ပါတယ်။")
        except Exception as e:
            logger.error(f"Handler error: {e}")
            await waiting_msg.edit_text("လုပ်ဆောင်ချက် မှားယွင်းသွားပါသည်။")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး Rednote လင့်ခ် ပို့ပေးပါ။")

# --- (၅) Main Async Runner (အိပ်မပျော်အောင် ကိုယ့်ဘာသာနှိုးမည့်စနစ်) ---
async def keep_alive():
    """ဆာဗာကို ကိုယ့်ဘာသာကိုယ် ၁၂ မိနစ်တိုင်း လှမ်းခေါ်ပြီး အိပ်မပျော်အောင် အလိုအလျောက်တားဆီးမည့်စနစ်"""
    await asyncio.sleep(15)
    while True:
        try:
            # မင်းရဲ့ Render URL ဆီကို စာပို့ပြီး အမြဲနိုးနေအောင် လုပ်ခြင်း
            requests.get("https://nnhzk.onrender.com/", timeout=5)
            logger.info("Self-ping successful. Server is awake!")
        except Exception as e:
            logger.error(f"Self-ping error: {e}")
        await asyncio.sleep(720) # ၁၂ မိနစ်တိုင်း (၇၂၀ စက္ကန့်) တစ်ခေါက် နှိုးမည်

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
        print("Bot is running with keep-alive system...")
        await bot_app.updater.start_polling()
        
        # အိပ်မပျော်စေမည့်စနစ်ကိုပါ တပြိုင်တည်း Run ခိုင်းထားခြင်း
        await keep_alive()

if __name__ == '__main__':
    asyncio.run(main())
