"""Turn fetched HTML (or poster images) into raw activity records.

Strategies, recorded on each record as `extraction`:
  - "listing":   per-item CSS selectors configured for a known page layout
  - "json-ld":   schema.org Event/Course/Product data embedded by the site
  - "page_text": one program-level record per page, fields found by text patterns
  - "ocr":       one record per poster image, fields found by the same text patterns

Patterns cover English, Simplified and Traditional Chinese, and mixed text. When several
patterns match, the one appearing first in the text wins. Fields that cannot be found stay
None (shown as "Not published"); nothing is guessed. Titles and descriptions are kept as
published (only whitespace runs are collapsed); `original_language` records their language.
"""
import json
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .i18n import detect_language, lang_group

DASH = r"(?:-|–|—|~|to)"
ZDASH = r"(?:-|–|—|~|至|到)"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
ORD = r"(?:st|nd|rd|th)?"
DAY = r"(?:Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)[a-z]*\.?"
AMPM = r"(?:am|pm|a\.m\.|p\.m\.)"
TIME = rf"\d{{1,2}}(?::\d{{2}})?\s*{AMPM}?"
TIME_END = rf"\d{{1,2}}(?::\d{{2}})?\s*{AMPM}"  # a time range must end with am/pm, so "6-9" is not a schedule
CNUM = r"(\d{1,2}|[一二两三四五六七八九十]{1,3})"
CN_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
SUI = r"(?:周岁|週歲|岁|歲)"
ZH_DAY = r"(?:周|週|星期|礼拜|禮拜)[一二三四五六日天]"
ZH_TIME = r"(?:上午|下午|晚上|中午|早上)?\s*\d{1,2}(?:\s*:\s*\d{2}|\s*[点點时時](?:\s*\d{1,2}\s*分|半)?)"

AGE_RANGE_RE = re.compile(rf"\bages?\s*(\d{{1,2}})\s*{DASH}\s*(\d{{1,2}})\b", re.I)
AGE_PLUS_RE = re.compile(r"\bages?\s*(\d{1,2})\s*(?:\+|and up|& up|and older)", re.I)
GRADE_RE = re.compile(rf"\bgrades?\s*:?\s*(TK|K|\d{{1,2}}){ORD}\s*{DASH}\s*(K|\d{{1,2}}){ORD}\b", re.I)
AGE_ZH_RANGE_RE = re.compile(rf"(?<![\d.]){CNUM}\s*{SUI}?\s*{ZDASH}\s*{CNUM}\s*{SUI}")
AGE_ZH_PLUS_RE = re.compile(rf"(?<![\d.]){CNUM}\s*{SUI}\s*(?:及以上|或以上|以上|\+)")
AGE_ZH_UNDER_RE = re.compile(rf"(?<![\d.]){CNUM}\s*{SUI}\s*(?:及以下|或以下|以下)")
GRADE_ZH_RE = re.compile(
    rf"(TK|K|幼儿园|幼兒園|\d{{1,2}}|[一二三四五六七八九十]{{1,2}})\s*(?:年级|年級)?\s*{ZDASH}\s*"
    rf"(K|\d{{1,2}}|[一二三四五六七八九十]{{1,2}})\s*(?:年级|年級)")

PRICE_UNIT = r"(?:week|wk|session|class|month|day|year|semester|term|周|週|星期|节|節|课|課|堂|月|天|期|学期|學期)"
PRICE_RE = re.compile(
    r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?:\s*(?:-|–)\s*\$?\d{1,3}(?:,\d{3})*)?"
    rf"(?:\s*(?:/|per|每)\s*{PRICE_UNIT})?", re.I)
