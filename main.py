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
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- (၃) Rednote Media Extractor ---
def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def extract_rednote_media(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    try:
        # Redirect လင့်ခ်အစစ်အမှန်ကို ရှာဖွေခြင်း
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Rednote ရဲ့ internal State data ကို ရှာဖွေခြင်း (ပုံနှင့် ဗီဒီယိုဒေတာ အစစ်အမှန်များ ဤနေရာတွင် ရှိသည်)
        state_script = None
        for script in soup.find_all("script"):
            if script.string and "window.__INITIAL_STATE__" in script.string:
                state_script = script.string
                break
                
        if state_script:
            # JSON ဒေတာကို ခွဲထုတ်ခြင်း
            json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', state_script)
            if json_text:
                data = json.loads(json_text.group(1))
                note_id = data.get("note", {}).get("currentNoteId")
                note_data = data.get("note", {}).get("noteDetailMap", {}).get(note_id, {}).get("note", {})
                
                if note_data:
                    note_type = note_data.get("type") # video သို့မဟုတ် normal (photo)
                    
                    # ကေတီဂိုရီ ၁ - ဗီဒီယို ဖြစ်ပါက
                    if note_type == "video":
                        video_info = note_data.get("video", {})
                        media_list = video_info.get("media", {}).get("stream", {}).get("h264", [])
                        if media_list:
                            # Quality အမြင့်ဆုံး ဗီဒီယိုလင့်ခ်ကို ယူခြင်း
                            video_url = media_list[0].get("masterUrl")
                            return {"type": "video", "url": video_url}
                    
                    # ကေတီဂိုရီ ၂ - Live Photo သို့မဟုတ် ပုံများ ဖြစ်ပါက
                    image_list = note_data.get("imageList", [])
                    if image_list:
                        urls = []
                        for img in image_list:
                            # Watermark မပါတဲ့ ပုံလင့်ခ်ကို ရယူခြင်း
                            img_url = img.get("urlDefault") or img.get("url")
                            if img_url:
                                urls.append(img_url)
                        
                        # Live Photo ဖြစ်နေလျှင် (Live Photo ဗီဒီယိုဖိုင် ပါဝင်ပါက)
                        video_info = note_data.get("video", {})
                        live_photo_video = None
                        if video_info:
                            media_list = video_info.get("media", {}).get("stream", {}).get("h264", [])
                            if media_list:
                                live_photo_video = media_list[0].get("masterUrl")
                        
                        if live_photo_video:
                            return {"type": "live_photo", "images": urls, "video": live_photo_video}
                        
                        return {"type": "images", "urls": urls}

        # Fallback စနစ် (HTML ကနေ ပြန်ရှာခြင်း)
        video_meta = soup.find("meta", property="og:video")
        if video_meta and video_meta.get("content"):
            return {"type": "video", "url": video_meta["content"]}
            
        image_meta = soup.find("meta", property="og:image")
        if image_meta and image_meta.get("content"):
            return {"type": "images", "urls": [image_meta["content"]]}
            
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
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

    # စာထဲတွင် Rednote လင့်ခ် ပါမပါ စစ်ဆေးခြင်း
    urls = re.findall(r'(https?://[^\s]+)', text)
    rednote_url = None
    for url in urls:
        if is_rednote_link(url):
            rednote_url = url
            break

    if rednote_url:
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ ပုံနှင့် ဗီဒီယိုများကို ဆွဲထုတ်နေပါတယ်...")
        media = extract_rednote_media(rednote_url)
        
        if media:
            try:
                # ၁။ ဗီဒီယို သီးသန့် ဖြစ်လျှင်
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="Here is your video!")
                
                # ၂။ ပုံတစ်ပုံတည်း သို့မဟုတ် အများကြီး (Slide) ဖြစ်လျှင်
                elif media["type"] == "images":
                    img_urls = media["urls"]
                    if len(img_urls) == 1:
                        await update.message.reply_photo(photo=img_urls[0], caption="Here is your image!")
                    else:
                        # ပုံအများကြီးကို Album အလိုက် စုပြီး ပို့ပေးခြင်း
                        media_group = [InputMediaPhoto(media=img_url) for img_url in img_urls[:10]] # အများဆုံး ၁၀ ပုံစီ ဖြတ်ပို့မယ်
                        await update.message.reply_media_group(media=media_group)
                
                # ၃။ Live Photo ဖြစ်လျှင် (ပုံရော ဗီဒီယိုပါ တွဲပို့ပေးခြင်း)
                elif media["type"] == "live_photo":
                    # ပုံရိပ်ပြားများ ပို့ခြင်း
                    if media["images"]:
                        await update.message.reply_photo(photo=media["images"][0], caption="Live Photo (Static Image)")
                    # နောက်ကွယ်က Live video ပို့ခြင်း
                    await update.message.reply_video(video=media["video"], caption="Live Photo (Video Part)")

                await waiting_msg.delete()
            except Exception as e:
                await waiting_msg.edit_text("မီဒီယာကို ဒေါင်းလို့ရပေမယ့် Telegram ဆီကို ပို့တဲ့နေရာမှာ error တက်သွားပါတယ်ခင်ဗျာ။")
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
        print("Bot is starting up successfully with Flask helper on Render...")
        await bot_app.updater.start_polling()
        
        while True:
            await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
