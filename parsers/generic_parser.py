from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

BAD_KEYWORDS = ["login", "sign", "menu", "account", "cart", "subscribe"]

def extract_age(text):
    text = text.lower()
    patterns = [
        r'(\d{1,2})\s*[-–]\s*(\d{1,2})',
        r'ages?\s*(\d{1,2})\s*[-–]\s*(\d{1,2})',
        r'(\d{1,2})\s*\+'
    ]
    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group()
    return None

def extract_location(text):
    keywords = ["san jose", "cupertino", "santa clara", "bay area", "palo alto", "mountain view"]
    for k in keywords:
        if k in text.lower():
            return k.title()
    return None

def extract_price(text):
    match = re.search(r'\$\d+', text)
    return match.group() if match else None

def extract_schedule(text):
    keywords = ["weekend", "weekday", "after school", "summer"]
    for k in keywords:
        if k in text.lower():
            return k
    return None

def parse_generic(html, category, base_url):
    soup = BeautifulSoup(html, "html.parser")
    courses = []
    for a in soup.select("a"):
        title = a.get_text(strip=True)
        href = a.get("href")
        if not title or not href:
            continue
        if len(title.split()) < 3:
            continue
        if any(k in title.lower() for k in BAD_KEYWORDS):
            continue
        if href.startswith("#") or "javascript" in href.lower():
            continue
        full_link = urljoin(base_url, href)
        if not full_link.startswith("http"):
            continue
        combined_text = title + " " + a.parent.get_text(" ", strip=True)
        courses.append({
            "title": title,
            "link": full_link,
            "category": category,
            "age": extract_age(combined_text) or "N/A",
            "location": extract_location(combined_text) or "N/A",
            "price": extract_price(combined_text) or "N/A",
            "schedule": extract_schedule(combined_text) or "N/A",
            "score": 3
        })
    return courses[:30]
