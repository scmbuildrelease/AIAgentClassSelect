import os
import json
import pytest
from unittest.mock import patch, MagicMock

from scrape_courses import run, safe_parse_ai, fetch

@pytest.fixture
def fake_html():
    # Simple HTML snippet your parser can handle
    return "<html><body><div class='course'>Sample Course</div></body></html>"

@pytest.fixture
def fake_courses():
    return [
        {"title": "Art Class [Age 6-8]", "link": "/art", "location": "San Jose"},
        {"title": "Music Class", "link": "/music", "location": "Sunnyvale"},
    ]

def test_safe_parse_ai_valid_json(fake_courses):
    json_str = json.dumps({"courses": fake_courses})
    parsed = safe_parse_ai(json_str)
    assert parsed == fake_courses

def test_safe_parse_ai_with_filler(fake_courses):
    # AI sometimes adds filler text
    content = "Sure! Here are the courses:\n" + json.dumps(fake_courses)
    parsed = safe_parse_ai(content)
    assert parsed == fake_courses

@patch("scrape_courses.parse_generic")
@patch("scrape_courses.fetch")
def test_run_pipeline(mock_fetch, mock_parse_generic, tmp_path, fake_courses):
    # Setup
    mock_fetch.return_value = "<html></html>"
    mock_parse_generic.return_value = fake_courses

    # Use a temporary output directory
    os.environ["COURSES_OUTPUT_DIR"] = str(tmp_path)
    os.environ["USE_AI"] = "false"

    run()

    # Check file created
    output_file = tmp_path / "courses_latest.json"
    assert output_file.exists()

    # Check content
    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["title"] == "Art Class [Age 6-8]"
