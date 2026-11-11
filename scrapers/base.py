import ipaddress
import logging
import socket
import time
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from playwright.sync_api import TimeoutError as BrowserTimeout
from playwright.sync_api import sync_playwright

from api.schemas.leads import LeadIngest
from core.config import get_settings
from core.external import ProviderUnavailable, call_provider

USER_AGENT = "FrameKathaResearchBot/1.0"
logger = logging.getLogger(__name__)


class ScrapingBlocked(Exception):
    pass


def public_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username:
        raise ScrapingBlocked("Only public HTTP(S) URLs are allowed")
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443)
    except OSError as error:
        raise ScrapingBlocked("Host resolution failed") from error
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ScrapingBlocked("Private network targets are not allowed")
    return url


class BaseScraper(ABC):
    channel: str

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._last_request = 0.0
        self._robots: dict[str, RobotFileParser] = {}

    def delay(self):
        elapsed = time.monotonic() - self._last_request
        time.sleep(max(0, self.settings.scraper_delay_seconds - elapsed))
        self._last_request = time.monotonic()

    def allowed(self, url: str) -> bool:
        public_url(url)
        origin = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}"
        if origin not in self._robots:
            self.delay()
            try:
                with httpx.Client(timeout=20, follow_redirects=False) as client:
                    response = client.get(
                        origin + "/robots.txt", headers={"User-Agent": USER_AGENT}
                    )
                if response.status_code == 404:
                    text = "User-agent: *\nAllow: /"
                elif response.status_code == 200:
                    text = response.text
                else:
                    return False
            except httpx.HTTPError:
                return False
            robot = RobotFileParser()
            robot.parse(text.splitlines())
            self._robots[origin] = robot
        robot = self._robots[origin]
        crawl_delay = robot.crawl_delay(USER_AGENT) or robot.crawl_delay("*")
        if crawl_delay:
            time.sleep(max(0, crawl_delay - (time.monotonic() - self._last_request)))
        return robot.can_fetch(USER_AGENT, url)

    def page_html(self, url: str) -> str:
        if not self.allowed(url):
            raise ScrapingBlocked("robots.txt disallows access or could not be verified")

        def fetch():
            self.delay()
            with sync_playwright() as playwright:
                proxy = self.settings.scraper_proxy
                browser = playwright.chromium.launch(
                    headless=True,
                    proxy={"server": proxy.get_secret_value()} if proxy else None,
                )
                context = browser.new_context(user_agent=USER_AGENT, service_workers="block")

                def guard(route):
                    # Only same-origin, robots-permitted requests. No private IPs,
                    # tracking endpoints, login redirects, or third-party resources.
                    target = route.request.url
                    try:
                        same_origin = urlsplit(target).netloc == urlsplit(url).netloc
                        if (
                            same_origin
                            and self.allowed(target)
                            and not any(
                                x in urlsplit(target).path.lower()
                                for x in ("login", "signin", "captcha", "challenge")
                            )
                        ):
                            route.continue_()
                        else:
                            route.abort()
                    except ScrapingBlocked:
                        route.abort()

                context.route("**/*", guard)
                try:
                    page = context.new_page()
                    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    if response is None or response.status >= 400:
                        raise ScrapingBlocked("Source unavailable or access denied")
                    html = page.content()
                    if any(
                        term in html.lower()
                        for term in (
                            "verify you are human",
                            "captcha",
                            "sign in to continue",
                        )
                    ):
                        raise ScrapingBlocked("Access challenge detected; no bypass attempted")
                    return html
                finally:
                    browser.close()

        # Playwright timeouts are converted by the caller to a failed scraper run;
        # access denials are never retried as a bypass strategy.
        for attempt in range(3):
            try:
                return fetch()
            except BrowserTimeout:
                logger.warning("scraper_browser_timeout", extra={"attempt": attempt + 1})
                if attempt == 2:
                    raise ProviderUnavailable("scraper_browser_timeout") from None
        raise ProviderUnavailable("scraper_browser_timeout")

    def get_json(self, url: str, *, headers=None, params=None) -> dict:
        def request():
            self.delay()
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()

        return call_provider("scraper_" + self.channel, request)

    @abstractmethod
    def collect(self, config: dict) -> list[LeadIngest]:
        raise NotImplementedError


def absolute_url(base: str, href: str) -> str:
    return urljoin(base, href)
