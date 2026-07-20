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


async def run_browser_task(
    task: str,
    browser,
    max_steps: int = 20,
) -> str:
    """Run a browser-use Agent task and return the final result string."""
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0.0,
        api_key=settings.GROQ_API_KEY,
    )

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        register_new_step_callback=_step_delay_callback,
        use_vision=False,
        max_failures=3,
    )

    async with acquire_groq_slot(estimated_tokens=1000):
        history = await agent.run(max_steps=max_steps)

    result = history.final_result()
    return result if result is not None else ""


async def execute_browser_task(task: str, use_stealth: bool = True, max_steps: int = 20) -> str:
    """Launch a browser, run the task, and return the result. Always closes the browser on exit."""
    from tools.stealth_browser import get_stealth_browser

    if use_stealth:
        camoufox_cm, bu_browser = await get_stealth_browser()
        try:
            return await run_browser_task(task, bu_browser, max_steps=max_steps)
        finally:
            await camoufox_cm.__aexit__(None, None, None)
    else:
        from browser_use.browser.browser import Browser as BrowserUseBrowser, BrowserConfig
        bu_browser = BrowserUseBrowser(config=BrowserConfig(browser_type="firefox"))
        try:
            return await run_browser_task(task, bu_browser, max_steps=max_steps)
        finally:
            await bu_browser.close()
