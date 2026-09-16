import os
import re
import json
import requests
from bs4 import BeautifulSoup
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
    payload = {"chat_id": chat_id, "video": video_url, "caption": "Here is your HD video!"}
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Error: {e}")

def send_photo(chat_id, photo_url):
    url = f"{TELEGRAM_API}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": "Here is your HD image!"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error: {e}")

def is_rednote_link(url):
    return "xiaohongshu.com" in url or "xhslink.com" in url

def extract_rednote_media(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        session = requests.Session()
        res = session.get(url, headers=headers, allow_redirects=True, timeout=8)
        
        # 1. Page ထဲက Initial State (JSON Data) ကို ရှာပြီး မူရင်း High Quality URL ယူခြင်း
        json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});</script>', res.text)
        if json_match:
            data = json.loads(json_match.group(1))
            note_data = data.get("note", {}).get("noteDetailMap", {})
            first_key = list(note_data.keys())[0] if note_data else None
            
            if first_key:
                note = note_data[first_key].get("note", {})
                
                # HD Video Stream URL ရှာခြင်း
                video_info = note.get("video", {})
                if video_info and "media" in video_info:
                    stream_url = video_info["media"].get("stream", {}).get("h264", [{}])[0].get("masterUrl")
                    if stream_url:
                        return {"type": "video", "url": stream_url}
                
                # HD Images ရှာခြင်း
                image_list = note.get("imageList", [])
                if image_list:
                    hd_images = [img.get("urlDefault") or img.get("url") for img in image_list if img.get("urlDefault") or img.get("url")]
                    if hd_images:
                        return {"type": "image", "url": hd_images[0]}

        # 2. Fallback (မရပါက ရိုးရိုး BeautifulSoup ဖြင့် ပြန်ရှာခြင်း)
        soup = BeautifulSoup(res.text, 'html.parser')
        video_meta = soup.find("meta", property="og:video") or soup.find("meta", attrs={"name": "og:video"})
        if video_meta and video_meta.get("content"):
            return {"type": "video", "url": video_meta["content"]}
            
        image_meta = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
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
