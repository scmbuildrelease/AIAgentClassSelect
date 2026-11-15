"""Turn fetched HTML into raw activity records.

Three strategies, recorded on each record as `extraction`:
  - "listing":   per-item CSS selectors configured for a known page layout
  - "json-ld":   schema.org Event/Course/Product data embedded by the site
  - "page_text": one program-level record per page, fields found by text patterns

Fields that cannot be found stay None (shown as "Not published"); nothing is guessed.
"""
import json
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

DASH = r"(?:-|–|—|to)"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
ORD = r"(?:st|nd|rd|th)?"
DAY = r"(?:Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)[a-z]*\.?"
AMPM = r"(?:am|pm|a\.m\.|p\.m\.)"
TIME = rf"\d{{1,2}}(?::\d{{2}})?\s*{AMPM}?"
TIME_END = rf"\d{{1,2}}(?::\d{{2}})?\s*{AMPM}"  # a time range must end with am/pm, so "6-9" is not a schedule

AGE_RANGE_RE = re.compile(rf"\bages?\s*(\d{{1,2}})\s*{DASH}\s*(\d{{1,2}})\b", re.I)
AGE_PLUS_RE = re.compile(r"\bages?\s*(\d{1,2})\s*(?:\+|and up|& up|and older)", re.I)
GRADE_RE = re.compile(
    rf"\bgrades?\s*:?\s*(TK|K|\d{{1,2}}){ORD}\s*{DASH}\s*(K|\d{{1,2}}){ORD}\b", re.I)
PRICE_RE = re.compile(
    r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?:\s*(?:-|–)\s*\$?\d{1,3}(?:,\d{3})*)?"
    r"(?:\s*(?:/|per)\s*(?:week|wk|session|class|month|day|year|semester|term))?", re.I)
PRICE_SKIP_RE = re.compile(r"(fee|discount|off\b|ext\s?care|extended|refund|cancel|save|donat|deposit|lab)", re.I)
DATE_RANGE_RE = re.compile(
    rf"({MONTH})\s+(\d{{1,2}}){ORD}(?:,?\s*(\d{{4}}))?\s*{DASH}\s*(?:({MONTH})\s+)?(\d{{1,2}}){ORD}(?:,?\s*(\d{{4}}))?", re.I)
NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/|\s+)(20\d{2})\b")
SCHEDULE_RE = re.compile(
    rf"(?:\b{DAY}(?:\s*(?:-|–|—|&|and|,|/)\s*{DAY})*[\s,:\[]*)?(?<![\d:])\b{TIME}\s*(?:-|–|—|to)\s*{TIME_END}", re.I)
ENROLLMENT_PATTERNS = [
    (re.compile(r"sold out", re.I), "Sold out"),
    (re.compile(r"no sessions available", re.I), "No sessions available"),
    (re.compile(r"(registration|enrollment)\s+(is\s+)?(now\s+)?closed", re.I), "Registration closed"),
    (re.compile(r"wait\s?list", re.I), "Waitlist mentioned"),
    (re.compile(rf"registration\s+(?:for [^.]{{0,40}}?)?opens?\s+(?:on\s+)?((?:{MONTH}\s+\d{{1,2}}(?:,\s*\d{{4}})?)|in\s+[A-Z][a-z]+)", re.I),
     "Registration opens {0}"),
    (re.compile(r"(registration|enrollment)\s+(is\s+)?(now\s+)?open\b|now enrolling", re.I), "Registration open"),
    (re.compile(r"register (now|today)", re.I), "Register link shown"),
]
SEASON_PATTERNS = [
    ("summer", re.compile(r"\bsummer\b", re.I)),
    ("winter", re.compile(r"\bwinter\b|holiday camp|winter break", re.I)),
    ("spring break", re.compile(r"spring break", re.I)),
    ("school break", re.compile(r"school break|break camp", re.I)),
]


def clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text.replace("​", "")).strip()
    return text or None


