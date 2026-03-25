from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_generic(html, category, base):
    soup = BeautifulSoup(html, "html.parser")
    courses = []

    for a in soup.select("a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        if not title or not href or len(title) < 8:
            continue

        if "login" in title.lower():
            continue

        courses.append({
            "title": title,
            "link": urljoin(base, href),
            "category": category,
            "score": 3
        })

    return courses[:20]
