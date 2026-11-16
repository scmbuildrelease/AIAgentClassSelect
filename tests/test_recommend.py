"""Lifecycle (dates), age-fit semantics, adult courses and the TechKnowHow general price.

"Today" is fixed at 2026-11-15 so the expectations never drift with the real calendar.
"""
import json
from datetime import date
from types import SimpleNamespace

import pytest

from activity_tracker.extract import audience_age_statement, extract_aggregator_events, extract_page, parse_age
from activity_tracker.recommend import (AGE_GROUP_MATCH, AGE_MATCH_CONFIRMED, AGE_MISMATCH, AGE_UNKNOWN,
                                        DATE_UNKNOWN, ONGOING, PAST, UPCOMING, age_fit, audience, lifecycle,
                                        not_recommended_reason)
from activity_tracker.report import build_report
from conftest import ROOT
from test_six_sources import records, six_config, six_run  # noqa: F401  (pytest fixtures)

TODAY = date(2026, 11, 15)
GROUPS = {"preschool": {"label": "学龄前 · 0–5 岁", "min": 0, "max": 5},
          "primary": {"label": "小学 · 6–12 岁", "min": 6, "max": 12}}


# --- lifecycle ----------------------------------------------------------------------------------

@pytest.mark.parametrize("rec, expected", [
    ({"start_date": "2026-06-15", "end_date": "2026-07-17"}, PAST),              # summer 2026 camp
    ({"start_date": "2026-11-14", "end_date": "2026-11-14"}, PAST),              # ended yesterday
    ({"start_date": "2026-11-15", "end_date": "2026-11-15"}, ONGOING),           # today
    ({"start_date": "2026-11-01", "end_date": "2026-12-20"}, ONGOING),           # running
    ({"start_date": "2026-11-16", "end_date": "2026-11-16"}, UPCOMING),          # tomorrow
    ({"start_date": "2027-06-14", "end_date": "2027-06-18"}, UPCOMING),
    ({"start_date": "2026-11-16"}, UPCOMING),
    ({"start_date": "2026-11-15"}, ONGOING),
    ({"start_date": "2026-09-01"}, DATE_UNKNOWN),   # started, end not published: may still run, not PAST
    ({"end_date": "2026-12-01"}, DATE_UNKNOWN),
    ({"start_date": "6/15", "end_date": "7/17"}, DATE_UNKNOWN),  # no year published -> no date assumed
    ({}, DATE_UNKNOWN),
])
def test_lifecycle_from_explicit_dates(rec, expected):
    assert lifecycle(rec, TODAY) == expected


@pytest.mark.parametrize("sessions, expected", [
    (["2026-11-08 10:00–11:00", "2026-11-14 10:00–11:00"], PAST),
    (["2026-11-08 10:00–11:00", "2026-11-22 10:00–11:00"], ONGOING),  # series with a session still to come
    (["2026-11-15 13:00–13:30"], ONGOING),
    (["2026-11-21 10:00–10:30", "2026-11-28 10:00–10:30"], UPCOMING),
    (["6/14 2027 At St. Justin Catholic School", "6/21 2027 At Mountain View Academy"], UPCOMING),
    (["6/16/2025 At Some School"], PAST),
])
def test_recurring_activities_use_their_individual_sessions(sessions, expected):
    # start/end dates deliberately disagree with the sessions: sessions win when they carry full dates
    assert lifecycle({"sessions": sessions, "start_date": "2026-01-01", "end_date": "2026-01-02"}, TODAY) == expected


def test_sessions_without_full_dates_fall_back_to_start_and_end():
    rec = {"sessions": ["June 15 – June 19"], "start_date": "2027-06-15", "end_date": "2027-06-19"}
    assert lifecycle(rec, TODAY) == UPCOMING


