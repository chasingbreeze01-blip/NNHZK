import os
import logging
import asyncio
import requests
import json
import re
import hashlib
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

# --- Telegram Bot Token ---
TOKEN = '8754460428:AAFGxRB1B4-DuL-QXxgd4fWWh0okPiznGhM'

# --- Flask Web Server ---
app = Flask('')

@app.route('/')
def home():
    return "ok"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Rednote API Extractor (Advanced Signature Engine) ---
def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def get_real_url(short_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    }
    try:
        session = requests.Session()
        res = session.get(short_url, headers=headers, allow_redirects=True, timeout=12)
        return res.url
    except Exception as e:
        logger.error(f"Error resolving URL: {e}")
        return short_url

def extract_rednote_media(url):
    try:
        real_url = get_real_url(url)
        
        # URL ထဲက Note ID ကို ရှာထုတ်ခြင်း
        note_id = None
        match = re.search(r'explore/([a-zA-Z0-9]+)', real_url)
        if not match:
            match = re.search(r'discovery/item/([a-zA-Z0-9]+)', real_url)
            
        if match:
            note_id = match.group(1)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.xiaohongshu.com/"
        }

        # ၁။ တိုက်ရိုက် Page Data မှ ဆွဲထုတ်ခြင်း
        res = requests.get(real_url, headers=headers, timeout=12)
        soup = BeautifulSoup(res.text, 'html.parser')

        state_data = None
        for script in soup.find_all("script"):
            if script.string and "window.__INITIAL_STATE__" in script.string:
                state_data = script.string
                break

        if state_data:
            json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})', state_data)
            if json_text:
                data_json = json_text.group(1).replace("undefined", "null")
                data = json.loads(data_json)
                
                note_dict = data.get("note", {}).get("noteDetailMap", {})
                if note_dict:
                    if not note_id:
                        note_id = list(note_dict.keys())[0]
                    
                    note_data = note_dict.get(note_id, {}).get("note", {})
                    if note_data:
                        note_type = note_data.get("type")

                        # ဗီဒီယိုဖြစ်လျှင်
                        if note_type == "video":
                            video_info = note_data.get("video", {})
                            stream = video_info.get("media", {}).get("stream", {})
                            
                            video_url = None
                            for codec in ['h264', 'h265']:
                                media_list = stream.get(codec, [])
                                if media_list and media_list[0].get("masterUrl"):
                                    video_url = media_list[0].get("masterUrl")
                                    break
                            
                            if not video_url:
                                video_url = video_info.get("backupUrl") or video_info.get("url")

                            if video_url:
                                if video_url.startswith("//"):
                                    video_url = "https:" + video_url
                                return {"type": "video", "url": video_url}

                        # ပုံများဖြစ်လျှင်
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
        logger.error(f"Extraction error: {e}")
    return None

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! Rednote လင့်ခ် ပို့ပေးရင် ဗီဒီယို သို့မဟုတ် ပုံများကို HD မူရင်းအတိုင်း ဆွဲထုတ်ပေးပါမယ်ဗျာ။")

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
            media = extract_rednote_media(rednote_url)
            if media:
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="Here is your video!")
                elif media["type"] == "images":
                    if len(media["urls"]) == 1:
                        await update.message.reply_photo(photo=media["urls"][0], caption="Here is your image!")
                    else:
                        # ပုံ ၁၀ ပုံအထိ တစ်ပြိုင်နက် ပို့ပေးခြင်း
                        media_group = [InputMediaPhoto(media=img_url) for img_url in media["urls"][:10]]
                        await update.message.reply_media_group(media=media_group)
                await waiting_msg.delete()
            else:
                await waiting_msg.edit_text("ဒေတာရှာမတွေ့ပါဘူးဗျာ 🥺 လင့်ခ်အပြည့်အစုံကို ပြန်ပို့ကြည့်ပေးပါနော်။")
        except Exception as e:
            logger.error(f"Handler error: {e}")
            await waiting_msg.edit_text("လုပ်ဆောင်ချက် မှားယွင်းသွားပါသည်။")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး Rednote လင့်ခ် ပို့ပေးပါ။")

# --- Keep-Alive System ---
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
        print("Bot is running with Advanced API...")
        await bot_app.updater.start_polling()
        await keep_alive()

if __name__ == '__main__':
    asyncio.run(main())
