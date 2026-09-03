#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربات ارسال روزانه یک صفحه از قرآن کریم
متن عربی + ترجمه فارسی (فولادوند) + صوت کامل صفحه (عبدالباسط مرتل)
صفحه هر روز یکی جلو می‌رود و در state ذخیره می‌شود.
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
STATE_FILE = Path("state.json")

ARABIC_EDITION = "quran-uthmani"
PERSIAN_EDITION = "fa.fooladvand"
API_BASE = "https://api.alquran.cloud/v1"
PAGE_AUDIO_BASE = (
    "https://archive.org/download/quran-by--abd-albasit--morattal--192-kb----604-part-full-quran-604-page--safah_89"
)

TEHRAN = timezone(timedelta(hours=3, minutes=30))


def tehran_today():
    return datetime.now(TEHRAN).date()


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_page": 1, "last_sent_date": None, "last_sent_page": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def next_page(state, today):
    """صفحه بعدی را از state می‌گیرد؛ اگر امروز قبلاً ارسال شده باشد None برمی‌گرداند."""
    last_date = state.get("last_sent_date")
    if last_date == today.isoformat():
        return None  # امروز قبلاً ارسال شده

    last_page = state.get("last_sent_page")
    current = state.get("current_page")

    if isinstance(last_page, int) and 1 <= last_page <= 604:
        page = last_page + 1 if last_page < 604 else 1
    elif isinstance(current, int) and 1 <= current <= 604:
        page = current
    else:
        # شروع از صفحه ۱ اگر state خالی باشد
        page = 1

    return page


def get_page_data(page: int):
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
        ayahs.append(
            {
                "number": ar_ayah["number"],
                "number_in_surah": ar_ayah["numberInSurah"],
                "surah": ar_ayah["surah"]["number"],
                "surah_name": ar_ayah["surah"]["name"],
                "arabic": ar_ayah["text"],
                "persian": fa_ayah["text"],
            }
        )
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
        "title": caption,
        "performer": "عبدالباسط عبدالصمد",
    }
    r = requests.post(url, json=payload, timeout=90)
    r.raise_for_status()
    return r.json()


def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN و TELEGRAM_CHANNEL_ID باید در Secrets تنظیم شوند")

    today = tehran_today()
    state = load_state()
    page = next_page(state, today)

    if page is None:
        print(f"امروز ({today}) قبلاً ارسال شده (صفحه {state.get('last_sent_page')}). رد می‌شود.")
        return

    print(f"تاریخ تهران: {today} | صفحه: {page}")

    ayahs, page_num = get_page_data(page)

    header = f"📖 <b>صفحه {page_num} قرآن کریم</b>\n"
    header += f"تاریخ: {today.isoformat()}\n"
    header += "صوت کامل صفحه: استاد عبدالباسط عبدالصمد (مرتل)\n"
    header += "─" * 20 + "\n\n"

    body_parts = []
    for a in ayahs:
        body_parts.append(
            f"<b>{a['surah_name']} | آیه {a['number_in_surah']}</b>\n"
            f"{a['arabic']}\n\n"
            f"<i>{a['persian']}</i>\n"
        )

    full_text = header + "\n".join(body_parts)
    if len(full_text) > 4000:
        full_text = header + "\n".join(body_parts[:10]) + "\n\n... (ادامه متن در صوت صفحه)"

    send_message(full_text)
    time.sleep(1.5)

    page_str = f"{page_num:03d}"
    audio_url = f"{PAGE_AUDIO_BASE}/Page{page_str}_2.mp3"
    caption = f"صفحه {page_num} قرآن کریم | عبدالباسط مرتل"

    try:
        send_audio(audio_url, caption)
        print(f"صوت صفحه {page_num} ارسال شد.")
    except Exception as e:
        print(f"خطا در ارسال صوت صفحه {page_num}: {e}")
        alt_url = f"{PAGE_AUDIO_BASE}/Page{page_str}.mp3"
        try:
            send_audio(alt_url, caption)
            print(f"صوت صفحه {page_num} با نام جایگزین ارسال شد.")
        except Exception as e2:
            print(f"خطای نهایی صوت: {e2}")

    next_p = page_num + 1 if page_num < 604 else 1
    state["last_sent_date"] = today.isoformat()
    state["last_sent_page"] = page_num
    state["current_page"] = next_p
    save_state(state)
    print(f"صفحه {page_num} ارسال شد. صفحه بعدی: {next_p}")


if __name__ == "__main__":
    main()
