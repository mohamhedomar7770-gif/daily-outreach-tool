"""Daily brand discovery and outreach generator."""
import csv
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "60"))
TARGET_MARKETS = os.environ.get("TARGET_MARKETS", "مصر,السعودية,الإمارات,الكويت,قطر,البحرين,عمان")
MY_SERVICE_DESCRIPTION = os.environ.get("MY_SERVICE_DESCRIPTION", "خدمات media buying وإدارة حملات إعلانية للـ e-commerce في مصر والخليج")


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def gemini_request(prompt, grounded=False):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY غير موجود")
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if grounded:
        payload["tools"] = [{"google_search": {}}]
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Gemini response غير متوقع: {data}") from exc
    metadata = data.get("candidates", [{}])[0].get("groundingMetadata", {})
    sources = [x.get("web", {}).get("uri", "") for x in metadata.get("groundingChunks", []) if x.get("web", {}).get("uri")]
    return text, sources


def parse_json_array(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        raise ValueError(f"لم يرجع Gemini قائمة JSON: {text[:300]}")
    value = json.loads(text[start:end + 1])
    return value if isinstance(value, list) else []


def load_rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_rows(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def norm(value):
    return re.sub(r"[^a-z0-9\u0600-\u06ff]", "", (value or "").lower())


def discover_brands():
    queries = [r.get("query", "").strip() for r in load_rows(DATA / "search_queries.csv") if r.get("query")]
    if not queries:
        queries = [
            "Instagram TikTok e-commerce brands Egypt skincare fashion food accessories",
            "Instagram TikTok brands Saudi Arabia UAE Kuwait Qatar Bahrain Oman e-commerce",
        ]
    prompt = f"""أنت باحث عملاء محتملين لخدمات media buying. استخدم Google Search للعثور على براندات حقيقية ونشطة في مصر والخليج ({TARGET_MARKETS}).
ابحث في Instagram وTikTok العامين، ولا تخترع أي حساب. نفّذ الاستعلامات التالية:
{chr(10).join('- ' + q for q in queries)}

أرجع JSON فقط، بدون Markdown، كمصفوفة من أفضل 10 براندات لكل استعلام، وبإجمالي لا يتجاوز {DAILY_LIMIT} براندًا. كل عنصر يجب أن يحتوي:
brand_name, handle_or_page, instagram_url, tiktok_url, website_url, dm_url, niche, market, notes, fit_score, fit_reason.
يجب أن يحتوي كل عنصر على رابط Instagram أو TikTok عام واحد على الأقل، وأن يكون مناسبًا للتجارة الإلكترونية أو لديه منتج يمكن الإعلان عنه، وأن يحتوي على instagram_url أو tiktok_url صالح. لا تكرر نفس البراند. اذكر فقط معلومات ظاهرة في نتائج البحث، واكتب fit_score من 1 إلى 5."""
    text, sources = gemini_request(prompt, grounded=True)
    items = parse_json_array(text)
    for item in items:
        existing = item.get("source_urls", [])
        if isinstance(existing, str):
            existing = [x.strip() for x in existing.split("|") if x.strip()]
        item["source_urls"] = " | ".join(list(dict.fromkeys(existing + sources))[:8])
    return items[:DAILY_LIMIT]


def check_meta_ads(brand_name):
    if not META_ACCESS_TOKEN:
        return "لم يتم الفحص (META_ACCESS_TOKEN اختياري)"
    try:
        params = {"search_terms": brand_name, "ad_reached_countries": "['EG','SA','AE','KW','QA','BH','OM']", "ad_active_status": "ACTIVE", "access_token": META_ACCESS_TOKEN, "fields": "page_name,ad_creation_time"}
        url = "https://graph.facebook.com/v19.0/ads_archive?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read())
        count = len(data.get("data", []))
        return f"عنده {count} إعلان شغال حاليًا" if count else "مفيش إعلانات شغالة دلوقتي"
    except Exception as exc:  # noqa: BLE001
        return f"تعذر الفحص ({exc})"


def draft_message(brand_name, niche, notes, ads_status):
    prompt = f"""اكتب رسالة outreach قصيرة من 3 إلى 4 أسطر بالعامية المصرية لبراند اسمه {brand_name}.
المجال: {niche}. الملاحظات: {notes}. حالة الإعلانات: {ads_status}.
أنا media buyer وخدمتي: {MY_SERVICE_DESCRIPTION}.
اذكر ملاحظة حقيقية من البيانات، لا تدّعي أنك تواصلت معهم من قبل، لا تبالغ ولا تضغط، واختم بسؤال بسيط يفتح حوار. أرجع النص فقط."""
    text, _ = gemini_request(prompt)
    return text


def main():
    if not GEMINI_API_KEY:
        raise SystemExit("أضف GEMINI_API_KEY إلى GitHub Secrets أولًا")
    history_fields = ["brand_name", "handle_or_page", "instagram_url", "tiktok_url", "website_url", "dm_url", "niche", "market", "notes", "fit_score", "fit_reason", "status", "first_seen", "last_seen", "source_urls"]
    history_path = DATA / "brand_history.csv"
    history = load_rows(history_path)
    seeded = [r for r in load_rows(DATA / "brands.csv") if not r.get("brand_name", "").startswith("مثال")]
    keys = {norm(v) for row in history + seeded for v in (row.get("handle_or_page"), row.get("instagram_url"), row.get("tiktok_url"), row.get("brand_name")) if v}
    try:
        discovered = discover_brands()
    except Exception as exc:
        print(f"تعذر اكتشاف البراندات: {exc}")
        discovered = []
    new_items = []
    for item in discovered:
        name, handle = str(item.get("brand_name", "")).strip(), str(item.get("handle_or_page", "")).strip()
        ig, tt = str(item.get("instagram_url", "")).strip(), str(item.get("tiktok_url", "")).strip()
        website = str(item.get("website_url", "")).strip()
        dm_url = (f"https://ig.me/m/{handle.lstrip("@")}" if ig and handle else (tt or ig))
        item["website_url"], item["dm_url"] = website, dm_url
        key = norm(ig or tt or handle or name)
        if not name or not key or key in keys or not (ig or tt):
            continue
        keys.add(key)
        stamp = now_iso()
        item.update({"status": "new", "first_seen": stamp, "last_seen": stamp})
        item["source_urls"] = item.get("source_urls", "")
        history.append({field: str(item.get(field, "")) for field in history_fields})
        new_items.append(item)
        if len(new_items) >= DAILY_LIMIT:
            break
    save_rows(history_path, history, history_fields)
    results = []
    for item in new_items:
        ads_status = check_meta_ads(item["brand_name"])
        try:
            message = draft_message(item["brand_name"], item.get("niche", ""), item.get("notes", ""), ads_status)
        except Exception as exc:
            message = f"تعذر توليد الرسالة: {exc}"
        results.append({"brand": item["brand_name"], "handle": item.get("handle_or_page", ""), "instagram_url": item.get("instagram_url", ""), "tiktok_url": item.get("tiktok_url", ""), "website_url": item.get("website_url", ""), "dm_url": item.get("dm_url", ""), "niche": item.get("niche", ""), "market": item.get("market", ""), "fit_score": item.get("fit_score", ""), "fit_reason": item.get("fit_reason", ""), "ads_status": ads_status, "message": message, "status": "new", "source_urls": item.get("source_urls", "")})
    output = {"generated_at": now_iso(), "count": len(results), "daily_limit": DAILY_LIMIT, "markets": TARGET_MARKETS.split(","), "results": results, "note": "النتائج اكتُشفت من بحث Google عبر Gemini؛ راجعها قبل التواصل."}
    DOCS.mkdir(exist_ok=True)
    (DOCS / "results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"تم اكتشاف {len(new_items)} براند جديد وتوليد {len(results)} رسالة.")


if __name__ == "__main__":
    main()
