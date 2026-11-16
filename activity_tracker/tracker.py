"""Stable IDs, deterministic comparison and persistent state (data/*.json)."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

NEW, UPDATED, UNCHANGED, NOT_FOUND, FETCH_FAILED = "NEW", "UPDATED", "UNCHANGED", "NOT_FOUND", "FETCH_FAILED"

# Only these fields decide whether an activity "changed". Timestamps, page titles and
# extraction metadata are deliberately excluded.
COMPARE_FIELDS = ["name", "age_text", "location", "schedule", "sessions", "start_date", "end_date",
                  "price", "enrollment_status", "description", "registration_url", "campus"]
HISTORY_LIMIT = 10
TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_|_ga)", re.I)


def normalize_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(normalize_text(v) for v in value)
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"[‐-―−]", "-", text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not TRACKING_PARAMS.match(k)))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower().removeprefix("www."), path, query, ""))


def make_id(source_id: str, detail_url: str | None, name: str | None, disambiguator: str = "") -> str:
    """Stable ID from source + normalized detail URL + normalized name.

    The name is included because several activities can share one listing page URL;
    it is never used alone.
    """
    key = "|".join([source_id, normalize_url(detail_url), normalize_text(name), disambiguator])
    return f"{source_id}-{hashlib.sha1(key.encode()).hexdigest()[:10]}"


def assign_ids(records: list[dict]) -> list[dict]:
    """Campus is part of the key, so one program offered at several campuses keeps stable IDs
    (records without a campus get the same IDs as before campuses existed)."""
    seen: dict[str, int] = {}
    for rec in records:
        campus = rec.get("campus") or ""
        base = make_id(rec["source_id"], rec.get("detail_url"), rec.get("name"), campus)
        n = seen.get(base, 0) + 1
        seen[base] = n
        rec["id"] = base if n == 1 else make_id(rec["source_id"], rec.get("detail_url"), rec.get("name"),
                                                f"{campus}|{n}" if campus else str(n))
    return records


def diff_fields(old: dict, new: dict) -> list[dict]:
    # A field missing from the stored record was added to the schema after it was saved:
    # the first value seen is a new baseline, not a change made by the provider.
    return [{"field": f, "old": old.get(f), "new": new.get(f)}
            for f in COMPARE_FIELDS if f in old and normalize_text(old.get(f)) != normalize_text(new.get(f))]


class Store:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.sources_path = self.dir / "sources.json"
        self.courses_path = self.dir / "courses.json"
        self.candidates_path = self.dir / "candidate_sources.json"

    @staticmethod
    def _read(path: Path, default: dict) -> dict:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    def load(self) -> tuple[dict, dict, dict]:
        sources = self._read(self.sources_path, {"sources": {}})
        courses = self._read(self.courses_path, {"meta": {}, "courses": {}})
        candidates = self._read(self.candidates_path, {"candidates": {}})
        return sources, courses, candidates

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def save(self, sources: dict, courses: dict, candidates: dict | None = None) -> None:
        self._write(self.sources_path, sources)
        self._write(self.courses_path, courses)
        if candidates is not None:
            self._write(self.candidates_path, candidates)


def update_source_state(state: dict, source, result, now: str, items_found: int | None,
                        org_only: bool = False) -> str:
    """Record a fetch attempt. Returns the source status for this run.

    org_only: the source has only organization-level pages, so finding no activities is expected.
    """
    entry = state["sources"].setdefault(source.id, {})
    entry.update({"provider": source.provider, "url": source.url, "categories": source.categories,
                  "city": source.city, "last_attempted_at": now})
    if result.ok and org_only:
        status = "OK"
        entry.update({"status": status, "http_status": 200, "error": None, "last_success_at": now,
                      "items_found": 0})
    elif not result.ok:
        status = "FETCH_FAILED" if result.status != "BLOCKED_BY_ROBOTS" else "BLOCKED_BY_ROBOTS"
        entry.update({"status": status, "http_status": result.http_status, "error": result.error})
    elif not items_found:
        status = "EMPTY_RESULT"
        entry.update({"status": status, "http_status": 200,
                      "error": "Page loaded but no activities could be extracted "
                               "(layout change or JavaScript-rendered content); verify manually"})
    else:
        status = "OK"
        entry.update({"status": status, "http_status": 200, "error": None, "last_success_at": now,
                      "items_found": items_found})
    entry.setdefault("last_success_at", None)
    return status


def merge_source(courses: dict, source_id: str, source_ok: bool, scraped: list[dict],
                 today: str, now: str, failed_pages: set[str] | frozenset = frozenset()) -> list[dict]:
    """Merge one source's scrape into the course store. Returns per-course change events.

    source_ok=False (failed fetch or empty extraction) never removes or downgrades data:
    existing records are kept and flagged as not recently verified. The same applies to records
    of a multi-page source whose own page (source_url, normalized) is in failed_pages.
    """
    store = courses["courses"]
    events = []
    existing_ids = {cid for cid, c in store.items() if c["source_id"] == source_id}

    if not source_ok:
        for cid in sorted(existing_ids):
            rec = store[cid]
            rec["status"], rec["verified"] = FETCH_FAILED, False
            events.append({"id": cid, "status": FETCH_FAILED})
        return events

    seen = set()
    for new in scraped:
        cid = new["id"]
        seen.add(cid)
        old = store.get(cid)
        if old is None:
            rec = {**new, "status": NEW, "verified": True, "first_seen": today, "last_seen": today,
                   "last_checked": now, "last_changed": today, "missing_since": None, "history": []}
            store[cid] = rec
            events.append({"id": cid, "status": NEW})
            continue
        changes = diff_fields(old, new)
        reappeared = old.get("status") == NOT_FOUND
        for key, value in new.items():
            old[key] = value
        old.update({"verified": True, "last_seen": today, "last_checked": now, "missing_since": None})
        if changes:
            old["status"], old["last_changed"] = UPDATED, today
            old["history"] = (old.get("history", []) + [{"date": today, "changes": changes}])[-HISTORY_LIMIT:]
        else:
            old["status"] = UNCHANGED
        events.append({"id": cid, "status": old["status"], "changes": changes, "reappeared": reappeared})

    for cid in sorted(existing_ids - seen):
        rec = store[cid]
        if normalize_url(rec.get("source_url")) in failed_pages:
            rec["status"], rec["verified"] = FETCH_FAILED, False
            events.append({"id": cid, "status": FETCH_FAILED})
            continue
        rec["status"], rec["verified"], rec["last_checked"] = NOT_FOUND, False, now
        rec["missing_since"] = rec.get("missing_since") or today
        events.append({"id": cid, "status": NOT_FOUND})
    return events
