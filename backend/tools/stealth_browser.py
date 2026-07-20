"""
Stealth browser using CloakBrowser (cloakbrowser).

CloakBrowser provides a source-level patched stealth Chromium binary.
We launch it asynchronously and wrap its Playwright Browser in browser-use's Browser class.
"""

from cloakbrowser import launch_async
from browser_use.browser.browser import Browser as BrowserUseBrowser, BrowserConfig


async def get_stealth_browser() -> tuple[None, BrowserUseBrowser]:
    """
    Launch a CloakBrowser instance and wrap it for browser-use.

    Returns (None, browser_use_browser). We return None for the context manager
    to maintain API compatibility with the caller. The caller should call
    await browser_use_browser.close() when done.
    """
    playwright_browser = await launch_async(headless=True)
    bu_browser = _wrap_for_browser_use(playwright_browser)
    return None, bu_browser


def _wrap_for_browser_use(playwright_browser) -> BrowserUseBrowser:
    bu_browser = BrowserUseBrowser(config=BrowserConfig())
    bu_browser.playwright_browser = playwright_browser
    return bu_browser
