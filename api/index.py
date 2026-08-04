import os
import re
import requests
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

def extract_via_cobalt(url):
    try:
        api_url = "https://api.cobalt.tools/api/json"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {"url": url, "filenamePattern": "basic"}
        
        res = requests.post(api_url, json=payload, headers=headers, timeout=8)
        data = res.json()
        
        if data.get("status") in ["stream", "redirect"]:
            return {"type": "video", "url": data.get("url")}
        elif data.get("status") == "picker":
            picker_items = data.get("picker", [])
            urls = [item.get("url") for item in picker_items if item.get("url")]
            if urls:
                return {"type": "images", "urls": urls}
    except Exception as e:
        print(f"Cobalt error: {e}")
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
                    send_message(chat_id, "မင်္ဂလာပါ! Rednote လင့်ခ် ပို့ပေးရင် မီဒီယာ ဒေါင်းလုဒ်လုပ်ပေးပါမယ်ဗျာ။")
                    return 'OK', 200

                urls = re.findall(r'(https?://[^\s]+)', text)
                rednote_url = next((url for url in urls if is_rednote_link(url)), None)

                if rednote_url:
                    send_message(chat_id, "ခဏစောင့်ပေးပါ၊ မီဒီယာ ဒေါင်းလုဒ်လုပ်နေပါတယ်...")
                    media = extract_via_cobalt(rednote_url)
                    if media:
                        if media["type"] == "video":
                            send_video(chat_id, media["url"])
                        elif media["type"] == "images":
                            if len(media["urls"]) == 1:
                                send_photo(chat_id, media["urls"][0])
                            else:
                                send_media_group(chat_id, media["urls"])
                    else:
                        send_message(chat_id, "ဒေတာရှာမတွေ့ပါဘူးဗျာ။")
                elif text:
                    send_message(chat_id, "ကျေးဇူးပြုပြီး Rednote လင့်ခ် ပို့ပေးပါ။")
        except Exception as e:
            print(f"Error: {e}")
        return 'OK', 200

    return 'Bot is active on Vercel!', 200
