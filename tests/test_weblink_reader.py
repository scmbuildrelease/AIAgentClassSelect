import os
import pytest
from scrape_courses import read_links

@pytest.fixture
def temp_weblink_file(tmp_path):
    file = tmp_path / "weblink.md"
    content = """
# Sample links
https://site1.com, Art
https://site2.com, Music
"""
    file.write_text(content, encoding="utf-8")
    return str(file)

def test_read_links(temp_weblink_file, monkeypatch):
    # Patch global WEBLINK to temporary file
    monkeypatch.setattr("scrape_courses.WEBLINK", temp_weblink_file)
    
    sites = read_links()
    assert isinstance(sites, list)
    assert sites[0][0] == "https://site1.com"
    assert sites[0][1] == "Art"
    assert sites[1][0] == "https://site2.com"
    assert sites[1][1] == "Music"
