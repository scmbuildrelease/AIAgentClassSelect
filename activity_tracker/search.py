"""Bilingual search and cross-language duplicate linking.

The glossary in config/settings.json maps concepts to English and Chinese terms
(e.g. robotics = 机器人). Matching is case-, width- and Simplified/Traditional-insensitive.
"""
import re
from urllib.parse import urlsplit

from .i18n import CJK_RE, lang_group, search_key
from .tracker import normalize_url

SEARCH_FIELDS = ("name", "description", "provider", "location", "page_title")


class Glossary:
    def __init__(self, entries: list[dict]):
        # (normalized term, concept key), longest first so 夏令营 wins over 营 and "summer camp" over "camp"
        self.terms = sorted(((search_key(t), e["key"]) for e in entries for t in e["terms"]),
                            key=lambda x: -len(x[0]))
        self.synonyms = {e["key"]: sorted({search_key(t) for t in e["terms"]}) for e in entries}

    def segment(self, text: str) -> tuple[set[str], list[str]]:
        """Split text into glossary concepts and leftover literal terms."""
        rest = search_key(text)
        concepts = set()
        for term, key in self.terms:
            if term and _contains(rest, term):
                concepts.add(key)
                rest = _remove(rest, term)
        leftovers = [w for w in re.split(r"[\s,，、/|()（）]+", rest) if w and (len(w) >= 2 or CJK_RE.match(w))]
        return concepts, leftovers


def _contains(haystack: str, term: str) -> bool:
    """CJK: substring. Latin: must start at a word boundary ('art' matches 'arts', not 'start')."""
    if CJK_RE.search(term):
        return term in haystack
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}", haystack) is not None


def _remove(haystack: str, term: str) -> str:
    if CJK_RE.search(term):
        return haystack.replace(term, " ")
    return re.sub(rf"(?<![a-z0-9]){re.escape(term)}[a-z]*", " ", haystack)


def record_text(rec: dict) -> str:
    parts = [rec.get(f) or "" for f in SEARCH_FIELDS]
    for tr in (rec.get("translations") or {}).values():
        parts += [tr.get("name") or "", tr.get("description") or ""]
    parts += rec.get("categories", [])
    return search_key(" ".join(parts))


def search(records: list[dict], query: str, glossary: Glossary, category_labels: dict | None = None) -> list[dict]:
    """All query concepts/terms must match (AND); each concept matches any of its synonyms.

    Results are ranked by matches in the title first.
    """
    concepts, words = glossary.segment(query)
    if not concepts and not words:
        return list(records)
    labels = category_labels or {}
    results = []
    for rec in records:
        text = record_text(rec) + " " + search_key(" ".join(labels.get(c, "") for c in rec.get("categories", [])))
        title = search_key(" ".join([rec.get("name") or ""] + [t.get("name") or "" for t in
                                                                (rec.get("translations") or {}).values()]))
        score = 0
        for key in concepts:
            syns = glossary.synonyms[key]
            if not any(_contains(text, s) for s in syns):
                break
            score += 2 if any(_contains(title, s) for s in syns) else 1
        else:
            if all(_contains(text, w) for w in words):
                results.append((score + sum(_contains(title, w) for w in words), rec))
    results.sort(key=lambda x: (-x[0], x[1].get("name") or ""))
    return [r for _, r in results]


def _site(url: str | None) -> str:
    return urlsplit(url or "").netloc.lower().removeprefix("www.")


def _price_amount(price: str | None) -> str | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", price or "")
    return m.group(0).replace(",", "") if m else None


def same_activity(a: dict, b: dict, glossary: Glossary) -> bool:
    """Conservative test that two records in different languages describe the same activity.

    Requires the same provider website and either the same registration link, or identical
    published dates and ages plus at least one shared glossary concept in the titles.
    Missing fields never count as a match.
    """
    la, lb = lang_group(a.get("original_language")), lang_group(b.get("original_language"))
    if not la or not lb or la == lb or "mixed" in (la, lb):
        return False
    if _site(a.get("source_url")) != _site(b.get("source_url")):
        return False
    ra, rb = normalize_url(a.get("registration_url")), normalize_url(b.get("registration_url"))
    if ra and ra == rb:
        return True
    for f in ("start_date", "end_date", "age_min", "age_max"):
        if a.get(f) is None or a.get(f) != b.get(f):
            return False
    pa, pb = _price_amount(a.get("price")), _price_amount(b.get("price"))
    if pa and pb and pa != pb:
        return False
    return bool(glossary.segment(a.get("name") or "")[0] & glossary.segment(b.get("name") or "")[0])


def link_aggregator_duplicates(recs: list[dict]) -> int:
    """An aggregator event whose original event URL is a page tracked directly from the provider
    (detail or registration URL) is the same activity: the provider's own record is primary.
    A URL shared by several provider records (one page listing several camps) is ambiguous: no link."""
    direct: dict[str, set] = {}
    by_id = {r["id"]: r for r in recs}
    for rec in recs:
        if rec.get("extraction") != "aggregator":
            for key in (rec.get("detail_url"), rec.get("registration_url")):
                if normalize_url(key):
                    direct.setdefault(normalize_url(key), set()).add(rec["id"])
    links = 0
    for rec in recs:
        ids: set[str] = set()
        if rec.get("extraction") == "aggregator":
            ids = direct.get(normalize_url(rec.get("original_event_url")), set())
        primary = by_id[next(iter(ids))] if len(ids) == 1 else None
        if primary and not primary.get("duplicate_of"):
            rec["duplicate_of"] = primary["id"]
            primary.setdefault("also_listed_by", []).append({"source_id": rec["source_id"], "record_id": rec["id"],
                                                            "url": rec.get("aggregator_url")})
            links += 1
    return links


def link_language_variants(store: dict, glossary: Glossary) -> int:
    """Link duplicates: aggregator listings of directly tracked events, then cross-language twins.

    Both records keep their own history; the secondary gets `duplicate_of`. For language twins the
    primary gets the secondary's original text as a provider translation.
    Recomputed from scratch each run, so it is idempotent. Returns the number of links."""
    recs = sorted(store["courses"].values(), key=lambda r: (r.get("first_seen") or "", r["id"]))
    for rec in recs:
        rec["duplicate_of"] = None
        rec.pop("also_listed_by", None)
        rec["translations"] = {k: v for k, v in (rec.get("translations") or {}).items()
                               if v.get("method") != "provider"}
    links = link_aggregator_duplicates(recs)
    for i, primary in enumerate(recs):
        if primary["duplicate_of"]:
            continue
        for other in recs[i + 1:]:
            if other["duplicate_of"] or not same_activity(primary, other, glossary):
                continue
            key = lang_group(other["original_language"])
            if key in primary["translations"]:
                continue
            other["duplicate_of"] = primary["id"]
            primary["translations"][key] = {
                "name": other.get("name"), "description": other.get("description"),
                "language": other["original_language"], "method": "provider",
                "record_id": other["id"], "url": other.get("detail_url")}
            links += 1
    return links
