from unittest.mock import MagicMock

import requests

from activity_tracker.fetcher import Fetcher

SETTINGS = {"request": {"user_agent": "TestBot/1.0", "timeout_seconds": 5, "retries": 2, "delay_seconds": 0}}


def response(status, text=""):
    r = MagicMock(status_code=status, text=text, url="https://x.example.org/page", encoding="utf-8")
    return r


def fetcher_with(responses):
    session = MagicMock(headers={})
    session.get.side_effect = responses
    return Fetcher(SETTINGS, session=session, sleep=lambda s: None), session


def test_respects_robots_disallow():
    f, session = fetcher_with([response(200, "User-agent: *\nDisallow: /private")])
    res = f.get("https://x.example.org/private/camps")
    assert res.status == "BLOCKED_BY_ROBOTS" and not res.ok
    assert session.get.call_count == 1  # only robots.txt was requested


def test_retries_transient_errors_then_succeeds():
    f, session = fetcher_with([response(404), response(503), requests.ConnectionError("reset"),
                               response(200, "<html>ok</html>")])
    res = f.get("https://x.example.org/page")
    assert res.ok and res.html == "<html>ok</html>" and session.get.call_count == 4


def test_does_not_retry_client_errors_and_reports_status():
    f, session = fetcher_with([response(404), response(403)])
    res = f.get("https://x.example.org/page")
    assert (res.ok, res.status, res.http_status, res.error) == (False, "HTTP_ERROR", 403, "HTTP 403")
    assert session.get.call_count == 2


def test_network_failure_after_retries():
    f, _ = fetcher_with([response(404)] + [requests.Timeout("slow")] * 3)
    res = f.get("https://x.example.org/page")
    assert res.status == "NETWORK_ERROR" and "Timeout" in res.error


def test_sends_honest_user_agent():
    f, session = fetcher_with([])
    assert session.headers["User-Agent"] == "TestBot/1.0"
