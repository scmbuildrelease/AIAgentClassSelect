from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

BAD_KEYWORDS = ["login", "sign", "menu", "account", "cart", "subscribe"]

# ---------- helpers ----------
def extract_age(text):
    text = text.lower()

    patterns = [
        r'(\d{1,2})\s*[-–]\s*(\d{1,2})',     # 6-8
        r'ages?\s*(\d{1,2})\s*[-–]\s*(\d{1,2})',
        r'(\d{1,2})\s*\+\s*',               # 6+
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group()

    return None


def extract_location(text):
    keywords = [
        "san jose", "cupertino", "santa clara",
        "bay area", "palo alto", "mountain view"
    ]

    text_lower = text.lower()

    for k in keywords:
        if k in text_lower:
            return k.title()

    return None


def extract_price(text):
    match = re.search(r'\$\d+', text)
    return match.group() if match else None


def extract_schedule(text):
    keywords = ["weekend", "weekday", "after school", "summer"]

    text_lower = text.lower()

    for k in keywords:
        if k in text_lower:
            return k

    return None


# ---------- main parser ----------
def parse_generic(html, category, base_url):
    soup = BeautifulSoup(html, "html.parser")
    courses = []

    for a in soup.select("a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        if not title or not href:
            continue

        # ---------- filtering ----------
        if len(title.split()) < 3:
            continue

        title_lower = title.lower()
        if any(k in title_lower for k in BAD_KEYWORDS):
            continue

        if href.startswith("#") or "javascript" in href.lower():
            continue

        full_link = urljoin(base_url, href)

        if not full_link.startswith("http"):
            continue

        # ---------- extract structured fields ----------
        combined_text = title + " " + a.parent.get_text(" ", strip=True)

        age = extract_age(combined_text)
        location = extract_location(combined_text)
        price = extract_price(combined_text)
        schedule = extract_schedule(combined_text)

        courses.append({
            "title": title,
            "link": full_link,
            "category": category,
            "age": age or "N/A",
            "location": location or "N/A",
            "price": price or "N/A",
            "schedule": schedule or "N/A",
            "score": 3
        })

    return courses[:30]
