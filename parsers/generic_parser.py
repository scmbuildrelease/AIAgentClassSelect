from bs4 import BeautifulSoup

def parse_generic(html, category):
    soup = BeautifulSoup(html, "html.parser")
    courses = []

    # fallback strategy: extract links + text
    for link in soup.select("a"):
        title = link.get_text(strip=True)
        href = link.get("href")

        if not title or not href:
            continue

        # simple filtering (avoid nav links)
        if len(title) < 5:
            continue

        courses.append({
            "title": title,
            "age": "N/A",
            "location": "N/A",
            "link": href,
            "category": category
        })

    return courses[:20]  # limit noise
