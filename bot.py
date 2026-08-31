#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربات ارسال روزانه یک صفحه از قرآن کریم
متن عربی + ترجمه فارسی (فولادوند) + صوت عبدالباسط
"""

import os
import json
import time
import requests
from pathlib import Path

# ================== تنظیمات ==================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
STATE_FILE = Path("state.json")

ARABIC_EDITION = "quran-uthmani"
PERSIAN_EDITION = "fa.fooladvand"
AUDIO_EDITION = "ar.abdulbasitmurattal"  # عبدالباسط مرتل

API_BASE = "https://api.alquran.cloud/v1"
AUDIO_CDN = "https://cdn.islamic.network/quran/audio/128"  # کیفیت ۱۲۸

# ================== توابع ==================

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_page": 1}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_page_data(page: int):
    """گرفتن آیات یک صفحه با متن عربی و ترجمه فارسی"""
    url = f"{API_BASE}/page/{page}/{ARABIC_EDITION}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    arabic_data = r.json()["data"]

    url_fa = f"{API_BASE}/page/{page}/{PERSIAN_EDITION}"
    r_fa = requests.get(url_fa, timeout=30)
    r_fa.raise_for_status()
    persian_data = r_fa.json()["data"]

    ayahs = []
    for ar_ayah, fa_ayah in zip(arabic_data["ayahs"], persian_data["ayahs"]):
        ayahs.append({
            "number": ar_ayah["number"],
            "number_in_surah": ar_ayah["numberInSurah"],
            "surah": ar_ayah["surah"]["number"],
            "surah_name": ar_ayah["surah"]["name"],
            "arabic": ar_ayah["text"],
            "persian": fa_ayah["text"],
        })
    return ayahs, arabic_data.get("number", page)


def send_message(text: str, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def send_audio(audio_url: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
    payload = {
        "chat_id": CHANNEL_ID,
        "audio": audio_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN و TELEGRAM_CHANNEL_ID باید تنظیم شوند")

    state = load_state()
    page = state.get("current_page", 1)

    if page > 604:
        page = 1  # بعد از ختم قرآن دوباره از اول

    print(f"در حال پردازش صفحه {page} ...")

    ayahs, page_num = get_page_data(page)

    # ساخت متن پیام
    header = f"📖 <b>صفحه {page_num} قرآن کریم</b>\n"
    header += f"صوت: استاد عبدالباسط عبدالصمد\n"
    header += "─" * 20 + "\n\n"

    body_parts = []
    for a in ayahs:
        body_parts.append(
            f"<b>{a['surah_name']} | آیه {a['number_in_surah']}</b>\n"
            f"{a['arabic']}\n\n"
            f"<i>{a['persian']}</i>\n"
        )

    full_text = header + "\n".join(body_parts)

    # تلگرام محدودیت ۴۰۹۶ کاراکتر دارد
    if len(full_text) > 4000:
        # اگر خیلی طولانی شد، فقط هدر + چند آیه اول
        full_text = header + "\n".join(body_parts[:8]) + "\n\n... (ادامه در صوت)"

    send_message(full_text)
    time.sleep(1)

    # ارسال صوت آیات صفحه
    for a in ayahs:
        audio_url = f"{AUDIO_CDN}/{AUDIO_EDITION}/{a['number']}.mp3"
        caption = f"آیه {a['number_in_surah']} | سوره {a['surah_name']}"
        try:
            send_audio(audio_url, caption)
            time.sleep(1.5)  # جلوگیری از محدودیت تلگرام
        except Exception as e:
            print(f"خطا در ارسال صوت آیه {a['number']}: {e}")

    # به‌روزرسانی صفحه بعدی
    state["current_page"] = page + 1
    save_state(state)
    print(f"صفحه {page} با موفقیت ارسال شد. صفحه بعدی: {page + 1}")


if __name__ == "__main__":
    main()
