"""The six Bay Area Chinese education / family activity sources, run offline against sanitized snapshots.

Uses the real config/sources.json entries, so URLs, source types and parser settings are tested as shipped.
"""
import json
from dataclasses import replace

import pytest

from activity_tracker.cli import run_discovery
from activity_tracker.config import ConfigError, load_config
from activity_tracker.fetcher import FixtureFetcher
from activity_tracker.report import build_report
from activity_tracker.search import Glossary, search
from activity_tracker.tracker import FETCH_FAILED, NEW, NOT_FOUND, UNCHANGED, Store
from conftest import FIXTURES, ROOT, RUN1, RUN2

SIX = {
    "mygredu": ("https://www.mygredu.com/", "education_provider"),
    "happy_childhood_education": ("https://www.happychildhoodedu.com/", "education_provider"),
    "brightup_kids": ("https://brightupkids.org/zh/", "community_education_provider"),
    "loving_tree_academy": ("https://www.lovingtreeacademy.com/", "education_provider"),
    "red_shoes_dance_studio": ("https://hongwuxie887.wixsite.com/redshoes", "activity_provider"),
    "ranchen_bay_area_weekend": ("https://ranchen.org/weekend", "community_activity_aggregator"),
}
ORG_PAGES = {"https://www.mygredu.com/", "https://www.happychildhoodedu.com/", "https://www.lovingtreeacademy.com/",
             "https://hongwuxie887.wixsite.com/redshoes", "https://hongwuxie887.wixsite.com/redshoes/contact"}


@pytest.fixture
def six_config():
    cfg = load_config(ROOT / "config")
    return replace(cfg, sources=[s for s in cfg.sources if s.id in SIX])


@pytest.fixture
def six_run(six_config, tmp_path):
    def _run(site="site_six", when=RUN1, config=None, mode="refresh_known_sources"):
        cfg = config or six_config
        params = {"min_age": 7, "max_age": 8, "categories": list(cfg.categories), "mode": mode}
        fetcher = FixtureFetcher(FIXTURES / site)
        result = run_discovery(cfg, Store(tmp_path / "data"), fetcher, params, now=when)
        result["fetched"] = fetcher.requested
        return result
    return _run


def records(run, source_id=None):
    return [c for c in run["courses"]["courses"].values() if source_id in (None, c["source_id"])]


def names(run, source_id):
    return sorted(c["name"] for c in records(run, source_id))


# --- configuration -----------------------------------------------------------------------------

def test_six_sources_are_configured_verified_and_enabled(six_config):
    by_id = {s.id: s for s in six_config.sources}
    assert set(by_id) == set(SIX)
    for sid, (url, source_type) in SIX.items():
        s = by_id[sid]
        assert (s.url, s.source_type, s.verification_status, s.enabled) == (url, source_type, "VERIFIED", True)
        assert not s.manual_only
    assert by_id["mygredu"].locations == ["Cupertino, CA", "Milpitas, CA"]
    assert by_id["loving_tree_academy"].locations == ["Milpitas, CA", "Fremont, CA", "Newark, CA", "Pleasanton, CA"]
    assert by_id["ranchen_bay_area_weekend"].language == ["zh"]
    assert by_id["brightup_kids"].require_bay_area
    assert [v.url for v in by_id["mygredu"].page_views()] == ["https://www.mygredu.com/",
                                                              "https://www.mygredu.com/summer-camp"]
    assert [v.url for v in by_id["red_shoes_dance_studio"].page_views()][1:] == [
        "https://hongwuxie887.wixsite.com/redshoes/about", "https://hongwuxie887.wixsite.com/redshoes/contact"]


def _write_config(tmp_path, sources):
    settings = (ROOT / "config/settings.json").read_text(encoding="utf-8")
    (tmp_path / "settings.json").write_text(settings, encoding="utf-8")
    (tmp_path / "sources.json").write_text(json.dumps({"sources": sources}, ensure_ascii=False), encoding="utf-8")
    return load_config(tmp_path)


BASE = {"id": "a_b", "provider": "P", "url": "https://a.example.org/", "categories": ["language"], "city": "San Jose"}


