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

# ---------- LOGGING ----------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# ---------- OPENAI CLIENT ----------
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.warning("OPENAI_API_KEY not set. AI filtering will be skipped.")
    client = None
else:
    client = OpenAI(api_key=api_key)

# ---------- SAFE AI PARSER ----------
def safe_parse_ai(content):
    """Robustly extracts JSON even if the model adds conversational text."""
    content = content.strip()
    try:
        data = json.loads(content)
        return data.get("courses", data) if isinstance(data, dict) else data
    except json.JSONDecodeError:
        # Non-greedy match handles multiple bracketed sections safely
        match = re.search(r"(\[.*?\])", content, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception as e:
                logging.warning(f"Nested JSON parse failed: {e}")
    logging.warning("AI JSON parsing failed.")
    return []

# ---------- FETCH WITH RETRIES ----------
def fetch(url, retries=3, timeout=15):
    """Fetch a URL with basic retry logic and exponential backoff."""
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=timeout)
            if res.status_code == 200:
                res.encoding = res.apparent_encoding
                return res.text
            logging.warning(f"{url} returned status {res.status_code}")
        except Exception as e:
            logging.warning(f"Attempt {attempt} failed for {url}: {e}")
        time.sleep(attempt * 2)  # simple backoff
    logging.error(f"Failed to fetch {url} after {retries} attempts")
    return None

# ---------- READ LINKS ----------
def read_links():
    sites = []
    if not os.path.exists(WEBLINK):
        logging.error(f"Link file not found: {WEBLINK}")
        return sites

    with open(WEBLINK, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "," not in line:
                continue
            url, cat = line.split(",", 1)
            sites.append((url.strip(), cat.strip()))
    return sites

# ---------- DEDUPLICATE ----------
def deduplicate(courses):
    seen = set()
    unique = []
    for c in courses:
        title = str(c.get("title", "")).strip().lower()
        link = str(c.get("link", "")).strip()
        key = (title, link)
        if key not in seen and title:
            seen.add(key)
            unique.append(c)
    return unique

# ---------- PRE-FILTER (LOCATION) ----------
def pre_filter(courses):
    if not courses:
        return []

    keywords = ["san jose", "bay area", "cupertino", "santa clara", "sunnyvale", "mountain view"]
    filtered = [
        c for c in courses
        if any(k in f"{c.get('title','')} {c.get('location','')}".lower() for k in keywords)
    ]

    if not filtered:
        logging.info("No Bay Area matches in pre-filter; using top 40 as fallback.")
        return courses[:40]

    return filtered

# ---------- AI FILTER ----------
def ai_filter_and_rank(courses):
    if not client or not courses:
        return courses

    sample = courses[:40]  # limit to top 40 for cost/token efficiency
    prompt = f"""
You are an educational consultant for parents.
TASK:
1. Filter this list for REAL kids' classes/camps (Age 6-8).
2. Rank South Bay/San Jose options highest.
3. Return a JSON object with a key "courses" containing the array of results.

DATA:
{json.dumps(sample, indent=2)}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a JSON assistant that outputs valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content
        parsed = safe_parse_ai(content)
        return parsed if isinstance(parsed, list) else courses
    except Exception as e:
        logging.error(f"AI processing failed: {e}")
        return courses

# ---------- MAIN ----------
def run():
    all_courses = []
    sites = read_links()
    if not sites:
        logging.error("No valid links found. Exiting.")
        return

    for url, cat in sites:
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
            logging.error(f"Parser error for {url}: {e}")

        time.sleep(1)

    # Core pipeline
    all_courses = deduplicate(all_courses)
    all_courses = pre_filter(all_courses)

    if os.getenv("USE_AI", "true").lower() == "true" and client:
        logging.info(f"AI filtering {len(all_courses)} courses...")
        all_courses = ai_filter_and_rank(all_courses)

    # Save output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_courses, f, indent=2, ensure_ascii=False)

    logging.info(f"Process complete. {len(all_courses)} courses saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
