import requests
import json
import os
import time
import re

from parsers.generic_parser import parse_generic
from openai import OpenAI

# ---------- CONFIG ----------
WEBLINK = "weblink.md"
OUTPUT = "/data/courses_latest.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
}

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- SAFE AI PARSER ----------
def safe_parse_ai(content):
    try:
        return json.loads(content)
    except:
        match = re.search(r"\[.*\]", content, re.S)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        print("⚠️ AI JSON parsing failed")
        return []

# ---------- READ LINKS ----------
def read_links():
    sites = []
    with open(WEBLINK) as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "," not in line:
                continue

            url, cat = line.split(",", 1)
            sites.append((url.strip(), cat.strip()))

    return sites

# ---------- FETCH WITH RETRY ----------
def fetch(url):
    for attempt in range(2):
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                return res.text
        except Exception as e:
            print(f"⚠️ retry {attempt+1} failed for {url}: {e}")

        time.sleep(1)

    return None

# ---------- DEDUP ----------
def deduplicate(courses):
    seen = set()
    unique = []

    for c in courses:
        key = (c.get("title"), c.get("link"))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique

# ---------- PRE-FILTER (LOCATION) ----------
def pre_filter(courses):
    result = []

    for c in courses:
        text = (c.get("title", "") + c.get("location", "")).lower()

        if any(k in text for k in ["san jose", "bay area", "cupertino", "santa clara"]):
            result.append(c)

    return result or courses  # fallback if empty

# ---------- AI FILTER ----------
def ai_filter_and_rank(courses):
    if not courses:
        return []

    sample = courses[:30]  # cost control

    prompt = f"""
You are a smart assistant helping parents find kids classes.

TASK:
1. Keep only REAL kids courses (remove navigation, login, ads)
2. Prefer age 6-8
3. Prefer San Jose / Bay Area
4. Rank best courses first

IMPORTANT:
Use the structured fields (age, location, schedule, price) when ranking.

Return STRICT JSON:

[
  {{
    "title": "...",
    "link": "...",
    "category": "...",
    "age": "...",
    "location": "...",
    "score": 1-5,
    "reason": "short reason"
  }}
]

DATA:
{json.dumps(sample, indent=2)}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        content = response.choices[0].message.content

        return safe_parse_ai(content)

    except Exception as e:
        print(f"❌ AI failed: {e}")
        return courses  # fallback

# ---------- MAIN ----------
def run():
    all_courses = []

    sites = read_links()

    for url, cat in sites:
        print(f"🔍 Scraping: {url}")

        html = fetch(url)
        if not html:
            print(f"❌ Failed: {url}")
            continue

        courses = parse_generic(html, cat, url)
        all_courses.extend(courses)

        time.sleep(1)  # rate limit

    # ---------- deduplicate ----------
    all_courses = deduplicate(all_courses)

    # ---------- pre-filter ----------
    all_courses = pre_filter(all_courses)

    # ---------- AI filter ----------
    use_ai = os.getenv("USE_AI", "true").lower() == "true"

    if use_ai:
        print("🤖 Running AI filter...")
        all_courses = ai_filter_and_rank(all_courses)

    # ---------- save ----------
    os.makedirs("/data", exist_ok=True)

    with open(OUTPUT, "w") as f:
        json.dump(all_courses, f, indent=2)

    print(f"✅ Saved {len(all_courses)} courses")


# ---------- ENTRY ----------
if __name__ == "__main__":
    run()
