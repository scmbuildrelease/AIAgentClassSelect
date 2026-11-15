"""Polite HTTP fetching: honest user agent, robots.txt, per-host delay, retries."""
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

log = logging.getLogger(__name__)
RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: str  # OK | HTTP_ERROR | NETWORK_ERROR | BLOCKED_BY_ROBOTS
    http_status: int | None = None
    final_url: str | None = None
    html: str = ""
    error: str | None = None


class Fetcher:
    def __init__(self, settings: dict, session: requests.Session | None = None, sleep=time.sleep):
        req = settings.get("request", {})
        self.user_agent = req["user_agent"]
        self.timeout = req.get("timeout_seconds", 20)
        self.retries = req.get("retries", 2)
        self.delay = req.get("delay_seconds", 2.0)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent, "Accept": "text/html,*/*;q=0.8"})
        self._sleep = sleep
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}

    def _wait_for_host(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            remaining = self.delay - (time.monotonic() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_hit[host] = time.monotonic()

    def _allowed(self, url: str) -> bool:
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = None
            try:
                self._wait_for_host(p.netloc)
                r = self.session.get(f"{host}/robots.txt", timeout=self.timeout)
                if r.status_code == 200:
                    rp = RobotFileParser()
                    rp.parse(r.text.splitlines())
            except requests.RequestException as e:
                log.warning("robots.txt unavailable for %s: %s", host, e)
            self._robots[host] = rp  # None = no usable robots.txt -> allowed
        rp = self._robots[host]
        return rp is None or rp.can_fetch(self.user_agent, url)

    def get(self, url: str) -> FetchResult:
        if not self._allowed(url):
            return FetchResult(url, False, "BLOCKED_BY_ROBOTS", error="Disallowed by robots.txt")
        host = urlparse(url).netloc
        last_error, last_status = None, None
        for attempt in range(self.retries + 1):
            if attempt:
                self._sleep(2 * attempt)
            self._wait_for_host(host)
            try:
                r = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as e:
                last_error, last_status = f"{type(e).__name__}: {e}", None
                log.warning("attempt %d failed for %s: %s", attempt + 1, url, last_error)
                continue
            if r.status_code == 200:
                if not r.encoding or r.encoding.lower() == "iso-8859-1":
                    r.encoding = r.apparent_encoding
                return FetchResult(url, True, "OK", 200, r.url, r.text)
            last_status, last_error = r.status_code, f"HTTP {r.status_code}"
            if r.status_code not in RETRY_STATUSES:
                break
        status = "HTTP_ERROR" if last_status else "NETWORK_ERROR"
        return FetchResult(url, False, status, last_status, error=last_error)


class FixtureFetcher:
    """Offline fetcher for tests and demos. manifest.json maps URL -> {"file": ...} or {"status": 403}."""

    def __init__(self, fixture_dir: Path):
        self.dir = Path(fixture_dir)
        self.manifest = json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))
        self.requested: list[str] = []

    def get(self, url: str) -> FetchResult:
        self.requested.append(url)
        entry = self.manifest.get(url)
        if entry is None:
            return FetchResult(url, False, "NETWORK_ERROR", error="ConnectionError: fixture not found")
        if "file" in entry:
            html = (self.dir / entry["file"]).read_text(encoding="utf-8")
            return FetchResult(url, True, "OK", 200, url, html)
        if entry.get("robots_blocked"):
            return FetchResult(url, False, "BLOCKED_BY_ROBOTS", error="Disallowed by robots.txt")
        code = entry.get("status", 500)
        return FetchResult(url, False, "HTTP_ERROR", code, error=f"HTTP {code}")