def test_past_activities_are_hidden_from_recommendations_but_kept(six_run, six_config):  # noqa: F811
    r = six_run()
    happy = records(r, "happy_childhood_education")
    assert {c["lifecycle"] for c in happy} == {PAST}  # summer 2026, dates from the page
    (mygredu,) = records(r, "mygredu")
    assert mygredu["lifecycle"] == DATE_UNKNOWN  # "2026 Summer Camp" title: no dates published -> not PAST
    md = build_report(r, six_config)
    current = md.split("🗄️")[0]
    assert "沉浸式 LEGO 机器人挑战暑期课程" not in current and "2026 谷雨 Summer Camp" in current
    hidden = md.split("🗄️")[1]
    assert "沉浸式 LEGO 机器人挑战暑期课程" in hidden and "| past |" in hidden
    assert len(records(r)) == 21  # nothing deleted


# --- age fit ------------------------------------------------------------------------------------

def _event(note, ages=("primary",)):
    """An aggregator event as the Ran Chen payload provides it."""
    ev = {"id": "e", "title": "活动", "region": "south", "city": "San Jose", "venue": "Library", "ageNote": note,
          "ages": list(ages), "sessions": [{"date": "2026-11-21", "start": "10:00", "end": "11:00"}],
          "source": "Org", "sourceUrl": "https://org.example.org/e", "category": "nature"}
    payload = json.dumps([ev], ensure_ascii=False, separators=(",", ":"))
    html = f"<script>self.__next_f.push([1,{json.dumps('5:' + payload, ensure_ascii=False)}])</script>"
    src = SimpleNamespace(id="agg", provider="Agg", categories=["outdoor"], program_type="event", url="https://agg/",
                          season=None, org_name="Agg", source_type="community_activity_aggregator", location=None,
                          detect_location=False, city="", translations={}, age_groups=GROUPS,
                          aggregator={"regions": {"south": "South Bay"}, "category_map": {}})
    (rec,) = extract_aggregator_events(html, src, "https://agg/", {})
    return rec


@pytest.mark.parametrize("note, ages, fit, age_min, age_max", [
    ("适合5–10岁儿童", ("primary",), AGE_MATCH_CONFIRMED, 5, 10),                    # explicit range includes 7–8
    ("6岁及以上", ("primary",), AGE_MATCH_CONFIRMED, 6, None),
    ("适合9–12岁", ("primary",), AGE_MISMATCH, 9, 12),                               # explicit range excludes 7–8
    ("适合10岁及以上儿童", ("primary",), AGE_MISMATCH, 10, None),
    ("适合0–5岁及5–10岁儿童", ("preschool", "primary"), AGE_GROUP_MATCH, None, None),  # two statements: not combined
    ("适合6岁以上，9岁以下需成人陪同", ("primary",), AGE_GROUP_MATCH, None, None),
    ("8岁以下须由成人陪同", ("primary",), AGE_GROUP_MATCH, None, None),                # supervision rule only
    ("0–5岁需家长陪同", ("preschool", "primary"), AGE_GROUP_MATCH, None, None),
    ("0-4岁不适合", ("primary",), AGE_GROUP_MATCH, None, None),                       # exclusion only
    ("建议小学儿童", ("primary",), AGE_GROUP_MATCH, None, None),                      # no number published
    ("建议学龄前儿童", ("preschool",), AGE_MISMATCH, None, None),                     # aggregator lists it only 0–5
    (None, (), AGE_UNKNOWN, None, None),                                              # nothing published
])
def test_aggregator_age_notes(note, ages, fit, age_min, age_max):
    rec = _event(note, ages)
    assert rec["age_text"] == note  # preserved word for word
    assert (rec["age_min"], rec["age_max"]) == (age_min, age_max)
    assert age_fit(rec, 7, 8) == fit


def test_aggregator_group_is_never_confirmation():
    rec = _event("建议小学儿童", ("primary",))
    assert rec["age_groups"] == ["小学 · 6–12 岁"]
    assert age_fit(rec, 7, 8) == AGE_GROUP_MATCH != AGE_MATCH_CONFIRMED


