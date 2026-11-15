"""Chinese (Simplified/Traditional), English and mixed-language support."""
import json
import shutil

import pytest

from activity_tracker import ocr
from activity_tracker.cli import run_discovery
from activity_tracker.config import ConfigError, load_config
from activity_tracker.extract import extract, find_dates, find_enrollment, find_price, find_schedule, parse_age
from activity_tracker.fetcher import FixtureFetcher, html_encoding
from activity_tracker.i18n import detect_language, display, to_simplified
from activity_tracker.report import build_report
from activity_tracker.search import Glossary, link_language_variants, search
from activity_tracker.tracker import Store
from conftest import FIXTURES, ROOT, RUN1, RUN2

ZH = FIXTURES / "site_zh"


@pytest.fixture
def zh_config(tmp_path):
    """Real settings (glossary, city aliases) + the Chinese fixture sources."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    shutil.copy(ROOT / "config/settings.json", cfg / "settings.json")
    shutil.copy(ZH / "sources.json", cfg / "sources.json")
    return load_config(cfg)


@pytest.fixture
def glossary():
    return Glossary(json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))["glossary"])


def source(config, sid):
    return next(s for s in config.sources if s.id == sid)


def page(config, sid, file):
    src = source(config, sid)
    return extract((ZH / file).read_text(encoding="utf-8"), src, src.url, config.cities)[0]


# ---------- language detection ----------

def test_detect_language():
    assert detect_language("Robotics Summer Camp") == "en"
    assert detect_language("机器人编程夏令营") == "zh-Hans"
    assert detect_language("機器人程式設計夏令營") == "zh-Hant"
    assert detect_language("Kids Art 儿童美术班 Drawing & Painting") == "mixed"
    assert detect_language(None, "") is None
    assert to_simplified("中文學校 機器人 夏令營") == "中文学校 机器人 夏令营"


# ---------- field extraction ----------

@pytest.mark.parametrize("text, expected", [
    ("适合7-9岁儿童", (7, 9, "age")),
    ("适合７－９岁", (7, 9, "age")),            # full-width digits and dash
    ("年龄：6至10岁", (6, 10, "age")),
    ("適合6到10歲", (6, 10, "age")),
    ("七至九岁", (7, 9, "age")),
    ("7歲以上", (7, None, "age")),
    ("8岁以下", (None, 8, "age")),
    ("一至三年级", (6, 9, "grade")),
    ("K-2年级", (5, 8, "grade")),
    ("Ages 7-9", (7, 9, "age")),
    ("Grades 1st – 3rd", (6, 9, "grade")),
    ("Ages 6-8 / 6-8岁", (6, 8, "age")),
    ("2027年报名", (None, None, None)),         # a year is not an age
    ("适合小朋友", (None, None, None)),          # no age stated -> nothing guessed
])
def test_parse_age_multilingual(text, expected):
    assert parse_age(text)[1:] == expected


@pytest.mark.parametrize("text, expected", [
    ("学费：$450/周（报名费$25另计）", "$450/周"),
    ("学费:$480/周(报名费$25另计)", "$480/周"),
    ("報名費$30，學費：每學期$380", "$380"),
    ("费用 450美元", "450美元"),
    ("学费：免费", "免费"),
    ("免费停车，欢迎参加", None),               # free parking is not a free class
    ("费用请咨询", None),
    ("Tuition: $300 per session. Registration fee $25.", "$300 per session"),
])
def test_find_price_multilingual(text, expected):
    assert find_price(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("2027年6月14日至6月18日", ("2027-06-14", "2027-06-18")),
    ("2027年6月14日-2027年6月18日", ("2027-06-14", "2027-06-18")),
    ("上課日期：2027年1月9日至2027年5月22日", ("2027-01-09", "2027-05-22")),
    ("6月14日～18日", ("6月14日", "6月18日")),        # no year published -> kept as published
    ("日期 2027/6/14", ("2027-06-14", "2027-06-14")),
    ("June 14 – 18, 2027", ("2027-06-14", "2027-06-18")),
    ("报名截止日期：2月20日", (None, None)),           # a single date is not a session range
    ("2027年2月30日至3月2日", ("2月30日", "2027-03-02")),  # invalid date is never "fixed"
])
def test_find_dates_multilingual(text, expected):
    assert find_dates(text) == expected


def test_schedule_and_enrollment_multilingual():
    assert find_schedule("时间：周一至周五 9:00-15:00") == "周一至周五 9:00-15:00"
    assert find_schedule("每週六 上午9點到12點") == "每週六 上午9點到12點"
    assert find_schedule("Ages 6-9, 7-8岁") is None
    assert find_enrollment("报名中，名额有限") == "Registration open"
    assert find_enrollment("名额已满") == "Sold out"
    assert find_enrollment("12月4日开始报名") == "Registration opens 12月4日"
    assert find_enrollment("报名截止日期：2月20日") is None   # deadline != closed
    assert find_enrollment("报名已截止") == "Registration closed"
    assert find_enrollment("立即報名") == "Register link shown"


def test_chinese_only_page(zh_config):
    r = page(zh_config, "zh-robotics", "zh_robotics.html")
    assert r["name"] == "机器人编程夏令营"                      # original title, untouched
    assert r["description"] == "为7-9岁孩子设计的机器人与编程夏令营，动手搭建并编写程序。"
    assert r["original_language"] == "zh-Hans"
    assert (r["age_min"], r["age_max"]) == (7, 9)
    assert (r["start_date"], r["end_date"]) == ("2027-06-14", "2027-06-18")
    assert r["schedule"] == "周一至周五 9:00-15:00"
    assert r["price"] == "$450/周"
    assert r["enrollment_status"] == "Registration open"
    assert r["location"] == "San Jose"                         # 圣何塞 -> canonical city
    assert r["registration_url"] == "https://camp.example.org/register/robotics-2027"
    assert r["season"] == "summer"
    assert r["translations"] == {}                             # no machine translation invented


def test_traditional_chinese_page_with_manual_translation(zh_config):
    r = page(zh_config, "tw-chinese-school", "zh_tw_school.html")
    assert r["name"] == "示例中文學校 週六班" and r["original_language"] == "zh-Hant"
    assert (r["age_min"], r["age_max"], r["price"]) == (6, 10, "$380")
    assert (r["start_date"], r["end_date"]) == ("2027-01-09", "2027-05-22")
    assert r["schedule"] == "每週六 上午9點到12點"
    assert r["enrollment_status"] == "Registration open"
    assert r["location"] == "Cupertino"
    assert r["registration_url"] == "https://school.example.org/zh-tw/apply"
    assert r["translations"]["en"] == {"name": "Example Chinese School - Saturday Class", "method": "manual"}
    shown = display(r, "en")
    assert shown["name"] == "Example Chinese School - Saturday Class" and shown["kind"] == "manual"
    assert display(r, "zh-Hans")["name"] == "示例中文學校 週六班"  # script is never converted


def test_english_only_page(zh_config):
    r = page(zh_config, "en-robotics", "en_robotics.html")
    assert r["original_language"] == "en"
    assert (r["age_min"], r["age_max"], r["price"]) == (7, 9, "$450/week")
    assert (r["start_date"], r["end_date"]) == ("2027-06-14", "2027-06-18")
    assert r["schedule"] == "Mon–Fri 9am – 3pm"
    assert display(r, "zh")["kind"] == "original_only"        # no Chinese text exists -> show original


def test_mixed_page(zh_config):
    r = page(zh_config, "mixed-art", "mixed_art.html")
    assert r["name"] == "Kids Art 儿童美术班 Drawing & Painting" and r["original_language"] == "mixed"
    assert (r["age_min"], r["age_max"]) == (6, 8)
    assert r["schedule"] == "Saturdays 10:00am - 11:30am"
    assert (r["start_date"], r["end_date"]) == ("2027-03-06", "2027-05-15")
    assert r["price"] == "$320 per term"                       # not "免费停车"
    assert r["enrollment_status"] == "Waitlist mentioned"     # 报名截止日期 is not "closed"
    assert r["registration_url"] is None                      # no register link -> not invented


def test_config_rejects_unlabelled_translation_method(tmp_path):
    cfg = tmp_path / "c"
    cfg.mkdir()
    shutil.copy(ROOT / "config/settings.json", cfg / "settings.json")
    data = json.loads((ZH / "sources.json").read_text(encoding="utf-8"))
    data["sources"][2]["translations"]["en"]["method"] = "ai"
    (cfg / "sources.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(cfg)


# ---------- encoding ----------

@pytest.mark.parametrize("enc, text", [("gbk", "机器人编程课程，适合7-9岁"), ("big5", "機器人程式課程，適合7-9歲"),
                                       ("gb2312", "夏令营")])
def test_meta_charset_is_honoured(enc, text):
    body = f'<html><head><meta charset="{enc}"></head><body>{text}</body></html>'.encode(enc)
    chosen = html_encoding("ISO-8859-1", body)    # requests' default when the header has no charset
    assert body.decode(chosen).count(text) == 1
    assert html_encoding("utf-8", body) == "utf-8"   # an explicit header charset wins


def test_json_export_import_round_trip(tmp_path):
    store = Store(tmp_path)
    courses = {"meta": {}, "courses": {"x-1": {"source_id": "x", "name": "機器人夏令營 · 编程 · Robotics",
                                               "description": "适合7-9岁 😀", "translations": {}}}}
    store.save({"sources": {}}, courses, {"candidates": {}})
    raw = (tmp_path / "courses.json").read_bytes().decode("utf-8")
    assert "機器人夏令營 · 编程" in raw and "\\u" not in raw and "?" not in raw
    assert store.load()[1] == courses


# ---------- search ----------

@pytest.fixture
def records():
    return [
        {"name": "Robotics Coding Summer Camp", "description": "Hands-on robots.", "categories": ["stem"]},
        {"name": "数学奥林匹克班", "description": "适合三年级", "categories": ["stem"]},
        {"name": "Kids Art 儿童美术班", "description": "", "categories": ["arts"]},
        {"name": "示例中文學校 週六班", "description": "學習閱讀與寫作", "categories": ["writing_reading"]},
        {"name": "Start Smart Soccer", "description": "", "categories": ["sports"]},
        {"name": "Hidden Valley Chinese School", "description": "Mandarin classes", "categories": ["writing_reading"]},
    ]


@pytest.mark.parametrize("query, expected", [
    ("机器人", ["Robotics Coding Summer Camp"]),
    ("編程", ["Robotics Coding Summer Camp"]),
    ("Math", ["数学奥林匹克班"]),
    ("美术", ["Kids Art 儿童美术班"]),
    ("art", ["Kids Art 儿童美术班"]),                 # not "Start Smart Soccer"
    ("夏令营", ["Robotics Coding Summer Camp"]),
    ("机器人夏令营", ["Robotics Coding Summer Camp"]),
    ("中文学校", ["Hidden Valley Chinese School", "示例中文學校 週六班"]),
    ("chinese school", ["Hidden Valley Chinese School", "示例中文學校 週六班"]),
    ("soccer", ["Start Smart Soccer"]),
    ("钢琴", []),
])
def test_bilingual_search(records, glossary, query, expected):
    assert sorted(r["name"] for r in search(records, query, glossary)) == sorted(expected)


# ---------- cross-language duplicates ----------

def _rec(rid, name, lang, **kw):
    base = {"id": rid, "name": name, "original_language": lang, "source_url": "https://camp.example.org/x",
            "start_date": "2027-06-14", "end_date": "2027-06-18", "age_min": 7, "age_max": 9, "price": "$450",
            "first_seen": "2026-11-15", "translations": {}}
    return {**base, **kw}


def test_cross_language_duplicate_detection(glossary):
    store = {"courses": {r["id"]: r for r in [
        _rec("a", "Robotics Summer Camp", "en"),
        _rec("b", "机器人夏令营", "zh-Hans", price="$450/周"),
        _rec("c", "机器人夏令营", "zh-Hans", start_date="2027-07-12", end_date="2027-07-16"),  # other week
        _rec("d", "Ballet Summer Camp", "en", first_seen="2026-11-16"),   # same dates, different concept
        _rec("e", "芭蕾夏令营", "zh-Hans", source_url="https://other.example.org/"),  # other provider
    ]}}
    assert link_language_variants(store, glossary) == 1
    c = store["courses"]
    assert c["b"]["duplicate_of"] == "a"
    assert c["a"]["translations"]["zh"]["name"] == "机器人夏令营"
    assert c["a"]["translations"]["zh"]["method"] == "provider"
    assert c["a"]["name"] == "Robotics Summer Camp"               # original never overwritten
    assert c["c"]["duplicate_of"] is None and c["d"]["duplicate_of"] is None and c["e"]["duplicate_of"] is None
    assert link_language_variants(store, glossary) == 1           # idempotent


def test_same_language_records_are_never_merged(glossary):
    store = {"courses": {"a": _rec("a", "Robotics Summer Camp", "en"),
                         "b": _rec("b", "Robotics Summer Camp", "en")}}
    assert link_language_variants(store, glossary) == 0


# ---------- OCR ----------

def test_poster_text_extraction(zh_config, monkeypatch):
    """Extraction from the poster's text (ground truth of poster_zh.png), independent of the OCR engine."""
    monkeypatch.setattr(ocr, "ocr_image", lambda data: (ZH / "poster_zh.txt").read_text(encoding="utf-8"))
    src = source(zh_config, "poster-robotics")
    r = extract("", src, src.url, zh_config.cities, (ZH / "poster_zh.png").read_bytes())[0]
    assert r["extraction"] == "ocr" and r["name"] == "机器人编程夏令营 (海报)"
    assert (r["age_min"], r["age_max"], r["price"]) == (7, 9, "$480/周")
    assert (r["start_date"], r["end_date"]) == ("2027-07-12", "2027-07-16")
    assert r["schedule"] == "周一至周五 9:00-15:00"
    assert r["enrollment_status"] == "Registration open"
    assert r["registration_url"] == "https://camp.example.org/register/poster"
    assert "示例科学中心" in r["description"]


