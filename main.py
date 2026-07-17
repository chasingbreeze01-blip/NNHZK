import os
import logging
import asyncio
import requests
import json
import re
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
from telegram import Update, InputMediaPhoto, InputMediaVideo
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

# --- (၃) Rednote (Xiaohongshu) Media Extractor ---
def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def get_real_url(short_url):
    """ တိုတိုလေးပေးထားတဲ့ xhslink.com ကို မူရင်းလင့်ခ်အရှည်ကြီးဖြစ်အောင် ပြောင်းပေးခြင်း """
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    }
    try:
        response = requests.get(short_url, headers=headers, allow_redirects=True, timeout=10)
        return response.url
    except Exception as e:
        logger.error(f"Error resolving short URL: {e}")
        return short_url

def extract_rednote_media(url):
    # ၁။ လင့်ခ်အစစ်အမှန်ကို အရင်ပြောင်းယူမယ်
    real_url = get_real_url(url)
    
    # URL ထဲကနေ Note ID ကို ရှာဖွေမယ်
    note_id_match = re.search(r'/discovery/item/([a-f0-9]+)', real_url) or re.search(r'/android/([a-f0-9]+)', real_url)
    if not note_id_match:
        # နောက်ထပ် ID ရှာဖွေနည်းလမ်းတစ်ခု
        note_id_match = re.search(r'item/([a-f0-9A-Za-z]+)', real_url)
        
    if not note_id_match:
        return None
        
    note_id = note_id_match.group(1)
    logger.info(f"Extracting Note ID: {note_id}")

    # Rednote ရဲ့ API လိပ်စာဆီ တိုက်ရိုက်ခေါ်ယူခြင်း
    api_url = f"https://www.xiaohongshu.com/fe_api/burdock/v2/note/{note_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            note_data = data.get("data", {})
            if note_data:
                note_type = note_data.get("type", "")
                
                # ၁။ ဗီဒီယို သီးသန့် ဖြစ်ခဲ့ရင်
                if note_type == "video":
                    video_url = note_data.get("video", {}).get("url", "")
                    if video_url:
                        return {"type": "video", "url": video_url}
                
                # ၂။ Live Photo သို့မဟုတ် ပုံများ ဖြစ်ခဲ့ရင်
                images_list = note_data.get("images", [])
                if images_list:
                    img_urls = []
                    for img in images_list:
                        # Watermark မပါတဲ့ မူရင်းပုံလင့်ခ်ကို ရယူခြင်း
                        img_url = img.get("url_raw") or img.get("url")
                        if img_url:
                            # http သို့မဟုတ် https ပါအောင် စစ်ဆေးခြင်း
                            if img_url.startswith("//"):
                                img_url = "https:" + img_url
                            img_urls.append(img_url)
                    
                    # Live Photo ဖြစ်ပါက (Live Video ဖိုင်ပါ ပါဝင်နေလျှင်)
                    video_info = note_data.get("video", {})
                    live_video_url = video_info.get("url", "") if video_info else ""
                    if live_video_url:
                        if live_video_url.startswith("//"):
                            live_video_url = "https:" + live_video_url
                        return {"type": "live_photo", "images": img_urls, "video": live_video_url}
                        
                    return {"type": "images", "urls": img_urls}
        
        # API အဆင်မပြေရင် နောက်ထပ် API တစ်ခုနဲ့ ထပ်စမ်းမယ်
        alternative_api = f"https://sns-api.xiaohongshu.com/api/sns/v1/note/feed"
        # ဤနေရာတွင် Fallback HTML parsing ကို ဆက်လက်အသုံးပြုသည်
        headers_html = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res_html = requests.get(real_url, headers=headers_html, timeout=10)
        soup = BeautifulSoup(res_html.text, 'html.parser')
        
        # HTML meta tags ကနေ ပြန်ရှာခြင်း
        video_meta = soup.find("meta", property="og:video")
        if video_meta and video_meta.get("content"):
            return {"type": "video", "url": video_meta["content"]}
            
        image_meta = soup.find("meta", property="og:image")
        if image_meta and image_meta.get("content"):
            img_url = image_meta["content"]
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            return {"type": "images", "urls": [img_url]}
            
    except Exception as e:
        logger.error(f"Extraction error details: {e}")
    return None

# --- (၄) Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "မင်္ဂလာပါ! NyiNyi + K 's OASIS လေးက ကြိုဆိုပါတယ်ဗျာ။\n\n"
        "Rednote (Xiaohongshu) link ပို့ပေးရင် watermark မပါတဲ့ ပုံ၊ ဗီဒီယို သို့မဟုတ် Live Photo တွေကို အကုန်ဒေါင်းပေးပါမယ်။"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    # စာသားထဲကနေ လင့်ခ်ကို ရှာဖွေခြင်း
    urls = re.findall(r'(https?://[^\s]+)', text)
    rednote_url = None
    for url in urls:
        if is_rednote_link(url):
            rednote_url = url
            break

    if rednote_url:
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ မီဒီယာများကို ရှာဖွေဒေါင်းလုဒ်လုပ်နေပါတယ်...")
        media = extract_rednote_media(rednote_url)
        
        if media:
            try:
                # ၁။ ဗီဒီယို ဖြစ်လျှင်
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="Here is your video!")
                
                # ၂။ ပုံအများကြီး (Slide) သို့မဟုတ် ပုံတစ်ပုံတည်း ဖြစ်လျှင်
                elif media["type"] == "images":
                    img_urls = media["urls"]
                    if len(img_urls) == 1:
                        await update.message.reply_photo(photo=img_urls[0], caption="Here is your image!")
                    else:
                        # Telegram ကန့်သတ်ချက်အရ Album အလိုက် စုစည်းပို့ပေးခြင်း
                        media_group = [InputMediaPhoto(media=img_url) for img_url in img_urls[:10]]
                        await update.message.reply_media_group(media=media_group)
                
                # ၃။ Live Photo ဖြစ်လျှင် (ပုံရော၊ လှုပ်ရှားတဲ့ ဗီဒီယိုပါ တွဲပို့ပေးခြင်း)
                elif media["type"] == "live_photo":
                    img_urls = media["images"]
                    video_url = media["video"]
                    
                    if img_urls and video_url:
                        # ပုံရော ဗီဒီယိုပါ Album တစ်ခုတည်းအဖြစ် ပေါင်းပြီး တစ်ခါတည်း ပို့ပေးခြင်း
                        media_group = [
                            InputMediaPhoto(media=img_urls[0], caption="Live Photo (Static & Video)"),
                            InputMediaVideo(media=video_url)
                        ]
                        await update.message.reply_media_group(media=media_group)
                    elif img_urls:
                        await update.message.reply_photo(photo=img_urls[0], caption="Live Photo (Image Only)")

                await waiting_msg.delete()
            except Exception as e:
                await waiting_msg.edit_text("မီဒီယာကို ဆွဲထုတ်ရရှိသော်လည်း Telegram ဆီ ပို့လွှတ်မှု အဆင်မပြေဖြစ်သွားပါတယ်။")
                logger.error(f"Sending error: {e}")
        else:
            await waiting_msg.edit_text("စိတ်မရှိပါနဲ့၊ မီဒီယာကို ဆွဲထုတ်လို့ မရပါဘူးခင်ဗျာ။ လင့်ခ်မှားနေတာ (သို့မဟုတ်) Post ဖျက်လိုက်တာ ဖြစ်နိုင်ပါတယ်။")
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