@pytest.mark.parametrize("note, is_audience", [
    ("适合5–10岁儿童", True), ("面向5-14岁", True),
    ("8岁以下须由成人陪同", False), ("0-4岁不在范围内", False), ("Children under 8 must be accompanied", False),
    ("0–5岁及5–10岁", False), ("建议小学儿童", False),
])
def test_audience_age_statement(note, is_audience):
    assert audience_age_statement(note) is is_audience


def test_provider_pages_keep_their_age_rules():
    # the aggregator rules do not change how provider pages are parsed
    assert parse_age("Ages 7-9. Children under 8 must be accompanied by an adult.")[1:3] == (7, 9)


@pytest.mark.parametrize("rec, fit", [
    ({"age_min": 7, "age_max": 8}, AGE_MATCH_CONFIRMED),
    ({"age_min": 8, "age_max": 12}, AGE_MATCH_CONFIRMED),
    ({"age_min": 3, "age_max": 6}, AGE_MISMATCH),
    ({"age_min": None, "age_max": None}, AGE_UNKNOWN),
    ({"age_group_min": 6, "age_group_max": 12}, AGE_GROUP_MATCH),
    ({"age_group_min": 0, "age_group_max": 5}, AGE_MISMATCH),
    ({"age_min": 9, "age_max": 12, "age_group_min": 6, "age_group_max": 12}, AGE_MISMATCH),  # explicit wins
])
def test_age_fit(rec, fit):
    assert age_fit(rec, 7, 8) == fit


def test_report_labels_unconfirmed_ages(six_run, six_config):  # noqa: F811
    md = build_report(six_run(), six_config)
    assert "≈ 适合0–5岁及5–10岁儿童" in md and "event ages not confirmed" in md  # puppet show: group only
    assert "✅ 6岁及以上" in md  # bird walk: explicit age
    assert "❓ _Not published_" in md
    assert "only listed under an aggregator's broad age group (event ages not confirmed)" in md


# --- adult courses ------------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("成人形体修塑", "adult"), ("辣妈舞团", "adult"), ("Adult Ballet", "adult"),
    ("幼儿中国舞启蒙教学", "children"), ("Kids Coding", "children"),
    # a children's dance school does not make each of its courses a kids' course
    ("拉丁舞", None), ("流行舞", None), ("中国技术技巧", None),
    ("成人陪同亲子绘本", None), ("Adults & Kids Yoga", None),   # adult accompaniment / family, not adult-only
])
def test_audience_from_title(name, expected):
    assert audience({"name": name}) == expected


def test_adult_courses_are_kept_but_not_recommended(six_run, six_config, tmp_path):  # noqa: F811
    r = six_run()
    shoes = {c["name"]: c for c in records(r, "red_shoes_dance_studio")}
    assert len(shoes) == 6  # kept in the provider's course list
    assert {n for n, c in shoes.items() if c["audience"] == "adult"} == {"成人形体修塑", "辣妈舞团"}
    assert shoes["幼儿中国舞启蒙教学"]["audience"] == "children" and shoes["拉丁舞"]["audience"] is None
    assert not_recommended_reason(shoes["辣妈舞团"], 7, 8, TODAY) == "adult course"
    assert not_recommended_reason(shoes["拉丁舞"], 7, 8, TODAY) is None
    md = build_report(r, six_config)
    current, hidden = md.split("🗄️")[0], md.split("🗄️")[1]
    assert "辣妈舞团" not in current and "成人形体修塑" not in current and "拉丁舞" in current
    assert "| adult course |" in hidden


