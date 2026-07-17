import os
import logging
import asyncio
import requests
import json
import re
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

# --- (၃) ဗီဒီယိုပြန်ရစေမယ့် HTML Scraper စနစ်စစ်စစ် ---
def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def get_real_url(short_url):
    # မူရင်း အလုပ်လုပ်ခဲ့သော သာမန် Header သို့ ပြန်ပြောင်းခြင်း
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
    real_url = get_real_url(url)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        response = requests.get(real_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        state_data = None
        for script in soup.find_all("script"):
            if script.string and "window.__INITIAL_STATE__" in script.string:
                state_data = script.string
                break
                
        if state_data:
            # JavaScript Object မှ JSON သို့ ပြောင်းလဲခြင်း
            json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})', state_data)
            if not json_text:
                json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', state_data)
                
            if json_text:
                data_json = json_text.group(1)
                data_json = data_json.replace("undefined", "null")
                data = json.loads(data_json)
                
                # Note details ကို ဆွဲထုတ်ခြင်း
                note_dict = data.get("note", {}).get("noteDetailMap", {})
                if note_dict:
                    note_id = list(note_dict.keys())[0]
                    note_data = note_dict[note_id].get("note", {})
                    
                    note_type = note_data.get("type")
                    
                    # အရင်အတိုင်း ဗီဒီယိုရစေရန် (Video Direct Link Extraction)
                    if note_type == "video":
                        video_info = note_data.get("video", {})
                        media_list = video_info.get("media", {}).get("stream", {}).get("h264", [])
                        if media_list:
                            video_url = media_list[0].get("masterUrl")
                            if video_url:
                                if video_url.startswith("//"):
                                    video_url = "https:" + video_url
                                return {"type": "video", "url": video_url}
                                
                    # အကယ်၍ ပုံသက်သက်ဖြစ်ပါက (Logo မဟုတ်သော ပုံများကိုသာ ယူမည်)
                    image_list = note_data.get("imageList", [])
                    if image_list:
                        urls = []
                        for img in image_list:
                            img_url = img.get("urlDefault") or img.get("url")
                            if img_url:
                                if img_url.startswith("//"):
                                    img_url = "https:" + img_url
                                # Rednote Logo မဟုတ်သော ပုံစစ်စစ်များကိုသာ ယူရန်
                                if "logo" not in img_url.lower() and "brand" not in img_url.lower():
                                    urls.append(img_url)
                        if urls:
                            return {"type": "images", "urls": urls}
                            
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
    return None

# --- (၄) Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "မင်္ဂလာပါ! Rednote လင့်ခ် ပို့ပေးရင် ဗီဒီယို သို့မဟုတ် ပုံများကို ရှာဖွေဒေါင်းလုဒ်လုပ်ပေးပါမယ်ဗျာ။"
    await update.message.reply_text(welcome_text)

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
        media = extract_rednote_media(rednote_url)
        
        if media:
            try:
                # ၁။ ဗီဒီယို ပြန်လည်ပို့ပေးခြင်း
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="Here is your video!")
                
                # ၂။ ပုံများကို ပို့ပေးခြင်း (Logo မဟုတ်လျှင်)
                elif media["type"] == "images":
                    await update.message.reply_photo(photo=media["urls"][0], caption="Here is your image!")
                
                await waiting_msg.delete()
            except Exception as e:
                await waiting_msg.edit_text("မီဒီယာကို ဒေါင်းလုဒ်ဆွဲနိုင်ခဲ့သော်လည်း Telegram ဆီ တင်ပေးရန် အဆင်မပြေဖြစ်သွားသည်။")
                logger.error(f"Sending error: {e}")
        else:
            await waiting_msg.edit_text("စိတ်မရှိပါနဲ့၊ မီဒီယာကို ဆွဲထုတ်လို့မရပါဘူးခင်ဗျာ။ လင့်ခ်မှားနေတာ ဖြစ်နိုင်ပါတယ်။")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး မှန်ကန်တဲ့ Rednote (Xiaohongshu) link တစ်ခုကို ပို့ပေးပါနော်။")

# --- (၅) Main Async Runner ---
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
        print("Bot is starting up successfully on Render...")
        await bot_app.updater.start_polling()
        
        while True:
            await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