PRICE_ZH_RE = re.compile(rf"(?<![\d.,])\d{{1,3}}(?:,\d{{3}})*(?:\.\d{{2}})?\s*(?:美元|美金|元)(?:\s*/\s*{PRICE_UNIT})?")
PRICE_FREE_RE = re.compile(r"(?:学费|學費|费用|費用|价格|價格|收费|收費)\s*:?\s*(免费|免費)|(?:tuition|cost|price)\s*:?\s*(free)\b", re.I)
PRICE_SKIP_RE = re.compile(
    r"(fee|discount|off\b|ext\s?care|extended|refund|cancel|save|donat|deposit|lab|"
    r"报名费|報名費|注册费|註冊費|手续费|手續費|材料费|材料費|折扣|优惠|優惠|退款|押金|订金|訂金|托管|延时|延時)", re.I)

DATE_RANGE_RE = re.compile(
    rf"({MONTH})\s+(\d{{1,2}}){ORD}(?:,?\s*(\d{{4}}))?\s*{DASH}\s*(?:({MONTH})\s+)?(\d{{1,2}}){ORD}(?:,?\s*(\d{{4}}))?", re.I)
DATE_ZH_RE = re.compile(
    rf"(?:(\d{{4}})\s*年\s*)?(\d{{1,2}})\s*月\s*(\d{{1,2}})\s*[日号號]?\s*(?:\([^)]{{1,4}}\))?\s*{ZDASH}\s*"
    rf"(?:(\d{{4}})\s*年\s*)?(?:(\d{{1,2}})\s*月\s*)?(\d{{1,2}})\s*[日号號]")
NUMERIC_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/|\s+)(20\d{2})(?!\d)")
YMD_DATE_RE = re.compile(r"(?<!\d)(20\d{2})[/.-](\d{1,2})[/.-](\d{1,2})(?!\d)")

SCHEDULE_RE = re.compile(
    rf"(?:\b{DAY}(?:\s*(?:-|–|—|&|and|,|/)\s*{DAY})*[\s,:\[]*)?(?<![\d:])\b{TIME}\s*(?:-|–|—|to)\s*{TIME_END}", re.I)
SCHEDULE_ZH_RE = re.compile(
    rf"(?:(?:每\s*)?{ZH_DAY}(?:\s*{ZDASH}\s*{ZH_DAY}|\s*[、和及]\s*(?:{ZH_DAY}|[一二三四五六日天]))*\s*[,:]?\s*)?"
    rf"(?<![\d:]){ZH_TIME}\s*{ZDASH}\s*{ZH_TIME}")

ENROLLMENT_PATTERNS = [
    (re.compile(r"sold out|名额已满|名額已滿|额满|額滿|已满员|已滿員|售罄", re.I), "Sold out"),
    (re.compile(r"no sessions available", re.I), "No sessions available"),
    (re.compile(r"(registration|enrollment)\s+(is\s+)?(now\s+)?closed|"
                r"报名已截止|報名已截止|停止报名|停止報名|报名已结束|報名已結束|报名已关闭|報名已關閉", re.I),
     "Registration closed"),
    (re.compile(r"wait\s?list|候补|候補|等候名单|等候名單", re.I), "Waitlist mentioned"),
    (re.compile(rf"registration\s+(?:for [^.]{{0,40}}?)?opens?\s+(?:on\s+)?((?:{MONTH}\s+\d{{1,2}}(?:,\s*\d{{4}})?)|in\s+[A-Z][a-z]+)", re.I),
     "Registration opens {0}"),
    (re.compile(r"((?:\d{4}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*[日号號]?)\s*(?:起\s*)?(?:开始|開始|开放|開放)\s*(?:报名|報名)|"
                r"(?:报名|報名)\s*(?:将|將)?\s*于?\s*((?:\d{4}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*[日号號]?)\s*(?:开始|開始|开放|開放)"),
     "Registration opens {0}"),
    (re.compile(r"(registration|enrollment)\s+(is\s+)?(now\s+)?open\b|now enrolling|"
                r"报名中|報名中|正在报名|正在報名|现正报名|現正報名|开放报名|開放報名|接受报名|接受報名", re.I),
     "Registration open"),
    (re.compile(r"register (now|today)|立即报名|立即報名|马上报名|馬上報名|点击报名|點擊報名|在线报名|線上報名", re.I),
     "Register link shown"),
]
SEASON_PATTERNS = [
    ("summer", re.compile(r"\bsummer\b|夏令营|夏令營|暑期|暑假|夏季", re.I)),
    ("winter", re.compile(r"\bwinter\b|holiday camp|winter break|冬令营|冬令營|寒假|冬季", re.I)),
    ("spring break", re.compile(r"spring break|春假", re.I)),
    ("school break", re.compile(r"school break|break camp", re.I)),
]
REGISTER_TEXT_RE = re.compile(r"regist|enroll|sign\s*up|报名|報名|注册|註冊", re.I)
URL_IN_TEXT_RE = re.compile(r"https?://[^\s<>\"'，。、）)]+")


def clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text.replace("​", "")).strip()
    return text or None


def _nfkc(text: str | None) -> str:
    """Width-normalize for matching only (full-width digits, colons, tildes -> ASCII)."""
    return unicodedata.normalize("NFKC", text or "")


def _first(*matches):
    """Earliest match in the text (longest on ties)."""
    found = [m for m in matches if m]
    return min(found, key=lambda m: (m.start(), -len(m.group(0)))) if found else None


def cn_int(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + CN_DIGITS.get(s[1:], 0)
    if "十" in s:
        tens, _, ones = s.partition("十")
        return CN_DIGITS.get(tens, 0) * 10 + (CN_DIGITS.get(ones, 0) if ones else 0)
    return CN_DIGITS.get(s)


def _iso(year, month, day) -> str | None:
    month = month if isinstance(month, int) else (int(month) if str(month).isdigit()
                                                 else MONTHS.get(str(month)[:3].lower()))
    try:
        return date(int(year), month, int(day)).isoformat() if year and month else None
    except ValueError:
        return None


def _grade_age(g: str, upper: bool) -> int | None:
    g = g.upper()
    if g in ("TK",):
        base = 4
    elif g in ("K", "幼儿园", "幼兒園"):
        base = 5
    else:
        n = cn_int(g)
        base = None if n is None else n + 5
    return None if base is None else base + (1 if upper else 0)


def _age_candidates(text: str):
    """Yield (match, min, max, basis) for every valid age/grade statement."""
    for m in AGE_RANGE_RE.finditer(text):
        yield m, int(m.group(1)), int(m.group(2)), "age"
    for m in AGE_PLUS_RE.finditer(text):
        yield m, int(m.group(1)), None, "age"
    for m in AGE_ZH_RANGE_RE.finditer(text):
        yield m, cn_int(m.group(1)), cn_int(m.group(2)), "age"
    for m in AGE_ZH_PLUS_RE.finditer(text):
        yield m, cn_int(m.group(1)), None, "age"
    for m in AGE_ZH_UNDER_RE.finditer(text):
        yield m, None, cn_int(m.group(1)), "age"
    for regex in (GRADE_RE, GRADE_ZH_RE):
        for m in regex.finditer(text):
            yield m, _grade_age(m.group(1), False), _grade_age(m.group(2), True), "grade"


def parse_age(text: str) -> tuple[str | None, int | None, int | None, str | None]:
    """Return (age_text, min, max, basis) for the first age statement in the text.

    Grades are converted to approximate ages. Implausible ranges ("ages 18 months to 9") are skipped.
    """
    text = _nfkc(text)
    valid = []
    for m, lo, hi, basis in _age_candidates(text):
        if lo is None and hi is None:
            continue
        if (lo is not None and not 0 < lo <= 21) or (hi is not None and not 0 < hi <= 21):
            continue
        if lo is not None and hi is not None and (lo > hi or (basis == "grade" and lo == hi)):
            continue
        valid.append((m, lo, hi, basis))
    if not valid:
        return None, None, None, None
    m, lo, hi, basis = min(valid, key=lambda v: (v[0].start(), -len(v[0].group(0))))
    return clean(m.group(0)), lo, hi, basis


def find_price(text: str) -> str | None:
    text = _nfkc(text)
    candidates = []
    for regex in (PRICE_RE, PRICE_ZH_RE):
        for m in regex.finditer(text):
            # look only at nearby words in the same clause: "fee $25. Tuition: $300" -> $300,
            # "学费:$450/周(报名费$25)" -> $450/周
            before = re.split(r"[.;!?。;!?,，)]\s?", text[max(0, m.start() - 30):m.start()])[-1]
            after = re.split(r"[.;!?。;!?,，(]", text[m.end():m.end() + 20])[0]
            if not PRICE_SKIP_RE.search(f"{before} {after}"):
                candidates.append(m)
                break
    m = _first(*candidates, PRICE_FREE_RE.search(text))
    if m is None:
        return None
    if m.re is PRICE_FREE_RE:
        return clean(m.group(1) or m.group(2))
    return clean(m.group(0))


def _en_range(m) -> tuple[str, str]:
    m1, d1, y1, m2, d2, y2 = m.groups()
    m2 = m2 or m1
    year1 = y1 or y2
    return (_iso(year1, m1, d1) or clean(f"{m1} {d1}"), _iso(y2 or year1, m2, d2) or clean(f"{m2} {d2}"))


def _zh_range(m) -> tuple[str, str]:
    y1, mo1, d1, y2, mo2, d2 = m.groups()
    mo2 = mo2 or mo1
    year1 = y1 or y2
    return (_iso(year1, int(mo1), d1) or f"{int(mo1)}月{int(d1)}日",
            _iso(y2 or year1, int(mo2), d2) or f"{int(mo2)}月{int(d2)}日")


def find_dates(text: str) -> tuple[str | None, str | None]:
    """First date range in text. ISO dates when a year is published, else the text as published.

    Single dates are ignored on purpose: alone they are often deadlines or "updated on" dates.
    """
    text = _nfkc(text)
    m = _first(DATE_RANGE_RE.search(text), DATE_ZH_RE.search(text))
    if m:
        return _en_range(m) if m.re is DATE_RANGE_RE else _zh_range(m)
    nums = [(int(y), int(mo), int(d)) for mo, d, y in NUMERIC_DATE_RE.findall(text)]
    nums += [(int(y), int(mo), int(d)) for y, mo, d in YMD_DATE_RE.findall(text)]
    dates = []
    for y, mo, d in nums:
        try:
            dates.append(date(y, mo, d))
        except ValueError:
            continue
    if dates:
        return min(dates).isoformat(), max(dates).isoformat()
    return None, None


def find_schedule(text: str) -> str | None:
    text = _nfkc(text)
    m = _first(SCHEDULE_RE.search(text), SCHEDULE_ZH_RE.search(text))
    return clean(m.group(0).strip(" ,:[")) if m else None


def find_enrollment(text: str) -> str | None:
    text = _nfkc(text)
    for pattern, label in ENROLLMENT_PATTERNS:
        m = pattern.search(text)
        if m:
            return label.format(*(clean(g) for g in m.groups() if g)) if "{0}" in label else label
    return None


def detect_season(*texts: str | None) -> str | None:
    joined = " ".join(t for t in texts if t)
    for season, pattern in SEASON_PATTERNS:
        if pattern.search(joined):
            return season
    return None


def city_table(cities) -> dict[str, list[str]]:
    """Accept a plain city list or {city: [aliases...]} (e.g. "San Jose": ["圣何塞", "聖荷西"])."""
    if isinstance(cities, dict):
        return {c: [c, *aliases] for c, aliases in cities.items()}
    return {c: [c] for c in cities or []}


def detect_cities(text: str, cities) -> list[str]:
    lowered = (text or "").lower()
    return [c for c, names in city_table(cities).items() if any(n.lower() in lowered for n in names)]


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


def find_registration_url(root, base_url: str) -> str | None:
    """First link whose text says register / enroll / 报名, as an absolute http(s) URL."""
    for a in root.find_all("a", href=True):
        if REGISTER_TEXT_RE.search(a.get_text(" ") or "") or REGISTER_TEXT_RE.search(a.get("title", "")):
            href = urljoin(base_url, a["href"].strip())
            if href.startswith(("http://", "https://")) and href.split("#")[0].rstrip("/") != base_url.rstrip("/"):
                return href
    return None


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
        "registration_url": None, "season": source.season,
    }


