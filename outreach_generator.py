"""
Outreach Generator
-------------------
يقرا ليستة براندات من data/brands.csv، ولكل براند بيولّد رسالة outreach
مخصصة باستخدام Claude API، ويحفظ النتيجة في docs/results.json
عشان صفحة GitHub Pages تعرضها.

لو عندك META_ACCESS_TOKEN (اختياري)، السكريبت هيحاول كمان يجيب حالة
الإعلانات بتاعة البراند من Meta Ads Library API.
"""

import os
import csv
import json
import datetime
import urllib.request
import urllib.parse

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")  # اختياري

MY_SERVICE_DESCRIPTION = os.environ.get(
    "MY_SERVICE_DESCRIPTION",
    "خدمات media buying وإدارة حملات إعلانية للـ e-commerce في مصر والخليج",
)


def check_meta_ads(brand_name: str) -> str:
    """يفحص لو البراند عنده إعلانات شغالة دلوقتي على Meta Ads Library (اختياري)."""
    if not META_ACCESS_TOKEN:
        return "لم يتم الفحص (محتاج META_ACCESS_TOKEN)"
    try:
        params = {
            "search_terms": brand_name,
            "ad_reached_countries": "['EG','SA','AE','KW','QA']",
            "ad_active_status": "ACTIVE",
            "access_token": META_ACCESS_TOKEN,
            "fields": "page_name,ad_creation_time",
        }
        url = "https://graph.facebook.com/v19.0/ads_archive?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        count = len(data.get("data", []))
        return f"عنده {count} إعلان شغال حاليًا" if count else "مفيش إعلانات شغالة دلوقتي"
    except Exception as e:  # noqa: BLE001
        return f"تعذر الفحص ({e})"


def draft_message(brand_name: str, niche: str, notes: str, ads_status: str) -> str:
    """يستخدم Gemini API (مجاني) عشان يكتب رسالة outreach مخصصة."""
    if not GEMINI_API_KEY:
        return "[محتاج GEMINI_API_KEY عشان يتولد نص الرسالة]"

    prompt = f"""اكتب رسالة outreach قصيرة (3-4 أسطر) بالعامية المصرية لبراند اسمه {brand_name}،
مجاله: {niche}. ملاحظات عنه: {notes}. حالة إعلاناته: {ads_status}.
أنا media buyer وخدمتي: {MY_SERVICE_DESCRIPTION}.
الرسالة تكون ودودة، شخصية (تذكر حاجة عن البراند)، ومن غير مبالغة أو إلحاح، وتنتهي بسؤال بسيط يفتح حوار."""

    body = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}]}
    ).encode()

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def main():
    results = []
    with open("data/brands.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["brand_name"].startswith("مثال"):
                continue  # تخطي صف المثال
            ads_status = check_meta_ads(row["brand_name"])
            message = draft_message(
                row["brand_name"], row["niche"], row.get("notes", ""), ads_status
            )
            results.append(
                {
                    "brand": row["brand_name"],
                    "handle": row.get("handle_or_page", ""),
                    "niche": row["niche"],
                    "ads_status": ads_status,
                    "message": message,
                }
            )

    output = {
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "count": len(results),
        "results": results,
    }
    os.makedirs("docs", exist_ok=True)
    with open("docs/results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"تم توليد {len(results)} رسالة.")


if __name__ == "__main__":
    main()