@pytest.mark.skipif(not {"chi_sim"} <= ocr.available_languages(),
                    reason="tesseract with chi_sim not installed (brew install tesseract tesseract-lang)")
def test_poster_ocr_engine():
    text = ocr.ocr_image((ZH / "poster_zh.png").read_bytes()).replace(" ", "")
    for expected in ("机器人", "夏令营", "7-9岁", "2027年7月12日", "$480"):
        assert expected in text


def test_missing_ocr_engine_is_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    with pytest.raises(ocr.OCRUnavailable, match="not installed"):
        ocr.ocr_image(b"png")


# ---------- end to end ----------

def test_bilingual_run_report_and_persistence(zh_config, tmp_path, monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)   # behave the same with or without tesseract
    params = {"min_age": 7, "max_age": 8, "categories": list(zh_config.categories), "mode": "refresh_known_sources"}
    store = Store(tmp_path / "data")
    r1 = run_discovery(zh_config, store, FixtureFetcher(ZH), params, now=RUN1)
    courses = r1["courses"]["courses"]
    zh = next(c for c in courses.values() if c["source_id"] == "zh-robotics")
    en = next(c for c in courses.values() if c["source_id"] == "en-robotics")
    assert zh["duplicate_of"] == en["id"] or en["duplicate_of"] == zh["id"]
    poster = next(s for s in r1["source_results"] if s["id"] == "poster-robotics")
    assert poster["status"] == "EMPTY_RESULT" and "not installed" in poster["error"]

    md = build_report(r1, zh_config)
    assert md.count("Robotics Coding Summer Camp") + md.count("机器人编程夏令营") >= 2
    assert "🌐" in md and "_(provider)_" in md
    assert "## 🆕 New activities (3)" in md            # the linked twin is not counted twice
    assert "示例中文學校 週六班" in md and "_(translation)_" in md

    raw = (tmp_path / "data/courses.json").read_text(encoding="utf-8")
    assert "机器人编程夏令营" in raw and "示例中文學校" in raw and "\\u" not in raw

    r2 = run_discovery(zh_config, store, FixtureFetcher(ZH), params, now=RUN2)
    statuses = {c["source_id"]: c["status"] for c in r2["courses"]["courses"].values()}
    assert statuses == {"zh-robotics": "UNCHANGED", "en-robotics": "UNCHANGED",
                        "tw-chinese-school": "UNCHANGED", "mixed-art": "UNCHANGED"}