@pytest.mark.parametrize("sources, message", [
    ([BASE, {**BASE, "id": "other", "url": "https://www.a.example.org"}], "already configured"),
    ([{**BASE, "pages": [{"url": "https://a.example.org/#top"}]}], "already configured"),
    ([{**BASE, "url": "ftp://a.example.org/"}], "http"),
    ([{**BASE, "url": "javascript:alert(1)"}], "http"),
    ([{**BASE, "pages": [{"url": "not a url"}]}], "http"),
    ([{**BASE, "source_type": "school"}], "source_type"),
    ([{**BASE, "verification_status": "MAYBE"}], "verification_status"),
    ([{**BASE, "pages": [{"url": "https://a.example.org/x", "colour": "red"}]}], "unknown page keys"),
    ([{**BASE, "unknown_field": 1}], "unknown_field"),
])
def test_invalid_source_config_is_rejected(tmp_path, sources, message):
    with pytest.raises(ConfigError, match=message):
        _write_config(tmp_path, sources)


def test_underscore_ids_are_valid(tmp_path):
    assert _write_config(tmp_path, [BASE]).sources[0].id == "a_b"


def test_pending_sources_are_reported_but_never_fetched(six_config, six_run):
    pending = [replace(s, verification_status="PENDING") if s.id == "red_shoes_dance_studio" else s
               for s in six_config.sources]
    r = six_run(config=replace(six_config, sources=pending))
    assert not any("wixsite" in u for u in r["fetched"])
    assert not records(r, "red_shoes_dance_studio")
    status = {s["id"]: s["status"] for s in r["source_results"]}
    assert status["red_shoes_dance_studio"] == "PENDING_VERIFICATION" and status["mygredu"] == "OK"
    md = build_report(r, six_config)
    assert "Pending verification" in md and "红舞鞋舞校 / Red Shoes Dance Studio" in md.split("Pending verification")[1]


# --- organization pages vs. activity records ---------------------------------------------------

def test_organization_pages_never_become_activities(six_run, tmp_path):
    r = six_run()
    assert ORG_PAGES <= set(r["fetched"])
    assert not {c["source_url"] for c in records(r)} & ORG_PAGES
    assert {c["source_url"] for c in records(r)} >= {"https://www.mygredu.com/summer-camp",
                                                     "https://hongwuxie887.wixsite.com/redshoes/about"}
    state = json.loads((tmp_path / "data/sources.json").read_text(encoding="utf-8"))["sources"]
    org = state["red_shoes_dance_studio"]["organization"]
    assert org["name"] == "红舞鞋舞校 / Red Shoes Dance Studio" and org["source_type"] == "activity_provider"
    assert [(p["role"], p["status"]) for p in org["pages"]] == [
        ("organization", "OK"), ("activities", "OK"), ("organization", "OK")]
    assert all(p["last_verified"] == "2026-11-15T12:00:00Z" for p in org["pages"])
    assert "hongwuxie887@" not in json.dumps(state)  # contact details are not stored


def test_chinese_text_is_preserved_exactly_as_utf8(six_run, tmp_path):
    r = six_run()
    assert names(r, "red_shoes_dance_studio") == sorted(
        ["幼儿中国舞启蒙教学", "流行舞", "中国技术技巧", "拉丁舞", "成人形体修塑", "辣妈舞团"])
    raw = (tmp_path / "data/courses.json").read_text(encoding="utf-8")
    assert "幼儿中国舞启蒙教学" in raw and "\\u5e7c" not in raw
    club = next(c for c in records(r, "brightup_kids") if c["name"] == "湾区中文亲子读书会")
    assert club["description"] == "面向湾区华人家庭的中文亲子阅读与手工活动，一个轻松交流、亲子共学的平台。"
    assert club["original_language"] == "zh-Hans" and club["translations"] == {}  # nothing is auto-translated


