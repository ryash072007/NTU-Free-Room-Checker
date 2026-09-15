"""Playwright browser lifecycle helpers."""

from contextlib import contextmanager
from collections.abc import Iterator

from playwright.sync_api import Browser, Page, Playwright, sync_playwright


@contextmanager
def browser_page(*, headless: bool = True) -> Iterator[Page]:
    playwright: Playwright = sync_playwright().start()
    browser: Browser | None = None
    try:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        yield context.new_page()
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()
