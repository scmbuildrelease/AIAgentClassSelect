import requests
import json
import os
import time
from parsers.generic_parser import parse_generic

WEBLINK = "weblink.md"
OUTPUT = "/data/courses_latest.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
}

# ---------- read links ----------
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


# ---------- fetch with retry ----------
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


# ---------- deduplicate ----------
def deduplicate(courses):
    seen = set()
    unique = []

    for c in courses:
        key = (c["title"], c["link"])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


# ---------- main ----------
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

    # ---------- save ----------
    os.makedirs("/data", exist_ok=True)

    with open(OUTPUT, "w") as f:
        json.dump(all_courses, f, indent=2)

    print(f"✅ Saved {len(all_courses)} courses")


if __name__ == "__main__":
    run()
