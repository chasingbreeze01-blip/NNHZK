import os
import logging
import asyncio
import requests
import re
from flask import Flask
from threading import Thread
from telegram import Update, InputMediaPhoto, InputMediaVideo
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
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def extract_via_premium_api(url):
    """ SnapX ကဲ့သို့သော Website များ၏ အနောက်ကွယ်စနစ်ကို လှမ်းသုံးပြီး ဒေတာဆွဲယူခြင်း """
    try:
        extracted_url = re.search(r'(https?://[^\s]+)', url)
        if not extracted_url:
            return None
        target_url = extracted_url.group(1)

        # Bypass API (ဒေါင်းလုဒ် Website များသုံးသော ကြားခံဆာဗာ)
        api_url = "https://auto.gdlapi.com/api/v1/parse"
        payload = {"url": target_url}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("code") == 0:
                data = res_data.get("data", {})
                
                # ၁။ ဗီဒီယို ဖြစ်ပါက
                if data.get("videoUrl"):
                    return {"type": "video", "url": data.get("videoUrl")}
                
                # ၂။ ပုံများ ဖြစ်ပါက
                images = data.get("images", [])
                if images:
                    # Logo ပုံတွေ မဟုတ်တဲ့ ပုံစစ်စစ်တွေကိုပဲ စစ်ထုတ်ယူမယ်
                    clean_images = [img for img in images if "logo" not in img.lower()]
                    if clean_images:
                        return {"type": "images", "urls": clean_images}
                        
    except Exception as e:
        logger.error(f"Premium API Error: {e}")
        
    # ဒုတိယမြောက် Bypass API စမ်းသပ်ခြင်း (ပထမတစ်ခု မရပါက)
    try:
        api_url = f"https://api.douyin.wtf/api?url={target_url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                if data.get("video_data"):
                    return {"type": "video", "url": data["video_data"]["nwm_video_url"]}
                elif data.get("image_data"):
                    return {"type": "images", "urls": data["image_data"]["no_watermark_image_list"]}
    except Exception as e:
        logger.error(f"Backup API Error: {e}")
        
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "မင်္ဂလာပါ! Rednote လင့်ခ် ပို့ပေးရင် Watermark မပါတဲ့ ပုံနဲ့ ဗီဒီယိုတွေ အမြန်ဆုံး ဆွဲပေးပါမယ်ဗျာ။"
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    if any(is_rednote_link(url) for url in re.findall(r'(https?://[^\s]+)', text)):
        waiting_msg = await update.message.reply_text("ခဏစောင့်ပေးပါ၊ Website ပေါ်ကနည်းလမ်းအတိုင်း ပုံနှင့်ဗီဒီယိုများကို ဆွဲထုတ်နေပါတယ်...")
        media = extract_via_premium_api(text)
        
        if media:
            try:
                if media["type"] == "video":
                    await update.message.reply_video(video=media["url"], caption="ဒေါင်းလုဒ်လုပ်ပြီးပါပြီ!")
                elif media["type"] == "images":
                    img_urls = media["urls"]
                    if len(img_urls) == 1:
                        await update.message.reply_photo(photo=img_urls[0], caption="ဒေါင်းလုဒ်လုပ်ပြီးပါပြီ!")
                    else:
                        media_group = [InputMediaPhoto(media=img_url) for img_url in img_urls[:10]]
                        await update.message.reply_media_group(media=media_group)
                await waiting_msg.delete()
            except Exception as e:
                await waiting_msg.edit_text("ပုံကို ဆွဲထုတ်လို့ရပေမယ့် Telegram ပေါ် တင်ပေးလို့ မရဖြစ်နေပါတယ်။")
                logger.error(f"Telegram Send Error: {e}")
        else:
            await waiting_msg.edit_text("စိတ်မရှိပါနဲ့၊ မီဒီယာကို လုံးဝ ဆွဲထုတ်လို့ မရပါဘူးခင်ဗျာ။ လင့်ခ်မှားနေတာ ဖြစ်နိုင်ပါတယ်။")
    else:
        await update.message.reply_text("ကျေးဇူးပြုပြီး မှန်ကန်တဲ့ Rednote link တစ်ခုကို ပို့ပေးပါနော်။")

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
