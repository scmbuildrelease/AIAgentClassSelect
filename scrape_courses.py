import requests
import json
import os
from datetime import datetime
from parsers.generic_parser import parse_generic

# ---------- CONFIG ----------
WEBLINK_FILE = "weblink.md"
HISTORY_FILE = "courses_history.json"
OUTPUT_FILE = f"courses_{datetime.now().strftime('%Y%m%d')}.md"

# ---------- Read weblink.md ----------
def read_weblinks(file_path=WEBLINK_FILE):
    sites = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            url, category = line.split(",", 1)
            sites.append({"url": url.strip(), "category": category.strip()})
    return sites

# ---------- Scrape ----------
def scrape_sites(sites):
    all_courses = []

    for site in sites:
        try:
            print(f"🔍 Scraping {site['url']}")
            res = requests.get(site["url"], timeout=10)

            if res.status_code != 200:
                print(f"⚠️ Failed: {site['url']}")
                continue

            courses = parse_generic(res.text, site["category"])
            all_courses.extend(courses)

        except Exception as e:
            print(f"❌ Error: {e}")

    return all_courses

# ---------- History ----------
def compare_history(new_data):
    if os.path.exists(HISTORY_FILE):
        old = json.load(open(HISTORY_FILE))
    else:
        old = []

    old_titles = {c["title"] for c in old}

    added = [c for c in new_data if c["title"] not in old_titles]

    json.dump(new_data, open(HISTORY_FILE, "w"), indent=2)

    return added

# ---------- Markdown ----------
def generate_md(courses, added):
    lines = ["# Weekly Kids Courses\n"]

    for c in courses:
        tag = "🆕" if c in added else ""
        lines.append(f"- {tag} [{c['title']}]({c['link']}) ({c['category']})")

    return "\n".join(lines)

# ---------- MAIN ----------
if __name__ == "__main__":
    sites = read_weblinks()
    courses = scrape_sites(sites)
    added = compare_history(courses)

    md = generate_md(courses, added)

    with open(OUTPUT_FILE, "w") as f:
        f.write(md)

    print(f"✅ Generated {OUTPUT_FILE}")