def test_mixed_chinese_english_camp_page(six_run):
    (camp,) = records(six_run(), "mygredu")
    assert camp["name"] == "2026 谷雨 Summer Camp" and camp["original_language"] == "mixed"
    assert camp["record_type"] == "camp" and camp["enrollment_status"] == "Registration open"
    assert camp["registration_url"] == "https://www.mygredu.com/registration/summer-camp-registration"
    assert camp["location"] == "Milpitas, Cupertino"  # both campuses named on the page; no campus assumed
    assert camp["campus"] is None
    # dates, ages and price are not in the page text: unknown, not guessed ($50 is a transfer fee)
    assert (camp["start_date"], camp["age_text"], camp["price"]) == (None, None, None)


def test_name_only_courses_have_no_inferred_details(six_run):
    for c in records(six_run(), "red_shoes_dance_studio"):
        assert c["record_type"] == "class" and c["location"] == "Newark"
        assert all(c[f] is None for f in ("age_text", "age_min", "age_max", "schedule", "price", "start_date"))
    assert "学员展示" not in names(six_run(), "red_shoes_dance_studio")  # a showcase, not a listed course


def test_sections_page_gives_one_record_per_camp(six_run):
    camps = {c["name"]: c for c in records(six_run(), "happy_childhood_education")}
    lego = camps["沉浸式 LEGO 机器人挑战暑期课程"]
    # the year comes from the page heading "2026 快乐童年暑期夏令营"
    assert (lego["start_date"], lego["end_date"], lego["schedule"]) == ("2026-06-15", "2026-07-17", "9:30am-12:30pm")
    assert lego["price"] == "$400/周" and lego["currency"] == "USD"  # 优惠价 is the price, $300 is an add-on
    fair = camps["传统文化、童玩、手作嘉年华会"]
    assert (fair["start_date"], fair["end_date"], fair["schedule"]) == ("2026-06-08", "2026-07-31", "8:30am-6:00pm")
    assert fair["price"] is None and fair["currency"] is None and fair["age_text"] is None
    assert lego["registration_url"] == "https://www.happychildhoodedu.com/pdf/2026%20summer%20camp%20cn.pdf"


def test_campuses_are_kept_separate(six_run):
    r = six_run()
    after = {c["campus"]: c for c in records(r, "loving_tree_academy") if c["name"] == "After School Program"}
    assert set(after) == {"Pleasanton", "Fremont", "Newark"}  # no Milpitas link on the page -> no Milpitas record
    assert after["Fremont"]["registration_url"] == "https://forms.example.com/lta-fremont"
    assert after["Newark"]["location"] == "36601 Newark Blvd, Suite 83 & 85, Newark, CA 94560"
    assert len({c["id"] for c in after.values()}) == 3
    (camp,) = [c for c in records(r, "loving_tree_academy") if c["record_type"] == "camp"]
    assert camp["campus"] is None and camp["location"] is None  # footer addresses are not assigned to it


def test_only_bay_area_programs_are_imported(six_run):
    r = six_run()
    assert names(r, "brightup_kids") == sorted(["湾区中文亲子读书会", "中文图书馆", "童心同行 · 融合家庭计划"])
    excluded = next(s for s in r["source_results"] if s["id"] == "brightup_kids")["excluded"]
    assert excluded == [{"name": "中文魔法：儿童故事时间", "location": "大波士顿地区的公共图书馆"},
                        {"name": "BrightUp Institute", "location": None}]
    lib = next(c for c in records(r, "brightup_kids") if c["name"] == "中文图书馆")
    assert (lib["age_min"], lib["age_max"], lib["location"]) == (0, 7, "加州圣何塞")
    club = next(c for c in records(r, "brightup_kids") if c["name"] == "湾区中文亲子读书会")
    assert club["age_text"] == "学龄前及小学低年级" and club["age_min"] is None  # text kept, no number guessed


# --- aggregator ---------------------------------------------------------------------------------

