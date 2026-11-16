"""Command-line entry point: python -m activity_tracker [options]."""
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import AGGREGATOR, ConfigError, load_config, parse_category_filter
from .discovery import find_candidates, merge_candidates
from .extract import extract, geo_filter
from .fetcher import Fetcher, FixtureFetcher
from .search import Glossary, link_language_variants
from .report import build_report
from .tracker import Store, assign_ids, merge_source, normalize_url, update_source_state

log = logging.getLogger("activity_tracker")
MODES = ("refresh_known_sources", "discover_new_sources", "both")
STEP_SUMMARY_LIMIT = 1_000_000  # GitHub caps each step summary at 1 MiB


def run_discovery(config, store: Store, fetcher, params: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    now_s, today = now.strftime("%Y-%m-%dT%H:%M:%SZ"), now.date().isoformat()
    mode = params["mode"]
    refresh, discover = mode in ("refresh_known_sources", "both"), mode in ("discover_new_sources", "both")
    sources_state, courses, candidates = store.load()
    is_baseline = refresh and not courses["courses"]
    selected = set(params["categories"])

    source_results, events, new_candidates, processed = [], [], [], []
    known_urls = {normalize_url(v.url) for s in config.sources for v in s.page_views()}
    known_urls |= {normalize_url(s["url"]) for s in config.discovery_seeds}
    known_urls |= {normalize_url(c.get("detail_url")) for c in courses["courses"].values()}

    for source in config.sources:
        if not source.enabled or not selected & set(source.categories):
            continue
        base = {"id": source.id, "provider": source.provider, "url": source.url,
                "categories": source.categories, "notes": source.notes, "source_type": source.source_type,
                "language": source.language, "locations": source.locations or source.geographic_scope,
                "verification_status": source.verification_status}
        if source.verification_status != "VERIFIED":
            source_results.append({**base, "status": "PENDING_VERIFICATION"})
            continue
        if source.manual_only:
            source_results.append({**base, "status": "MANUAL"})
            continue
        kept = sum(1 for c in courses["courses"].values() if c["source_id"] == source.id)
        records, pages, excluded, failed_pages, results = [], [], [], set(), []
        for view in source.page_views():
            log.info("fetching %s (%s)", source.id, view.url)
            result = fetcher.get(view.url)
            page = {"url": view.url, "role": view.role, "parser": view.parser, "http_status": result.http_status,
                    "status": "OK" if result.ok else ("BLOCKED_BY_ROBOTS" if result.status == "BLOCKED_BY_ROBOTS"
                                                      else "FETCH_FAILED"), "error": result.error, "items": 0}
            if refresh and result.ok and view.role == "activities":
                try:
                    found = extract(result.html, view, result.final_url or view.url, config.cities, result.content)
                    found, out = geo_filter(found, view, config.cities)
                    excluded += [{"name": r.get("name"), "location": r.get("location") or r.get("region")}
                                 for r in out]
                    page["items"] = len(found)
                    records += found
                except Exception as e:  # a parser bug on one page must not break the run
                    log.exception("extraction failed for %s (%s)", source.id, view.url)
                    page.update(status="EXTRACTION_ERROR", error=f"Extraction error: {type(e).__name__}: {e}")
            if view.role == "activities":
                results.append((page, result))
                if page["status"] != "OK":
                    failed_pages.add(normalize_url(view.url))
            if discover and result.ok and source.source_type != AGGREGATOR:  # aggregators link to hundreds of sites
                found = find_candidates(result.html, view.url, config.settings, config.categories)
                new_candidates += merge_candidates(candidates, found, view.url, known_urls, today)
            pages.append(page)

        ok_results = [r for p_, r in results if p_["status"] == "OK"]
        any_failed = next((r for p_, r in results if p_["status"] != "OK"), None)
        main = ok_results[0] if ok_results else (any_failed or result)
        errors = (pages[0]["error"] if len(pages) == 1 else
                  "; ".join(f"{p_['url']}: {p_['error']}" for p_ in pages if p_["error"]) or None)
        entry = {**base, "status": pages[0]["status"], "http_status": main.http_status, "error": errors,
                 "kept_records": kept, "pages": pages, "excluded": excluded}
        if refresh:
            records = assign_ids(records)
            status = update_source_state(sources_state, source, main, now_s, len(records), org_only=not results)
            if status == "OK" and failed_pages:
                status = "PARTIAL"
            state = sources_state["sources"][source.id]
            state.update(status=status, organization=_organization_profile(source, pages, state, now_s))
            if status == "PARTIAL":
                state["error"] = errors
            entry.update(status=status, error=errors or state.get("error"),
                         last_success_at=state.get("last_success_at"), items_found=len(records))
            known_urls |= {normalize_url(r.get("detail_url")) for r in records}
            events += merge_source(courses, source.id, status in ("OK", "PARTIAL"), records, today, now_s,
                                   failed_pages)
            processed.append(source.id)
        source_results.append(entry)

    if discover:
        for seed in config.discovery_seeds:
            if not selected & set(seed.get("categories", list(config.categories))):
                continue
            result = fetcher.get(seed["url"])
            entry = {"id": f"seed:{seed['url']}", "provider": seed.get("provider", seed["url"]), "url": seed["url"],
                     "categories": seed.get("categories", []), "status": "OK" if result.ok else "FETCH_FAILED",
                     "http_status": result.http_status, "error": result.error, "seed": True}
            if result.ok:
                found = find_candidates(result.html, seed["url"], config.settings, config.categories)
                new_candidates += merge_candidates(candidates, found, seed["url"], known_urls, today)
            source_results.append(entry)

    if refresh:
        link_language_variants(courses, Glossary(config.settings.get("glossary", [])))

    attempted = [s for s in source_results if s["status"] not in ("MANUAL", "PENDING_VERIFICATION")]
    succeeded = [s for s in attempted if s["status"] in ("OK", "PARTIAL")]
    saved, reason = True, None
    if attempted and not succeeded:
        saved, reason = False, f"all {len(attempted)} fetched sources failed or returned no activities"
    if saved:
        if refresh:
            meta = courses.setdefault("meta", {})
            meta.setdefault("baseline_created_at", now_s)
            meta["last_run_at"] = now_s
            meta["run_count"] = meta.get("run_count", 0) + 1
        store.save(sources_state, courses, candidates if discover else None)

    return {"run_at": now_s, "params": params, "is_baseline": is_baseline, "saved": saved,
            "not_saved_reason": reason, "source_results": source_results, "events": events,
            "processed_source_ids": processed, "courses": courses, "new_candidates": new_candidates}


def _organization_profile(source, pages: list[dict], state: dict, now: str) -> dict:
    """Organization-level facts kept per source (not activity records). Contact details are not stored."""
    previous = {p["url"]: p for p in (state.get("organization") or {}).get("pages", [])}
    return {
        "name": source.org_name, "official_url": source.url, "source_type": source.source_type,
        "verification_status": source.verification_status, "language": source.language,
        "locations": source.locations, "geographic_scope": source.geographic_scope, "topics": source.topics,
        "pages": [{"url": p["url"], "role": p["role"], "status": p["status"],
                   "last_verified": now if p["status"] == "OK" else previous.get(p["url"], {}).get("last_verified")}
                  for p in pages],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Discover and track kids' activities from configured sources.")
    ap.add_argument("--min-age", type=int, default=None)
    ap.add_argument("--max-age", type=int, default=None)
    ap.add_argument("--categories", default="all", help="'all' or comma-separated category keys")
    ap.add_argument("--mode", choices=MODES, default="refresh_known_sources")
    ap.add_argument("--config-dir", type=Path, default=Path("config"))
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--report", type=Path, default=Path("reports/report.md"))
    ap.add_argument("--summary", type=Path, default=None, help="also append the report here ($GITHUB_STEP_SUMMARY)")
    ap.add_argument("--fixtures", type=Path, default=None, help="offline mode: serve pages from a fixture dir")
    args = ap.parse_args(argv)
    logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)

    try:
        config = load_config(args.config_dir)
        cats = parse_category_filter(args.categories, config.categories)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    min_age = args.min_age if args.min_age is not None else config.settings.get("default_age_min", 7)
    max_age = args.max_age if args.max_age is not None else config.settings.get("default_age_max", 8)
    if not (0 <= min_age <= max_age <= 21):
        print(f"Invalid age range {min_age}-{max_age}", file=sys.stderr)
        return 1

    fetcher = FixtureFetcher(args.fixtures) if args.fixtures else Fetcher(config.settings)
    params = {"min_age": min_age, "max_age": max_age, "categories": cats, "mode": args.mode}
    run = run_discovery(config, Store(args.data_dir), fetcher, params)
    report = build_report(run, config)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    slim = {k: v for k, v in run.items() if k != "courses"}
    args.report.with_name("run_summary.json").write_text(json.dumps(slim, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.summary:
        text = report
        if len(text.encode()) > STEP_SUMMARY_LIMIT:
            text = text.encode()[: STEP_SUMMARY_LIMIT - 200].decode(errors="ignore") + \
                "\n\n_Report truncated — download the full report artifact._\n"
        with open(args.summary, "a", encoding="utf-8") as f:
            f.write(text)
    log.info("report written to %s (data saved: %s)", args.report, run["saved"])
    return 0 if run["saved"] else 2