def test_backend_hides_past_and_adult_by_default(tmp_path, monkeypatch):
    pytest.importorskip("flask")
    pytest.importorskip("flask_cors")
    data = tmp_path / "courses.json"
    data.write_text(json.dumps({"courses": {
        "past": {"id": "past", "name": "Summer Camp", "start_date": "2026-06-15", "end_date": "2026-07-17"},
        "adult": {"id": "adult", "name": "成人形体修塑"},
        "kids": {"id": "kids", "name": "幼儿中国舞启蒙教学"},
        "soon": {"id": "soon", "name": "Bird Walk", "sessions": ["2026-11-21 08:00–10:00"]},
    }}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("COURSES_FILE", str(data))
    monkeypatch.setenv("TODAY", "2026-11-15")
    import importlib
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    app = importlib.reload(importlib.import_module("app")).app
    client = app.test_client()
    shown = {c["id"]: c for c in client.get("/courses").get_json()}
    assert set(shown) == {"kids", "soon"} and shown["soon"]["lifecycle"] == UPCOMING
    assert {c["id"] for c in client.get("/courses?all=1").get_json()} == {"past", "adult", "kids", "soon"}


# --- TechKnowHow general price ------------------------------------------------------------------

TECHKNOWHOW_TEXT = """<html><head><title>Robotics & Game-Making</title></head><body><main>
<h1>Robotics &amp; Game-Making</h1><p>Ages 8-12</p>
<p>Location Details SF - Sunset 9:00am - 3:30pm $460/wk, Mon-Thu* ExtCare 8:30-9:00($32/week)</p>
<p>Location Details Fremont 9:00am - 3:30pm $575/week ExtCare 8:30-9:00($40/week)</p>
<p>Camp Pricing Camp Tuition 9:00 am - 3:30 pm $465 Tuition for 4-day week $355 Multi-Week discount</p>
</main></body></html>"""


def _tkh(price_label):
    from bs4 import BeautifulSoup
    src = SimpleNamespace(id="techknowhow-lego-robotics", provider="TechKnowHow", categories=["stem"], url="https://t/",
                          program_type="camp", season="summer", course_name=None, price_label=price_label,
                          campus_links={}, org_name="TechKnowHow", source_type="activity_provider", location=None,
                          detect_location=True, city="Multiple Bay Area locations", translations={})
    (rec,) = extract_page(BeautifulSoup(TECHKNOWHOW_TEXT, "html.parser"), src, "https://t/", [])
    return rec


def test_general_price_comes_from_the_tuition_line():
    assert _tkh(None)["price"] == "$460/wk"  # first price on the page: a single location's 4-day week
    assert _tkh("Camp Tuition")["price"] == "$465"
    assert _tkh("No Such Label")["price"] is None  # label missing -> unknown, not a fallback guess


def test_techknowhow_is_configured_with_the_tuition_label():
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))["sources"]
    (tkh,) = [s for s in sources if s["id"] == "techknowhow-lego-robotics"]
    assert tkh["price_label"] == "Camp Tuition"
    assert sum(1 for s in sources if s.get("price_label")) == 1  # no other source affected


# --- time zone ----------------------------------------------------------------------------------

def test_today_is_the_bay_area_date_not_utc():
    from datetime import datetime, timezone
    from activity_tracker.recommend import local_today
    evening = datetime(2026, 11, 16, 4, 5, tzinfo=timezone.utc)  # 8:05 pm Nov 15 in San Jose
    assert local_today(evening) == date(2026, 11, 15)
    assert lifecycle({"sessions": ["2026-11-15 13:00–13:30"]}, local_today(evening)) == ONGOING


def test_run_in_the_bay_area_evening_keeps_todays_events(six_run):  # noqa: F811
    from datetime import datetime, timezone
    r = six_run(when=datetime(2026, 11, 22, 4, 0, tzinfo=timezone.utc))  # 8 pm Nov 21 Pacific
    assert r["today"] == "2026-11-21"
    birds = next(c for c in records(r, "ranchen_bay_area_weekend") if c["original_title_en"] == "Bay Bird Mornings")
    assert birds["sessions"] == ["2026-11-21 08:00–10:00"] and birds["lifecycle"] == ONGOING