def _iso(year, month_name, day) -> str | None:
    month = MONTHS.get(month_name[:3].lower())
    try:
        return date(int(year), month, int(day)).isoformat() if year and month else None
    except ValueError:
        return None


def parse_age(text: str) -> tuple[str | None, int | None, int | None, str | None]:
    """Return (age_text, min, max, basis). Grades are converted to approximate ages."""
    if not text:
        return None, None, None, None
    for m in AGE_RANGE_RE.finditer(text):
        lo, hi = int(m.group(1)), int(m.group(2))
        if 0 < lo <= hi <= 21:
            return clean(m.group(0)), lo, hi, "age"
    m = AGE_PLUS_RE.search(text)
    if m:
        return clean(m.group(0)), int(m.group(1)), None, "age"
    m = GRADE_RE.search(text)
    if m:
        def grade(g, upper):
            g = g.upper()
            base = {"TK": 4, "K": 5}.get(g, int(g) + 5 if g.isdigit() else None)
            return None if base is None else base + (1 if upper else 0)
        lo, hi = grade(m.group(1), False), grade(m.group(2), True)
        if lo is not None and hi is not None and lo < hi:
            return clean(m.group(0)), lo, hi, "grade"
    return None, None, None, None


def find_price(text: str) -> str | None:
    for m in PRICE_RE.finditer(text or ""):
        # look only at nearby words in the same sentence: "fee $25. Tuition: $300" -> $300
        before = re.split(r"[.;!?]\s", text[max(0, m.start() - 30):m.start()])[-1]
        after = re.split(r"[.;!?]\s", text[m.end():m.end() + 20])[0]
        if not PRICE_SKIP_RE.search(f"{before} {after}"):
            return clean(m.group(0))
    return None


def find_dates(text: str) -> tuple[str | None, str | None]:
    """First date range in text. ISO dates when a year is published, else the text as published."""
    m = DATE_RANGE_RE.search(text or "")
    if m:
        m1, d1, y1, m2, d2, y2 = m.groups()
        m2 = m2 or m1
        year1 = y1 or y2
        start = _iso(year1, m1, d1) or clean(f"{m1} {d1}")
        end = _iso(y2 or year1, m2, d2) or clean(f"{m2} {d2}")
        return start, end
    nums = [date(int(y), int(mo), int(d)) for mo, d, y in NUMERIC_DATE_RE.findall(text or "")
            if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31]
    if nums:
        return min(nums).isoformat(), max(nums).isoformat()
    return None, None


def find_schedule(text: str) -> str | None:
    m = SCHEDULE_RE.search(text or "")
    return clean(m.group(0).strip(" ,:[")) if m else None


def find_enrollment(text: str) -> str | None:
    for pattern, label in ENROLLMENT_PATTERNS:
        m = pattern.search(text or "")
        if m:
            return label.format(*(clean(g) for g in m.groups() if g)) if "{0}" in label else label
    return None


def detect_season(*texts: str | None) -> str | None:
    joined = " ".join(t for t in texts if t)
    for season, pattern in SEASON_PATTERNS:
        if pattern.search(joined):
            return season
    return None


def detect_cities(text: str, cities: list[str]) -> list[str]:
    lowered = (text or "").lower()
    return [c for c in cities if c.lower() in lowered]


def _main_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "aside", "svg"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    return clean(root.get_text(" ")) or ""


def _meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            return clean(tag["content"])
    return None


def _page_title(soup: BeautifulSoup) -> str | None:
    return clean(soup.title.get_text()) if soup.title else None


def strip_site_suffix(title: str | None, provider: str) -> str | None:
    """'Summer Camp - Western Ballet' -> 'Summer Camp' (only drops segments naming the provider)."""
    if not title:
        return title
    parts = re.split(r"\s+[|–—-]\s+", title)
    prov = provider.casefold()
    while len(parts) > 1 and (parts[-1].casefold() in prov or prov in parts[-1].casefold()):
        parts.pop()
    return " - ".join(parts)