def _finish(rec: dict, source, text: str, cities) -> dict:
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
    rec["original_language"] = detect_language(rec["name"], rec["description"])
    # human-written translations from config; the original name/description are never replaced
    rec["translations"] = {lang_group(k) or k: {"method": "manual", **v}
                           for k, v in (getattr(source, "translations", None) or {}).items()}
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


def extract_listing(soup: BeautifulSoup, source, page_url: str, cities) -> list[dict]:
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
        for key in ("age_text", "price", "schedule", "enrollment_status", "description", "location",
                    "registration_url"):
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


def extract_jsonld(soup: BeautifulSoup, source, page_url: str, cities) -> list[dict]:
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
        if isinstance(offer, dict):
            if offer.get("price") not in (None, ""):
                rec["price"] = f"{offer.get('priceCurrency', 'USD')} {offer['price']}".replace("USD ", "$")
                avail = str(offer.get("availability", "")).rsplit("/", 1)[-1]
                rec["enrollment_status"] = {"InStock": "Registration open", "SoldOut": "Sold out",
                                            "PreOrder": "Registration not yet open"}.get(avail)
            if isinstance(offer.get("url"), str):
                rec["registration_url"] = urljoin(page_url, offer["url"])
        text = " ".join(filter(None, [rec["name"], rec["description"], str(obj.get("typicalAgeRange") or "")]))
        if obj.get("typicalAgeRange"):
            rec["age_text"], rec["age_min"], rec["age_max"], rec["age_basis"] = parse_age(
                f"ages {obj['typicalAgeRange']}")
        records.append(_finish(rec, source, text, cities))
    return records


