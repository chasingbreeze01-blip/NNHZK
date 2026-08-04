import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request

TOKEN = '8754460428:AAFGxRB1B4-DuL-QXxgd4fWWh0okPiznGhM'
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error: {e}")

def send_video(chat_id, video_url):
    url = f"{TELEGRAM_API}/sendVideo"
    payload = {"chat_id": chat_id, "video": video_url, "caption": "Here is your video!"}
    try:
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        print(f"Error: {e}")

def send_photo(chat_id, photo_url):
    url = f"{TELEGRAM_API}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": "Here is your image!"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error: {e}")

def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

# မူရင်း Beautiful Soup / Downloader Logic (Spelling Error ပြင်ပြီး)
def extract_rednote_media(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=8)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ဗီဒီယိုလင့်ခ် ရှာဖွေခြင်း
        video_meta = soup.find("meta", property="og:video")
        if video_meta and video_meta.get("content"):
            return {"type": "video", "url": video_meta["content"]}
            
        # ပုံလင့်ခ် ရှာဖွေခြင်း
        image_meta = soup.find("meta", property="og:image")
        if image_meta and image_meta.get("content"):
            return {"type": "image", "url": image_meta["content"]}
            
    except Exception as e:
        print(f"Error extracting media: {e}")
    return None

@app.route('/', defaults={'path': ''}, methods=['POST', 'GET'])
@app.route('/<path:path>', methods=['POST', 'GET'])
def webhook(path):
    if request.method == 'POST':
        try:
            data = request.get_json(force=True, silent=True)
            if data and "message" in data:
                message = data["message"]
                chat_id = message["chat"]["id"]
                text = message.get("text", "")

                if text.startswith("/start"):
                    welcome_text = (
                        "မင်္ဂလာပါ ✌️ NyiNyi + K 's OASIS 🍀🌎 လေးက ကြိုဆိုပါတယ်ဗျာ💕 \n\n"
                        "Rednote link ပို့ပေးရင် watermark မပါတဲ့ video ပြန်ဒေါင်းပေးပါမယ်ဗျ🫶🏻"
                    )
                    send_message(chat_id, welcome_text)
                    return 'OK', 200

                urls = re.findall(r'(https?://[^\s]+)', text)
                rednote_url = next((url for url in urls if is_rednote_link(url)), None)

                if rednote_url:
                    send_message(chat_id, "ခဏလေးစောင့်ပေးပါနော် ⏳ media ကိုရှာဖွေနေပါတယ်❤️...")
                    media = extract_rednote_media(rednote_url)
                    if media:
                        if media["type"] == "video":
                            send_video(chat_id, media["url"])
                        elif media["type"] == "image":
                            send_photo(chat_id, media["url"])
                    else:
                        send_message(chat_id, "Data ကို ရှာမတွေ့ပါဘူးဗျ 🥺 link မှားနေတာဖြစ်နိုင်ပါတယ်။")
                elif text:
                    send_message(chat_id, "ကျေးဇူးပြုပြီး မှန်ကန်တဲ့ Rednote link တစ်ခုကို ပို့ပေးပါနော် 🫶🏻")
        except Exception as e:
            print(f"Webhook Error: {e}")
        return 'OK', 200

    return 'Bot is active on Vercel!', 200
