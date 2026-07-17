"""
Content extractor using crawl4ai==0.5.0.

Import paths: from crawl4ai import AsyncWebCrawler, CacheMode
              from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
result.markdown is MarkdownGenerationResult — use str() to get raw text.
"""

import asyncio
import logging

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

from config import settings

logger = logging.getLogger(__name__)


def _make_browser_config() -> BrowserConfig:
    return BrowserConfig(browser_type="firefox", headless=True, verbose=False)


def _make_run_config() -> CrawlerRunConfig:
    return CrawlerRunConfig(
        word_count_threshold=10,
        cache_mode=CacheMode.BYPASS,
        exclude_social_media_links=True,
        verbose=False,
    )


async def extract_page_content(url: str) -> dict:
    """
    Extract structured content from a URL.

    Returns a dict with keys: markdown, status_code, url, is_https, title,
    meta_description, h1_tags, internal_links_count, has_mobile_viewport.
    """
    async with AsyncWebCrawler(config=_make_browser_config()) as crawler:
        result = await crawler.arun(url=url, config=_make_run_config())

    if not result.success:
        logger.warning("crawl4ai failed for %s: %s", url, result.error_message)
        return _empty_result(url)

    return _build_result_dict(result)


async def batch_extract(urls: list[str]) -> list[dict]:
    """
    Extract content from multiple URLs concurrently.

    Concurrency is capped at settings.MAX_CONCURRENT_PAGES to prevent OOM
    on the 3 GB worker container (each arun() opens a full browser context).
    """
    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_PAGES)

    async def _crawl_one(url: str) -> dict:
        async with semaphore:
            return await extract_page_content(url)

    results = await asyncio.gather(*[_crawl_one(u) for u in urls], return_exceptions=True)

    output = []
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            logger.warning("batch_extract failed for %s: %s", url, result)
            output.append(_empty_result(url))
        else:
            output.append(result)

    return output


def _build_result_dict(result) -> dict:
    metadata = result.metadata or {}
    html_source = result.cleaned_html or result.html or ""
    internal_links = (result.links or {}).get("internal", [])
    markdown_text = str(result.markdown) if result.markdown is not None else ""

    return {
        "markdown": markdown_text,
        "status_code": result.status_code,
        "url": result.url,
        "is_https": result.url.startswith("https://"),
        "title": metadata.get("title") or "",
        "meta_description": metadata.get("description") or "",
        "h1_tags": _extract_h1_tags(html_source),
        "internal_links_count": len(internal_links),
        "has_mobile_viewport": _check_mobile_viewport(html_source),
    }


def _extract_h1_tags(html: str) -> list[str]:
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "lxml")
        return [tag.get_text(strip=True) for tag in soup.find_all("h1") if tag.get_text(strip=True)]
    except Exception:
        return []


def _check_mobile_viewport(html: str) -> bool:
    if not html:
        return False
    try:
        soup = BeautifulSoup(html, "lxml")
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            return False
        return "width=device-width" in viewport.get("content", "")
    except Exception:
        return False


def _empty_result(url: str) -> dict:
    return {
        "markdown": "",
        "status_code": None,
        "url": url,
        "is_https": url.startswith("https://"),
        "title": "",
        "meta_description": "",
        "h1_tags": [],
        "internal_links_count": 0,
        "has_mobile_viewport": False,
    }
