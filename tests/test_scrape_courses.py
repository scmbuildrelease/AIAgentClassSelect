import requests
import json
import os
import time
import re
import logging
from urllib.parse import urljoin
from parsers.generic_parser import parse_generic
from openai import OpenAI

# ---------- CONFIG ----------
WEBLINK = "weblink.md"
OUTPUT_DIR = os.getenv("COURSES_OUTPUT_DIR", "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "courses_latest.json")

HEADERS = {
    "User-Agent": os.getenv(
        "HTTP_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    )
}

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# ---------- OPENAI CLIENT ----------
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None
if not client:
    logging.warning("OPENAI_API_KEY not set. AI filtering will be skipped.")

# ---------- SAFE AI PARSER ----------
def safe_parse_ai(content):
    """
    Robustly extracts JSON array from AI response.
    1. Try direct json.loads
    2. Fallback: greedy regex to capture [ ... ] including nested brackets
    """
    content = content.strip()
    try:
        data = json.loads(content)
        return data.get("courses", data) if isinstance(data, dict) else data
    except json.JSONDecodeError:
        pass

    # Greedy match to capture outermost array
    match = re.search(r"\[.*\]", content, re.S)
    if match:
        try:
            return json.loads(match.group())
        except Exception as e:
            logging.warning(f"Greedy JSON parsing failed: {e}")

    logging.warning("AI JSON parsing failed. Returning original list.")
    return []

# ---------- FETCH WITH RETRIES ----------
def fetch(url, retries=3, timeout=15):
    """Fetch HTML content with retries and exponential backoff."""
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=timeout)
            if res.status_code == 200:
                res.encoding = res.apparent_encoding
                return res.text
            logging.warning(f"{url} returned status {res.status_code}")
        except Exception as e:
            logging.warning(f"Attempt {attempt} failed for {url}: {e}")
        time.sleep(attempt * 2)
    logging.error(f"Failed to fetch {url} after {retries} attempts")
    return None

# ---------- MAIN ----------
def run():
    all_courses = []

    # 1. Read links
    if not os.path.exists(WEBLINK):
        logging.error(f"{WEBLINK} not found. Exiting.")
        return

    with open(WEBLINK, "r", encoding="utf-8") as f:
        sites = [
            line.strip().split(",", 1)
            for line in f
            if "," in line and not line.startswith("#")
        ]

    if not sites:
        logging.warning("No valid links found in weblink.md.")
        return

    # 2. Scrape and parse
    for url_raw, cat_raw in sites:
        url, cat = url_raw.strip(), cat_raw.strip()
        logging.info(f"Scraping: {url}")
        html = fetch(url)
        if not html:
            continue

        try:
            courses = parse_generic(html, cat, url) or []

            # Resolve relative links
            for c in courses:
                if c.get("link") and not str(c["link"]).startswith("http"):
                    c["link"] = urljoin(url, c["link"])

            all_courses.extend(courses)
        except Exception as e:
            logging.error(f"Error parsing {url}: {e}")

        time.sleep(1)

    # 3. Deduplicate
    unique_dict = {
        (c.get("title", "").lower(), c.get("link", "")): c
        for c in all_courses
    }
    unique_list = list(unique_dict.values())

    # 4. Pre-filter: Bay Area
    keywords = ["san jose", "bay area", "cupertino", "santa clara", "sunnyvale", "mountain view"]
    filtered = [
        c for c in unique_list
        if any(k in f"{c.get('title','')} {c.get('location','')}".lower() for k in keywords)
    ]
    final_list = filtered if filtered else unique_list[:40]

    # 5. AI filter & ranking
    use_ai = os.getenv("USE_AI", "true").lower() == "true"
    if use_ai and client and final_list:
        logging.info(f"AI filtering {len(final_list[:40])} courses...")
        prompt = (
            "Filter for real kids classes (Age 6-8) in the South Bay Area. "
            "Return a JSON object with a key 'courses' containing the array.\n"
            f"DATA: {json.dumps(final_list[:40])}"
        )
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional JSON assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},  # ✅ Keep for structured JSON
                temperature=0.1
            )
            final_list = safe_parse_ai(response.choices[0].message.content)
        except Exception as e:
            logging.error(f"AI ranking failed: {e}")

    # 6. Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2, ensure_ascii=False)

    logging.info(f"Successfully saved {len(final_list)} courses to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
