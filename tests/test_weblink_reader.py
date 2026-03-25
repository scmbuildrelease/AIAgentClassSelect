from scrape_courses import read_weblinks

def test_read_weblinks():
    sites = read_weblinks("weblink.md")
    assert isinstance(sites, list)
    assert "url" in sites[0]
    assert "category" in sites[0]
