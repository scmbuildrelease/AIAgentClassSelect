import os
import json
import time
import logging
from urllib.parse import urljoin
from parsers.generic_parser import parse_generic
import requests
from openai import OpenAI

# ---------- CONFIG ----------
WEBLINK = "weblink.md"
OUTPUT_DIR = os.getenv("COURSES_OUTPUT_DIR", "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "courses_latest.json")

HEADERS = {
    "User-Agent": os.getenv(
        "HTTP_USER_AGENT", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    )
}

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)

# ---------- OPENAI CLIENT ----------
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None
if not client:
    logging.warning("OPENAI_API_KEY not set. AI filtering will be skipped.")

# ---------- SAFE AI PARSER ----------
def safe_parse_ai(content):
    content = content.strip()
    try:
        data = json.loads(content)
        return data.get("courses", data) if isinstance(data, dict) else data
    except:
        match = re.search(r"(\[.*\])", content, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
    logging.warning("AI JSON parsing failed.")
    return []

# ---------- FETCH WITH RETRIES ----------
def fetch(url, retries=3, timeout=15):
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=timeout)
            if res.status_code == 200:
                res.encoding = res.apparent_encoding
                return res.text
        except Exception as e:
            logging.warning(f"Attempt {attempt} failed for {url}: {e}")
        time.sleep(attempt * 2)
    return None

# ---------- MAIN ----------
def run():
    all_courses = []

    if not os.path.exists(WEBLINK):
        logging.error(f"{WEBLINK} not found.")
        return

    with open(WEBLINK, "r", encoding="utf-8") as f:
        sites = [line.strip().split(",", 1) for line in f if "," in line and not line.startswith("#")]

    for url_raw, cat_raw in sites:
        url, cat = url_raw.strip(), cat_raw.strip()
        html = fetch(url)
        if not html: continue
        try:
            courses = parse_generic(html, cat, url) or []
            for c in courses:
                if c.get("link") and not str(c["link"]).startswith("http"):
                    c["link"] = urljoin(url, c["link"])
            all_courses.extend(courses)
        except Exception as e:
            logging.error(f"Error parsing {url}: {e}")

    # Deduplicate
    unique_dict = {(c.get("title","").lower(), c.get("link","")): c for c in all_courses}
    unique_list = list(unique_dict.values())

    # Pre-filter
    keywords = ["san jose", "bay area", "cupertino", "santa clara", "sunnyvale", "mountain view"]
    filtered = [c for c in unique_list if any(k in f"{c.get('title','')} {c.get('location','')}".lower() for k in keywords)]
    final_list = filtered if filtered else unique_list[:40]

    # AI filtering
    use_ai = os.getenv("USE_AI","true").lower() == "true"
    if use_ai and client and final_list:
        prompt = f"Filter real kids classes (Age 6-8) in South Bay. Return JSON object with key 'courses'.\nDATA: {json.dumps(final_list[:40])}"
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"You are a JSON assistant."},
                    {"role":"user","content":prompt}
                ],
                response_format={"type":"json_object"},
                temperature=0.1
            )
            final_list = safe_parse_ai(response.choices[0].message.content)
        except Exception as e:
            logging.error(f"AI ranking failed: {e}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    logging.info(f"Saved {len(final_list)} courses to {OUTPUT_FILE}")

if __name__ == "__main__":
    run()