def test_aggregator_events_keep_organizer_and_original_url(six_run):
    r = six_run()
    events = {c["original_title_en"]: c for c in records(r, "ranchen_bay_area_weekend")}
    assert set(events) == {"Bay Bird Mornings", "Hummingbird Puppet Show", "Baby Music & Movement",
                           "Loving Tree Summer Camp", "Craft [Workshop](javascript:alert(1))"}
    birds = events["Bay Bird Mornings"]
    assert birds["name"] == "海湾观鸟早晨" and birds["organizer"] == "Example Parks District"
    assert birds["original_event_url"] == birds["detail_url"] == "https://parks.example.org/events/bay-birds"
    assert birds["aggregator_url"] == birds["source_url"] == "https://ranchen.org/weekend"
    assert birds["verification"] == "aggregator_listing" and birds["registration_url"] is None
    assert (birds["region"], birds["location"]) == ("East Bay", "Hayward Shoreline, Hayward")
    assert (birds["age_text"], birds["age_min"], birds["age_max"]) == ("6岁及以上", 6, None)
    assert birds["categories"] == ["outdoor"] and birds["record_type"] == "event"


def test_one_time_vs_multiple_session_events(six_run):
    events = {c["original_title_en"]: c for c in records(six_run(), "ranchen_bay_area_weekend")}
    assert events["Bay Bird Mornings"]["recurrence"] == "one_time"
    puppet = events["Hummingbird Puppet Show"]
    assert puppet["recurrence"] == "multiple_sessions"
    assert puppet["sessions"] == ["2026-11-21 10:00–10:30", "2026-11-22 13:00–13:30", "2026-11-28 10:00–10:30"]
    assert (puppet["start_date"], puppet["end_date"]) == ("2026-11-21", "2026-11-28")
    assert puppet["schedule"] == "2026-11-21 10:00–10:30 (+2 more)"


def test_aggregator_missing_fields_stay_unknown(six_run):
    events = {c["original_title_en"]: c for c in records(six_run(), "ranchen_bay_area_weekend")}
    puppet = events["Hummingbird Puppet Show"]
    # two age statements ("0–5岁及5–10岁"): shown as published, no single range is extracted from it
    assert puppet["age_text"] == "适合0–5岁及5–10岁儿童" and puppet["age_min"] is None and puppet["age_max"] is None
    assert puppet["age_groups"] == ["学龄前 · 0–5 岁", "小学 · 6–12 岁"]  # aggregator's filter, kept as published
    assert puppet["price"] == "票价未说明，详见原活动页面" and puppet["currency"] is None


def test_aggregator_skips_undated_and_out_of_area_events(six_run):
    r = six_run()
    titles = {c["original_title_en"] for c in records(r, "ranchen_bay_area_weekend")}
    assert "Date TBD" not in titles  # no session date -> not an event record
    assert "Out of Area Fair" not in titles
    excluded = next(s for s in r["source_results"] if s["id"] == "ranchen_bay_area_weekend")["excluded"]
    assert excluded == [{"name": "外地活动", "location": "Los Angeles"}]


def test_aggregator_listing_of_a_tracked_provider_page_is_a_duplicate(six_run):
    r = six_run()
    camp = next(c for c in records(r, "loving_tree_academy") if c["record_type"] == "camp")
    listed = next(c for c in records(r, "ranchen_bay_area_weekend")
                  if c["original_title_en"] == "Loving Tree Summer Camp")
    assert listed["duplicate_of"] == camp["id"] and camp["duplicate_of"] is None
    assert camp["also_listed_by"] == [{"source_id": "ranchen_bay_area_weekend", "record_id": listed["id"],
                                       "url": "https://ranchen.org/weekend"}]
    md = build_report(r, load_config(ROOT / "config"))
    assert "春雨学院夏令营" not in md  # shown once, as the provider's own record


def test_preschool_only_events_are_outside_ages_7_8(six_run, six_config):
    md = build_report(six_run(), six_config)
    before_sources = md.split("## 📚")[0]
    assert "宝宝音乐律动" not in before_sources  # aggregator group 0–5 rules it out
    assert "木偶剧《蜂鸟取火》" in before_sources  # 0–5 and 6–12: shown, ages still "Not published"
    assert "listed under: 学龄前 · 0–5 岁; 小学 · 6–12 岁" in md


