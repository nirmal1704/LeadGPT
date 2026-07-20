"""
Stealth browser using Camoufox (camoufox==0.4.11).

AsyncCamoufox manages the Playwright lifecycle. We wrap its raw playwright.Browser
in browser-use's Browser class by pre-assigning .playwright_browser, which causes
browser-use to skip its own chromium launch and use our camoufox instance instead.
"""

from camoufox.async_api import AsyncCamoufox
from browser_use.browser.browser import Browser as BrowserUseBrowser, BrowserConfig


async def get_stealth_browser() -> tuple[AsyncCamoufox, BrowserUseBrowser]:
    """
    Launch a Camoufox browser and wrap it for browser-use.

    Returns (context_manager, browser_use_browser). The caller must call
    await context_manager.__aexit__(None, None, None) when done.
    """
    camoufox_cm = AsyncCamoufox(
        headless=True,
        humanize=True,
    )
    playwright_browser = await camoufox_cm.__aenter__()
    bu_browser = _wrap_for_browser_use(playwright_browser)
    return camoufox_cm, bu_browser


def _wrap_for_browser_use(playwright_browser) -> BrowserUseBrowser:
    bu_browser = BrowserUseBrowser(config=BrowserConfig())
    bu_browser.playwright_browser = playwright_browser
    return bu_browser