def _base_record(source, page_url: str, page_title: str | None) -> dict:
    return {
        "source_id": source.id, "provider": source.provider, "categories": list(source.categories),
        "program_type": source.program_type, "source_url": source.url, "detail_url": None,
        "page_title": page_title, "name": None, "age_text": None, "age_min": None, "age_max": None,
        "age_basis": None, "location": None, "schedule": None, "sessions": [], "start_date": None,
        "end_date": None, "price": None, "enrollment_status": None, "description": None,
        "season": source.season,
    }


def _finish(rec: dict, source, text: str, cities: list[str]) -> dict:
    """Fill fields shared by all strategies; never overwrite values a strategy already found."""
    if rec["age_text"] is None:
        rec["age_text"], rec["age_min"], rec["age_max"], rec["age_basis"] = parse_age(text)
    if rec["location"] is None:
        found = detect_cities(text, cities)
        if source.city and not source.city.lower().startswith("multiple"):
            rec["location"] = source.city
        elif found:
            rec["location"] = ", ".join(found[:6])
        else:
            rec["location"] = source.city or None
    rec["season"] = rec["season"] or detect_season(rec["name"], rec["page_title"])
    if rec["season"] and rec["program_type"] == "program_info":
        rec["program_type"] = "seasonal_program"
    if rec["description"] and len(rec["description"]) > 400:
        rec["description"] = rec["description"][:397].rstrip() + "..."
    return rec


def _select_value(item: Tag, spec: str, base_url: str, many: bool = False):
    """spec: 'css' -> text, 'css@attr' -> attribute, '@attr' -> attribute of the item itself."""
    selector, _, attr = spec.partition("@")
    nodes = item.select(selector) if selector else [item]
    values = []
    for node in nodes:
        v = node.get(attr) if attr else node.get_text(" ")
        if attr in ("href", "src") and v:
            v = urljoin(base_url, v)
        v = clean(v)
        if v:
            values.append(v)
    return values if many else (values[0] if values else None)


def extract_listing(soup: BeautifulSoup, source, page_url: str, cities: list[str]) -> list[dict]:
    cfg = source.listing
    page_title = _page_title(soup)
    records = []
    for item in soup.select(cfg["item"]):
        rec = _base_record(source, page_url, page_title)
        rec["extraction"] = "listing"
        rec["name"] = _select_value(item, cfg.get("title", "h2, h3"), page_url)
        if not rec["name"]:
            continue
        if cfg.get("link"):
            rec["detail_url"] = _select_value(item, cfg["link"], page_url)
        fields = cfg.get("fields", {})
        if "sessions" in fields:
            rec["sessions"] = _select_value(item, fields["sessions"], page_url, many=True)
        for key in ("age_text", "price", "schedule", "enrollment_status", "description", "location"):
            if key in fields:
                rec[key] = _select_value(item, fields[key], page_url)
        if rec["price"] and re.fullmatch(r"\d[\d,]*(\.\d\d)?", rec["price"]):
            rec["price"] = f"${rec['price']}"
        item_text = clean(item.get_text(" ")) or ""
        if rec["enrollment_status"]:
            rec["enrollment_status"] = find_enrollment(rec["enrollment_status"]) or rec["enrollment_status"]
        else:
            rec["enrollment_status"] = find_enrollment(item_text)
        if rec["age_text"]:
            _, rec["age_min"], rec["age_max"], rec["age_basis"] = parse_age(rec["age_text"])
        rec["start_date"], rec["end_date"] = find_dates(" ".join(rec["sessions"]) or item_text)
        if rec["location"] is None and rec["sessions"]:
            places = [m.group(1) for s in rec["sessions"] for m in [re.search(r"\bAt (.+)$", s)] if m]
            rec["location"] = "; ".join(dict.fromkeys(places)) or None
        records.append(_finish(rec, source, item_text, cities))
    return records