def _text_fields(rec: dict, text: str, description: str | None) -> None:
    rec["price"] = find_price(text)
    rec["start_date"], rec["end_date"] = find_dates(text)
    rec["schedule"] = find_schedule(text)
    rec["enrollment_status"] = find_enrollment(text)
    age = parse_age(text)
    if age[0] is None and description:
        age = parse_age(description)
    rec["age_text"], rec["age_min"], rec["age_max"], rec["age_basis"] = age


def extract_page(soup: BeautifulSoup, source, page_url: str, cities) -> list[dict]:
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
    _text_fields(rec, text, description)
    rec["registration_url"] = find_registration_url(soup.find("main") or soup.body or soup, page_url)
    return [_finish(rec, source, text, cities)]


def extract_poster(content: bytes, source, page_url: str, cities) -> list[dict]:
    from .ocr import ocr_image  # optional: only needed for poster sources

    raw = ocr_image(content)
    lines = [clean(line) for line in raw.splitlines()]
    lines = [line for line in lines if line and len(line) >= 2]
    text = " ".join(lines)
    if not text:
        return []
    rec = _base_record(source, page_url, None)
    rec["extraction"] = "ocr"
    rec["name"] = source.course_name or lines[0]
    rec["detail_url"] = page_url
    rec["description"] = text  # the poster's own text (OCR), kept as the original
    _text_fields(rec, text, None)
    url = URL_IN_TEXT_RE.search(text)  # only complete http(s) URLs; a bare domain is left in the text
    rec["registration_url"] = url.group(0) if url else None
    return [_finish(rec, source, text, cities)]


def extract(html: str, source, page_url: str, cities, content: bytes = b"") -> list[dict]:
    if source.parser == "poster":
        return extract_poster(content, source, page_url, cities)
    soup = BeautifulSoup(html, "html.parser")
    if source.parser == "listing":
        base = soup.find("base", href=True)  # relative links resolve against <base href>, as browsers do
        return extract_listing(soup, source, urljoin(page_url, base["href"]) if base else page_url, cities)
    structured = extract_jsonld(soup, source, page_url, cities)
    return structured or extract_page(soup, source, page_url, cities)
