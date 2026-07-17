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

# --- (၃) Rednote (Xiaohongshu) Extractor ဟောင်းကို ပြန်သုံးခြင်း ---
def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def get_real_url(short_url):
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
    
    note_id_match = re.search(r'/discovery/item/([a-f0-9]+)', real_url) or re.search(r'/android/([a-f0-9]+)', real_url)
    if not note_id_match:
        note_id_match = re.search(r'item/([a-f0-9A-Za-z]+)', real_url)
        
    if not note_id_match:
        return None
        
    note_id = note_id_match.group(1)
    logger.info(f"Extracting Note ID: {note_id}")

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
    }
    
    try:
        session = requests.Session()
        session.get("https://www.xiaohongshu.com/", headers=headers, timeout=5)
        response = session.get(real_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        state_data = None
        for script in soup.find_all("script"):
            if script.string:
                if "window.__INITIAL_STATE__" in script.string or "window.__INITIAL_SSR_STATE__" in script.string:
                    state_data = script.string
                    break
                    
        if state_data:
            json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', state_data) or \
                        re.search(r'window\.__INITIAL_SSR_STATE__\s*=\s*(\{.*?\});', state_data) or \
                        re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})', state_data)
                        
            if json_text:
                data_json = json_text.group(1)
                data_json = data_json.replace("undefined", "null")
                data = json.loads(data_json)
                
                note_dict = data.get("note", {}).get("noteDetailMap", {}) or data.get("note", {}).get("note", {})
                
                note_data = {}
                if note_id in note_dict:
                    note_data = note_dict[note_id].get("note", {})
                elif "note" in data:
                    note_data = data.get("note", {})
                else:
                    for key, val in note_dict.items():
                        if isinstance(val, dict) and "note" in val:
                            note_data = val.get("note", {})
                            break
                
                if note_data:
                    note_type = note_data.get("type", "")
                    
                    # ၁။ ဗီဒီယို ရနိုင်လျှင် (အရင်လို ပြန်ရအောင် အဓိကယူမည်)
                    if note_type == "video" or "video" in note_data:
                        video_info = note_data.get("video", {})
                        media_list = video_info.get("media", {}).get("stream", {}).get("h264", [])
                        if media_list:
                            video_url = media_list[0].get("masterUrl")
                            if video_url:
                                if video_url.startswith("//"):
                                    video_url = "https:" + video_url
                                return {"type": "video", "url": video_url}
                    
                    # ၂။ ပုံများ ဖြစ်ပါက (Logo မဟုတ်သော ပုံများကို စစ်ထုတ်မည်)
                    image_list = note_data.get("imageList", [])
                    if image_list:
                        urls = []
                        for img in image_list:
                            img_url = img.get("urlDefault") or img.get("url") or img.get("url_raw")
                            if img_url:
                                if img_url.startswith("//"):
                                    img_url = "https:" + img_url
                                
                                # LOGO ပုံစိစစ်ခြင်း Rule: URL ထဲမှာ logo ဆိုတဲ့ စာလုံးပါရင် သို့မဟုတ် Logo size ဖြစ်နေရင် ဖယ်ထုတ်ပစ်မည်
                                if "logo" not in img_url.lower() and "brand" not in img_url.lower() and "sns-avatar" not in img_url.lower():
                                    urls.append(img_url)
                        
                        if urls:
                            return {"type": "images", "urls": urls}

        # Fallback Parse: meta tag ကနေ ယူရင်လည်း Logo ပုံကြီး ဖြစ်နေပါက လုံးဝ ဖယ်ထုတ်ပစ်မည်
        image_meta = soup.find("meta", property="og:image")
        if image_meta and image_meta.get("content"):
            img_url = image_meta["content"]
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            
            # အကယ်၍ logo ပုံကြီး ဖြစ်နေပါက user ဆီ မပို့ဘဲ ကျော်သွားရန်
            if "logo" not in img_url.lower() and "brand" not in img_url.lower() and "xhs" not in img_url.lower():
                return {"type": "images", "urls": [img_url]}
            
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
    return None

# --- (၄) Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "မင်္ဂလာပါ! NyiNyi + K 's OASIS လေးက ကြိုဆိုပါတယ်ဗျာ။\n\n"
        "Rednote (Xiaohongshu) link ပို့ပေးရင် ဗီဒီယို သို့မဟုတ် ပုံများကို ပြန်လည်ဒေါင်းလုဒ်ဆွဲပေးပါမည်။"
    )
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
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ ဗီဒီယိုနှင့် ပုံများကို ပြန်လည်ရှာဖွေနေပါတယ်...")
        media = extract_rednote_media(rednote_url)
        
        if media:
            try:
                # ဗီဒီယို ပို့ခြင်း
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="ဒေါင်းလုဒ်လုပ်ပြီးပါပြီ!")
                
                # ပုံများ ပို့ခြင်း
                elif media["type"] == "images":
                    img_urls = media["urls"]
                    if len(img_urls) == 1:
                        await update.message.reply_photo(photo=img_urls[0], caption="ဒေါင်းလုဒ်လုပ်ပြီးပါပြီ!")
                    else:
                        media_group = [InputMediaPhoto(media=img_url) for img_url in img_urls[:10]]
                        await update.message.reply_media_group(media=media_group)
                
                await waiting_msg.delete()
            except Exception as e:
                await waiting_msg.edit_text("မီဒီယာကို ဒေါင်းလုဒ်ဆွဲနိုင်ခဲ့သော်လည်း Telegram ပေါ်သို့ တင်ပေးရန် အဆင်မပြေဖြစ်သွားသည်။")
                logger.error(f"Sending error: {e}")
        else:
            # ဒီနေရာမှာ Logo ပုံကြီးပဲ မိသွားရင်လည်း error အနေနဲ့ပဲ ပြပစ်လိုက်မှာ ဖြစ်ပြီး Logo ပုံကြီး ပို့မှာ မဟုတ်တော့ပါ
            await waiting_msg.edit_text("စိတ်မရှိပါနဲ့၊ မီဒီယာအစစ်အမှန်ကို ဆွဲထုတ်လို့မရပါဘူးခင်ဗျာ။ (ပိတ်ဆို့ခံထားရခြင်း သို့မဟုတ် post မရှိခြင်း ဖြစ်နိုင်သည်)")
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
