"""Suggest new source pages by scanning links on known provider pages.

Candidates are only *suggestions* saved to data/candidate_sources.json for review;
nothing is added to config/sources.json automatically.
"""
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .extract import clean
from .i18n import CJK_RE
from .tracker import normalize_url

EXCLUDE_RE = re.compile(
    r"(login|log-in|signin|account|cart|checkout|donat|give\.|jobs?\b|employment|careers?|volunteer|"
    r"privacy|terms|mailto:|tel:|facebook|instagram|twitter|youtube|linkedin|tiktok|\.pdf$|"
    r"birthday|wp-content)", re.I)


def _word(term: str) -> str:
    """Word-start match for English; plain substring for Chinese (no spaces between words)."""
    return re.escape(term) if CJK_RE.search(term) else rf"\b{re.escape(term)}"


def find_candidates(html: str, page_url: str, settings: dict, categories: dict) -> list[dict]:
    disc = settings.get("discovery", {})
    program_re = re.compile("|".join(_word(w) for w in disc.get("program_words", [])) or r"(?!)", re.I)
    soup = BeautifulSoup(html, "html.parser")
    site = urlsplit(page_url).netloc.removeprefix("www.")
    base = soup.find("base", href=True)
    base_url = urljoin(page_url, base["href"]) if base else page_url
    found: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].strip())
        text = clean(a.get_text(" ")) or ""
        parts = urlsplit(href)
        if parts.scheme not in ("http", "https") or parts.netloc.removeprefix("www.") != site:
            continue
        haystack = f"{text} {parts.path}"
        if EXCLUDE_RE.search(href) or EXCLUDE_RE.search(text) or not program_re.search(haystack):
            continue
        cats = [key for key, cat in categories.items()
                if any(re.search(_word(k), haystack, re.I) for k in cat.get("keywords", []))]
        key = normalize_url(href)
        if key and key not in found and key != normalize_url(page_url):
            found[key] = {"url": href.split("#")[0], "anchor_text": text[:120], "suggested_categories": cats}
        if len(found) >= disc.get("max_candidates_per_page", 15):
            break
    return list(found.values())


def merge_candidates(state: dict, found: list[dict], found_on: str, known_urls: set[str], today: str) -> list[dict]:
    """Add unseen candidates; return the ones that are new this run."""
    new = []
    for cand in found:
        key = normalize_url(cand["url"])
        if key in known_urls:
            continue
        if key in state["candidates"]:
            state["candidates"][key]["last_seen"] = today
            continue
        entry = {**cand, "found_on": found_on, "first_seen": today, "last_seen": today, "status": "needs_review"}
        state["candidates"][key] = entry
        new.append(entry)
    return new
