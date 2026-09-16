import os
import re
import requests
from flask import Flask, request

TOKEN = '8754460428:AAFGxRB1B4-DuL-QXxgd4fWWh0okPiznGhM'
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text,
        "reply_markup": {
            "keyboard": [[{"text": "🚀 Start"}]],
            "resize_keyboard": True,
            "is_persistent": True
        }
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error: {e}")

def send_video(chat_id, video_url):
    url = f"{TELEGRAM_API}/sendVideo"
    payload = {"chat_id": chat_id, "video": video_url, "caption": "Here is your video!"}
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"Error: {e}")

def send_photo(chat_id, photo_url):
    url = f"{TELEGRAM_API}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": "Here is your image!"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error: {e}")

def send_media_group(chat_id, media_urls):
    url = f"{TELEGRAM_API}/sendMediaGroup"
    media = [{"type": "photo", "media": u} for u in media_urls[:10]]
    payload = {"chat_id": chat_id, "media": media}
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"Error: {e}")

def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

# Short Link (xhslink.com) များကို Real URL သို့ ပြောင်းပေးသည့် Function
def get_real_url(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.head(url, headers=headers, allow_redirects=True, timeout=5)
        return res.url
    except Exception:
        return url

def extract_rednote_media(url):
    real_url = get_real_url(url)
    
    # Method 1: TikWM Rednote API
    try:
        api_url = f"https://api.v2.tikwm.com/api/rednote?url={real_url}"
        res = requests.get(api_url, timeout=6).json()
        if res.get("code") == 0 and "data" in res:
            data = res["data"]
            if data.get("images"):
                return {"type": "images", "urls": data["images"]}
            elif data.get("play"):
                return {"type": "video", "url": data["play"]}
    except Exception as e:
        print(f"API 1 Error: {e}")

    # Method 2: Cobalt API
    try:
        cobalt_url = "https://api.cobalt.tools/api/json"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {"url": real_url}
        res = requests.post(cobalt_url, json=payload, headers=headers, timeout=6).json()
        
        status = res.get("status")
        if status in ["stream", "redirect"]:
            return {"type": "video", "url": res.get("url")}
        elif status == "picker":
            urls = [item.get("url") for item in res.get("picker", []) if item.get("url")]
            if urls:
                return {"type": "images", "urls": urls}
    except Exception as e:
        print(f"API 2 Error: {e}")

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

                if text.startswith("/start") or text == "🚀 Start":
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
                        elif media["type"] == "images":
                            if len(media["urls"]) == 1:
                                send_photo(chat_id, media["urls"][0])
                            else:
                                send_media_group(chat_id, media["urls"])
                    else:
                        send_message(chat_id, "Data ကို ရှာမတွေ့ပါဘူးဗျ 🥺 link မှားနေတာဖြစ်နိုင်ပါတယ်။")
                elif text:
                    send_message(chat_id, "ကျေးဇူးပြုပြီး မှန်ကန်တဲ့ Rednote link တစ်ခုကို ပို့ပေးပါနော် 🫶🏻")
        except Exception as e:
            print(f"Webhook Error: {e}")
        return 'OK', 200

    return 'Bot is active on Vercel!', 200