def test_backend_returns_unescaped_chinese_and_searches(tmp_path, monkeypatch):
    pytest.importorskip("flask")
    pytest.importorskip("flask_cors")
    data = tmp_path / "courses.json"
    data.write_text(json.dumps({"courses": {
        "a": {"id": "a", "name": "Robotics Summer Camp", "original_language": "en", "provider": "X",
              "translations": {"zh": {"name": "机器人夏令营", "method": "provider"}}},
        "b": {"id": "b", "name": "机器人夏令营", "original_language": "zh-Hans", "provider": "X", "duplicate_of": "a",
              "translations": {}},
        "c": {"id": "c", "name": "Ballet", "original_language": "en", "provider": "Y", "translations": {}},
    }}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("COURSES_FILE", str(data))
    monkeypatch.setenv("SETTINGS_FILE", str(ROOT / "config/settings.json"))
    import importlib
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    app_module = importlib.import_module("app")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    resp = client.get("/courses?q=" + "機器人" + "&lang=zh")
    assert resp.status_code == 200 and "charset=utf-8" in resp.headers["Content-Type"]
    body = resp.get_data(as_text=True)
    assert "机器人夏令营" in body and "\\u" not in body
    items = resp.get_json()
    assert [i["id"] for i in items] == ["a"]                              # duplicate hidden, Ballet filtered out
    assert items[0]["display"] == {"name": "机器人夏令营", "description": None, "language": "zh", "kind": "provider"}
    assert items[0]["name"] == "Robotics Summer Camp"                     # original still returned
    assert len(client.get("/courses").get_json()) == 2


def test_discovery_matches_chinese_keywords():
    from activity_tracker.discovery import find_candidates
    settings = json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))
    html = ('<a href="/zh/coding-camp">少儿编程夏令营</a><a href="/zh/piano">钢琴课程</a>'
            '<a href="/zh/about">关于我们</a><a href="/zh/donate">捐款</a>')
    found = {c["url"]: c["suggested_categories"]
             for c in find_candidates(html, "https://x.example.org/zh/", settings, settings["categories"])}
    assert found == {"https://x.example.org/zh/coding-camp": ["stem", "camps"],
                     "https://x.example.org/zh/piano": ["music"]}


def test_registration_link_to_the_page_itself_is_ignored(zh_config):
    src = source(zh_config, "mixed-art")
    html = '<main><h1>Art</h1><p>Ages 6-8</p><a href="/kids-art#form">Registration info</a></main>'
    assert extract(html, src, src.url, zh_config.cities)[0]["registration_url"] is None