def _jsonld_items(soup: BeautifulSoup) -> list[dict]:
    items = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            obj = stack.pop(0)
            if isinstance(obj, dict):
                if "@graph" in obj:
                    stack.extend(obj["@graph"])
                types = obj.get("@type")
                types = types if isinstance(types, list) else [types]
                if any(t in ("Event", "Course", "CourseInstance", "EducationEvent", "Product") for t in types):
                    items.append(obj)
    return items


def extract_jsonld(soup: BeautifulSoup, source, page_url: str, cities: list[str]) -> list[dict]:
    page_title = _page_title(soup)
    records = []
    for obj in _jsonld_items(soup):
        rec = _base_record(source, page_url, page_title)
        rec["extraction"] = "json-ld"
        rec["name"] = clean(str(obj.get("name") or ""))
        if not rec["name"]:
            continue
        url = obj.get("url")
        rec["detail_url"] = urljoin(page_url, url) if isinstance(url, str) else None
        rec["description"] = clean(BeautifulSoup(str(obj.get("description") or ""), "html.parser").get_text(" "))
        rec["start_date"] = (obj.get("startDate") or "")[:10] or None
        rec["end_date"] = (obj.get("endDate") or "")[:10] or None
        loc = obj.get("location")
        if isinstance(loc, dict):
            rec["location"] = clean(loc.get("name"))
        offers = obj.get("offers")
        offer = offers[0] if isinstance(offers, list) and offers else offers
        if isinstance(offer, dict) and offer.get("price") not in (None, ""):
            rec["price"] = f"{offer.get('priceCurrency', 'USD')} {offer['price']}".replace("USD ", "$")
            avail = str(offer.get("availability", "")).rsplit("/", 1)[-1]
            rec["enrollment_status"] = {"InStock": "Registration open", "SoldOut": "Sold out",
                                        "PreOrder": "Registration not yet open"}.get(avail)
        text = " ".join(filter(None, [rec["name"], rec["description"], str(obj.get("typicalAgeRange") or "")]))
        if obj.get("typicalAgeRange"):
            rec["age_text"], rec["age_min"], rec["age_max"], rec["age_basis"] = parse_age(
                f"ages {obj['typicalAgeRange']}")
        records.append(_finish(rec, source, text, cities))
    return records


def extract_page(soup: BeautifulSoup, source, page_url: str, cities: list[str]) -> list[dict]:
    page_title = _page_title(soup)
    h1 = next((h for h in soup.find_all("h1") if not h.find_parent(["header", "nav", "footer"])),
              soup.find("h1"))
    h1_text = clean(h1.get_text(" ")) if h1 else None
    og_title = _meta(soup, "og:title")
    description = _meta(soup, "description", "og:description")
    text = _main_text(soup)
    rec = _base_record(source, page_url, page_title)
    rec["extraction"] = "page_text"
    rec["name"] = source.course_name or h1_text or strip_site_suffix(og_title or page_title, source.provider)
    if not rec["name"] or not text:
        return []
    rec["detail_url"] = page_url
    rec["description"] = description or next(
        (p for p in (clean(p.get_text(" ")) for p in soup.find_all("p")) if p and len(p) > 80), None)
    rec["price"] = find_price(text)
    rec["start_date"], rec["end_date"] = find_dates(text)
    rec["schedule"] = find_schedule(text)
    rec["enrollment_status"] = find_enrollment(text)
    age_text = parse_age(text)
    if age_text[0] is None and description:
        age_text = parse_age(description)
    rec["age_text"], rec["age_min"], rec["age_max"], rec["age_basis"] = age_text
    return [_finish(rec, source, text, cities)]


def extract(html: str, source, page_url: str, cities: list[str]) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    if source.parser == "listing":
        base = soup.find("base", href=True)  # relative links resolve against <base href>, as browsers do
        return extract_listing(soup, source, urljoin(page_url, base["href"]) if base else page_url, cities)
    structured = extract_jsonld(soup, source, page_url, cities)
    return structured or extract_page(soup, source, page_url, cities)
