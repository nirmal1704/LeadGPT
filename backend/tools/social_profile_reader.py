from playwright.async_api import Page


async def extract_social_bio(page: Page, profile_url: str) -> dict:
    platform = _detect_platform(profile_url)

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
    except Exception:
        return _empty_result(platform)

    if await _is_login_gated(page, platform):
        return _empty_result(platform)

    if platform == "instagram":
        return await _extract_instagram_bio(page, platform)
    elif platform == "linkedin":
        return await _extract_linkedin_bio(page, platform)

    return _empty_result(platform)


async def _extract_instagram_bio(page: Page, platform: str) -> dict:
    try:
        display_name = await page.locator("h2").first.inner_text(timeout=5000)
    except Exception:
        display_name = None

    try:
        bio_text = await page.locator("span._ap3a").first.inner_text(timeout=5000)
    except Exception:
        bio_text = None

    try:
        external_url_el = page.locator("a[href*='l.instagram.com']").first
        external_url = await external_url_el.get_attribute("href", timeout=3000)
    except Exception:
        external_url = None

    return {"display_name": display_name, "bio_text": bio_text, "external_url": external_url, "platform": platform}


async def _extract_linkedin_bio(page: Page, platform: str) -> dict:
    try:
        display_name = await page.locator("h1").first.inner_text(timeout=5000)
    except Exception:
        display_name = None

    try:
        bio_text = await page.locator(".org-top-card-summary__tagline").first.inner_text(timeout=5000)
    except Exception:
        bio_text = None

    try:
        website_el = page.locator("a[data-tracking-control-name='top-card_website']").first
        external_url = await website_el.get_attribute("href", timeout=3000)
    except Exception:
        external_url = None

    return {"display_name": display_name, "bio_text": bio_text, "external_url": external_url, "platform": platform}


async def _is_login_gated(page: Page, platform: str) -> bool:
    current_url = page.url
    if platform == "instagram" and "accounts/login" in current_url:
        return True
    if platform == "linkedin" and "authwall" in current_url:
        return True
    return False


def _detect_platform(profile_url: str) -> str:
    if "instagram.com" in profile_url:
        return "instagram"
    if "linkedin.com" in profile_url:
        return "linkedin"
    return "unknown"


def _empty_result(platform: str) -> dict:
    return {"display_name": None, "bio_text": None, "external_url": None, "platform": platform}
