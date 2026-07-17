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
    """ xhslink.com ကို မူရင်းလင့်ခ်အရှည်ကြီးဖြစ်အောင် ပြောင်းပေးခြင်း """
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9"
    }
    try:
        response = requests.get(short_url, headers=headers, allow_redirects=True, timeout=10)
        return response.url
    except Exception as e:
        logger.error(f"Error resolving short URL: {e}")
        return short_url

def extract_rednote_media(url):
    real_url = get_real_url(url)
    
    # URL ထဲကနေ Note ID ကို ရှာဖွေမယ်
    note_id_match = re.search(r'/discovery/item/([a-f0-9]+)', real_url) or re.search(r'/android/([a-f0-9]+)', real_url)
    if not note_id_match:
        note_id_match = re.search(r'item/([a-f0-9A-Za-z]+)', real_url)
        
    if not note_id_match:
        return None
        
    note_id = note_id_match.group(1)
    logger.info(f"Extracting Note ID: {note_id}")

    # Rednote ရဲ့ Web Page ကို လှမ်းခေါ်တဲ့အခါ Block မခံရအောင် Cookie ပါ တွဲယူခြင်း
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
    }
    
    try:
        # Web Page HTML ကို အရင်ဆွဲယူမယ်
        session = requests.Session()
        # Cookie ရရှိအောင် ပင်မစာမျက်နှာကို အရင်တစ်ချက်ခေါ်တယ်
        session.get("https://www.xiaohongshu.com/", headers=headers, timeout=5)
        
        # သက်ဆိုင်ရာ Post စာမျက်နှာကို ခေါ်ယူတယ်
        response = session.get(real_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # HTML ထဲက window.__INITIAL_STATE__ သို့မဟုတ် window.__INITIAL_SSR_STATE__ ကို ရှာဖွေခြင်း
        state_data = None
        for script in soup.find_all("script"):
            if script.string:
                if "window.__INITIAL_STATE__" in script.string or "window.__INITIAL_SSR_STATE__" in script.string:
                    state_data = script.string
                    break
                    
        if state_data:
            # JSON ဒေတာကို ခွဲထုတ်ခြင်း
            json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', state_data) or \
                        re.search(r'window\.__INITIAL_SSR_STATE__\s*=\s*(\{.*?\});', state_data) or \
                        re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})', state_data)
                        
            if json_text:
                data_json = json_text.group(1)
                # သာမန် String အဖြစ် ပြောင်းလဲထားသော JSON ကို decode ပြန်လုပ်ခြင်း
                data_json = data_json.replace("undefined", "null")
                data = json.loads(data_json)
                
                # Note Detail Map ကို ရှာဖွေခြင်း
                note_dict = data.get("note", {}).get("noteDetailMap", {}) or data.get("note", {}).get("note", {})
                
                # တိုက်ရိုက် note data မရလျှင် ID ဖြင့် ထပ်မံရှာဖွေခြင်း
                note_data = {}
                if note_id in note_dict:
                    note_data = note_dict[note_id].get("note", {})
                elif "note" in data:
                    note_data = data.get("note", {})
                else:
                    # အဆင့်မြင့် JSON ရှာဖွေနည်းဖြင့် Note object ကို တိုက်ရိုက်ဆွဲထုတ်ခြင်း
                    for key, val in note_dict.items():
                        if isinstance(val, dict) and "note" in val:
                            note_data = val.get("note", {})
                            break
                
                if note_data:
                    note_type = note_data.get("type", "")
                    
                    # ၁။ ဗီဒီယို သီးသန့် ဖြစ်ပါက
                    if note_type == "video":
                        video_info = note_data.get("video", {})
                        media_list = video_info.get("media", {}).get("stream", {}).get("h264", [])
                        if media_list:
                            video_url = media_list[0].get("masterUrl")
                            return {"type": "video", "url": video_url}
                    
                    # ၂။ Live Photo သို့မဟုတ် ပုံများ ဖြစ်ပါက
                    image_list = note_data.get("imageList", [])
                    if image_list:
                        urls = []
                        for img in image_list:
                            # Watermark မရှိသော URL ကို ဦးစားပေးရွေးချယ်ခြင်း
                            img_url = img.get("urlDefault") or img.get("url") or img.get("url_raw")
                            if img_url:
                                # // တည်းပါလာသော URL များကို https ဖြည့်ပေးခြင်း
                                if img_url.startswith("//"):
                                    img_url = "https:" + img_url
                                # Rednote Logo မဟုတ်သော ပုံစစ်စစ်များကိုသာ ယူရန် (Logo URL တွင် logo သို့မဟုတ် logo_brand ပါတတ်သည်)
                                if "logo" not in img_url.lower():
                                    urls.append(img_url)
                        
                        # Live Photo ဖြစ်နေလျှင် (Live Video ပါဝင်ပါက)
                        video_info = note_data.get("video", {})
                        live_photo_video = None
                        if video_info:
                            media_list = video_info.get("media", {}).get("stream", {}).get("h264", []) or video_info.get("media", {}).get("stream", {}).get("h265", [])
                            if media_list:
                                live_photo_video = media_list[0].get("masterUrl")
                                if live_photo_video and live_photo_video.startswith("//"):
                                    live_photo_video = "https:" + live_photo_video
                        
                        if live_photo_video and urls:
                            return {"type": "live_photo", "images": urls, "video": live_photo_video}
                        
                        if urls:
                            return {"type": "images", "urls": urls}

        # Fallback HTML Parse စနစ် (API fallback အဖြစ်သုံးသည်)
        # Rednote Logo ပုံကို ရှောင်ရှားပြီး meta tag မှ ပုံစစ်စစ်ကို ယူခြင်း
        image_meta = soup.find("meta", property="og:image")
        if image_meta and image_meta.get("content"):
            img_url = image_meta["content"]
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            if "logo" not in img_url.lower() and "小红书" not in response.text:
                return {"type": "images", "urls": [img_url]}
            
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
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ ပုံနှင့် ဗီဒီယိုများကို ရှာဖွေဆွဲထုတ်နေပါတယ်...")
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
                        media_group = [InputMediaPhoto(media=img_url) for img_url in img_urls[:10]]
                        await update.message.reply_media_group(media=media_group)
                
                # ၃။ Live Photo ဖြစ်လျှင် (ပုံရော ဗီဒီယိုပါ တွဲပို့ပေးခြင်း)
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