def test_scraped_markup_and_urls_are_sanitized(six_run, six_config):
    r = six_run()
    craft = next(c for c in records(r, "ranchen_bay_area_weekend") if c["region"] == "North Bay")
    assert craft["name"] == "<img src=x onerror=alert(1)>手作 | 工坊"  # stored as published (data, not markup)
    assert craft["detail_url"] is None and craft["original_event_url"] is None  # javascript: URL dropped
    md = build_report(r, six_config)
    assert "<img" not in md and "javascript:" not in md
    assert "&lt;img src=x onerror=alert(1)&gt;手作 \\| 工坊" in md
    assert "Example \\*Museum\\*" in md


# --- runs, failures, reporting ------------------------------------------------------------------

def test_second_identical_run_is_unchanged(six_run):
    first = six_run()
    assert {c["status"] for c in records(first)} == {NEW}
    second = six_run(when=RUN2)
    assert {c["status"] for c in records(second)} == {UNCHANGED}
    assert len(records(second)) == len(records(first)) == 21


def test_failed_pages_preserve_existing_records(six_run):
    six_run()
    r = six_run("site_six_v2", RUN2)
    status = {s["id"]: s["status"] for s in r["source_results"]}
    assert status["ranchen_bay_area_weekend"] == "FETCH_FAILED"
    assert status["loving_tree_academy"] == "PARTIAL"  # camp page down, after-school page fine
    assert status["mygredu"] == status["brightup_kids"] == "OK"
    events = records(r, "ranchen_bay_area_weekend")
    assert len(events) == 5 and {c["status"] for c in events} == {FETCH_FAILED}
    assert all(not c["verified"] and c["organizer"] for c in events)  # kept with their data
    lta = {(c["name"], c["campus"]): c["status"] for c in records(r, "loving_tree_academy")}
    assert lta[("Summer /Winter Camp Program", None)] == FETCH_FAILED
    assert {lta[("After School Program", k)] for k in ("Fremont", "Newark", "Pleasanton")} == {UNCHANGED}
    shoes = {c["name"]: c["status"] for c in records(r, "red_shoes_dance_studio")}
    assert shoes["流行舞"] == NOT_FOUND and shoes["拉丁舞"] == UNCHANGED


def test_all_sources_unreachable_saves_nothing(six_run, tmp_path):
    six_run()
    before = (tmp_path / "data/courses.json").read_text(encoding="utf-8")
    r = six_run("site_down", RUN2)  # none of these URLs resolve -> network errors
    assert not r["saved"] and {s["status"] for s in r["source_results"]} == {"FETCH_FAILED"}
    assert (tmp_path / "data/courses.json").read_text(encoding="utf-8") == before


def test_report_shows_source_types_and_aggregator_attribution(six_run, six_config):
    md = build_report(six_run(), six_config)
    overview = md.split("## 📚 Sources by type")[1].split("## ⚠️")[0]
    assert "| Community activity aggregator | zh |" in overview
    assert "| Community education provider | zh/en |" in overview
    assert "中文魔法：儿童故事时间 (大波士顿地区的公共图书馆)" in overview
    assert "www.lovingtreeacademy.com/ (OK)" in overview  # organization page
    assert "1 camp, 3 class" in overview
    assert "listed by [aggregator](https://ranchen.org/weekend); organizer: " \
           "[Example Parks District](https://parks.example.org/events/bay-birds)" in md
    assert "not confirmed by the organizer; one-time" in md
    assert "After School Program](https://www.lovingtreeacademy.com/blog) † · campus: Fremont" in md


def test_discovery_does_not_harvest_aggregator_links(six_run):
    r = six_run(mode="both")
    assert not [c for c in r["new_candidates"] if c["found_on"] == "https://ranchen.org/weekend"]


def test_bilingual_search_finds_new_sources(six_run, six_config):
    recs = [c for c in records(six_run()) if not c.get("duplicate_of")]
    glossary = Glossary(six_config.settings["glossary"])
    # Loving Tree is tagged after-school; Happy Childhood's page title says 课后教室 (after-school classroom)
    assert {c["source_id"] for c in search(recs, "after school", glossary)} == {"loving_tree_academy",
                                                                                 "happy_childhood_education"}
    assert "湾区中文亲子读书会" in {c["name"] for c in search(recs, "reading", glossary)}
    assert "拉丁舞" in {c["name"] for c in search(recs, "dance", glossary, {"dance_performing": "Dance"})}
