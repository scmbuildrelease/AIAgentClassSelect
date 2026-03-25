from bs4 import BeautifulSoup
from urllib.parse import urljoin

BAD_KEYWORDS = ["login", "sign", "menu", "account", "cart", "subscribe"]

def parse_generic(html, category, base_url):
    soup = BeautifulSoup(html, "html.parser")
    courses = []

    for a in soup.select("a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        # ---------- basic validation ----------
        if not title or not href:
            continue

        # ---------- filter short / useless ----------
        if len(title.split()) < 3:
            continue

        # ---------- filter junk ----------
        title_lower = title.lower()
        if any(k in title_lower for k in BAD_KEYWORDS):
            continue

        # ---------- skip anchors / javascript ----------
        if href.startswith("#") or "javascript" in href.lower():
            continue

        # ---------- build full url ----------
        full_link = urljoin(base_url, href)

        # ---------- must be valid link ----------
        if not full_link.startswith("http"):
            continue

        courses.append({
            "title": title,
            "link": full_link,
            "category": category,
            "score": 3
        })

    return courses[:30]
