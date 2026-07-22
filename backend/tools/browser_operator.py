import asyncio
import logging

from langchain_groq import ChatGroq
from browser_use import Agent
from browser_use.browser.views import BrowserState
from browser_use.agent.views import AgentOutput

from config import settings
from tools.rate_limiter import acquire_groq_slot

logger = logging.getLogger(__name__)

# Inter-step delay via register_new_step_callback — the only supported pacing
# hook in browser-use==0.1.40 (there is no step_delay parameter on Agent).
_STEP_DELAY_SECONDS = 2.0


async def _step_delay_callback(
    state: BrowserState,
    output: AgentOutput,
    step_number: int,
) -> None:
    logger.debug("Browser step %d — sleeping %.1fs", step_number, _STEP_DELAY_SECONDS)
    await asyncio.sleep(_STEP_DELAY_SECONDS)


async def run_navigation_task(
    url: str,
    browser,
    max_steps: int = 5,
) -> str:
    """Run a browser-use Agent just to navigate to a page, then return the raw HTML."""
    llm = ChatGroq(
        model=settings.GROQ_FAST_MODEL,
        temperature=0.0,
        api_key=settings.GROQ_API_KEY,
    )

    task = f"Navigate to {url} and wait for the page to fully load. Do not extract any data."

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        register_new_step_callback=_step_delay_callback,
        use_vision=False,
        max_failures=3,
    )

    # Aggressive token optimization: block all images, fonts, and stylesheets at the network level
    try:
        pw_browser = browser.playwright_browser
        if pw_browser and pw_browser.contexts:
            context = pw_browser.contexts[0]
            
            async def block_resources(route):
                if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                    await route.abort()
                else:
                    await route.continue_()
                    
            await context.route("**/*", block_resources)
    except Exception as e:
        logger.debug("Failed to set token-optimization routes: %s", e)

    async with acquire_groq_slot(estimated_tokens=1000):
        await agent.run(max_steps=max_steps)

    # After navigation is complete (or max steps reached), grab the HTML
    try:
        # bu_browser wraps the playwright browser
        pw_browser = browser.playwright_browser
        if pw_browser.contexts and pw_browser.contexts[0].pages:
            page = pw_browser.contexts[0].pages[0]
            html = await page.content()
            return html
    except Exception as e:
        logger.warning("Failed to extract HTML after navigation: %s", e)
        
    return ""


async def navigate_and_get_page_content(url: str, use_stealth: bool = True, max_steps: int = 5) -> str:
    """Tier 3 Fallback: Launch a browser, navigate to URL via agent, and return raw HTML."""
    from tools.stealth_browser import get_stealth_browser

    if use_stealth:
        _, bu_browser = await get_stealth_browser()
        try:
            return await run_navigation_task(url, bu_browser, max_steps=max_steps)
        finally:
            await bu_browser.close()
    else:
        from browser_use.browser.browser import Browser as BrowserUseBrowser, BrowserConfig
        bu_browser = BrowserUseBrowser(config=BrowserConfig(browser_type="chromium"))
        try:
            return await run_navigation_task(url, bu_browser, max_steps=max_steps)
        finally:
            await bu_browser.close()
