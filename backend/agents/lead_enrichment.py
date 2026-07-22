import json
import logging
import re

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from graph.state import IntelligenceState
from tools.rate_limiter import acquire_groq_slot
from tools.browser_operator import execute_browser_task
from tools.content_extractor import extract_page_content
from db.memory_store import log_job_event

logger = logging.getLogger(__name__)

_SCORING_PROMPT = """You are a lead scoring and categorisation agent.
Given a business lead and the platform's opportunity category definitions,
do two things:

1. Assign exactly ONE opportunity_category code from the provided list.
   Choose the most specific category that the observable site data supports.
   If the business has a fully functional site with no issues, use "functional"
   (or the closest equivalent in the list).

2. Set opportunity_score (integer 1–10): higher = stronger sales opportunity for
   the offering described. Base it on the category match — a business whose
   observed condition exactly matches what the offering fixes should score 8–10.

3. Write a business_summary (1-2 sentences): briefly summarize what the business does, what their pain point/need is based on the site data, and how the offering can help them. Keep it simple and factual.

Return ONLY valid JSON:
{"opportunity_category": "no_website", "opportunity_score": 9, "business_summary": "..."}"""


async def enrich_leads(state: IntelligenceState) -> dict:
    llm = ChatGroq(
        model=settings.GROQ_FAST_MODEL,
        temperature=0.0,
        api_key=settings.GROQ_API_KEY,
    )

    opportunity_categories = state.get("opportunity_categories", [])
    category_rules = state.get("category_rules", {})
    job_id = state.get("job_id", "")
    brief = state.get("job_brief", {})

    enriched: list[dict] = []
    leads = state.get("discovered_leads", [])

    log_job_event(job_id, f"Lead enrichment starting — {len(leads)} candidates to process")

    for i, lead in enumerate(leads):
        try:
            enriched_lead = await _enrich_single_lead(
                lead, llm, opportunity_categories, category_rules, brief
            )
            enriched.append(enriched_lead)
            logger.debug("[job %s] Enriched %d/%d: %s", job_id, i + 1, len(leads), lead.get("name", "?"))
        except Exception as exc:
            logger.warning("[job %s] Enrichment error for %s: %s", job_id, lead.get("name", "?"), exc)
            enriched.append({**lead, "opportunity_category": "unknown", "opportunity_score": 1, "pitch_angle": ""})

    log_job_event(job_id, f"Lead enrichment complete — {len(enriched)} leads enriched")
    return {"enriched_leads": enriched}


async def _enrich_single_lead(
    lead: dict,
    llm: ChatGroq,
    opportunity_categories: list[str],
    category_rules: dict,
    brief: dict,
) -> dict:
    enriched = dict(lead)
    website_url = lead.get("website_url", "").strip()

    # Three-strategy website discovery: social bio → Google exact → Google broad
    if not website_url:
        website_url = await _find_website_three_strategies(lead)
        enriched["website_url"] = website_url

    if website_url:
        site_data = await _crawl_website(website_url)
        enriched["site_data"] = site_data
    else:
        enriched["site_data"] = {}

    scoring = await _score_and_categorise(enriched, llm, opportunity_categories, category_rules, brief)
    enriched.update(scoring)

    return enriched


async def _find_website_three_strategies(lead: dict) -> str:
    name = lead.get("name", "").strip()
    address = lead.get("address", "").strip()
    social_url = lead.get("social_media_url", "").strip()

    # Strategy 1: extract website URL from social media bio
    if social_url:
        url = await _bio_link(social_url)
        if url:
            return url

    if not name:
        return ""

    # Strategy 2: Google search for official website
    result2 = await execute_browser_task(
        f'Search Google for the official website of "{name}" located in "{address}". '
        "Return only the website URL, nothing else.",
        use_stealth=True,
    )
    url2 = _first_url(result2)
    if url2:
        return url2

    # Strategy 3: broader search — name + contact
    location_keywords = " ".join(address.split()[:2]) if address else ""
    result3 = await execute_browser_task(
        f'Search Google for: "{name}" {location_keywords} contact site. Return the most relevant website URL.',
        use_stealth=True,
    )
    return _first_url(result3)


async def _bio_link(social_url: str) -> str:
    """Open a social profile and return the external website URL from the bio, if any."""
    try:
        result = await execute_browser_task(
            f"Open this social media profile: {social_url}. "
            "Find and return any website URL listed in the bio or profile. "
            "Return only the URL, nothing else.",
            use_stealth=True,
            max_steps=5,
        )
        return _first_url(result)
    except Exception:
        return ""


def _first_url(text: str) -> str:
    match = re.search(r'https?://[^\s"\'<>()]+', text)
    return match.group(0) if match else ""


async def _crawl_website(url: str) -> dict:
    try:
        return await extract_page_content(url)
    except Exception:
        return {
            "status_code": None,
            "is_https": url.startswith("https://"),
            "has_mobile_viewport": False,
            "title": "",
            "meta_description": "",
            "h1_tags": [],
            "internal_links_count": 0,
            "markdown": "",
        }


async def _score_and_categorise(
    lead: dict,
    llm: ChatGroq,
    opportunity_categories: list[str],
    category_rules: dict,
    brief: dict,
) -> dict:
    site_data = lead.get("site_data", {})
    website_url = lead.get("website_url", "")

    observable = {
        "has_website": bool(website_url),
        "status_code": site_data.get("status_code"),
        "is_https": site_data.get("is_https", False),
        "has_mobile_viewport": site_data.get("has_mobile_viewport", False),
        "title": site_data.get("title", ""),
        "has_h1": bool(site_data.get("h1_tags")),
        "content_length_chars": len(site_data.get("markdown", "")),
    }

    category_defs = "\n".join(
        f'  "{code}": {category_rules.get(code, code)}'
        for code in opportunity_categories
    )
    if not category_defs:
        category_defs = '  "no_website": "Business has no discoverable website."'

    prompt = (
        f"{_SCORING_PROMPT}\n\n"
        f"Allowed category codes:\n{category_defs}\n\n"
        f"Offering: {brief.get('offering', '')}\n"
        f"Lead category: {brief.get('lead_category', '')}"
    )

    async with acquire_groq_slot(estimated_tokens=500):
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Lead name: {lead.get('name', '')}\nObservable facts: {json.dumps(observable)}"),
        ])

    try:
        result = json.loads(response.content)
        category = result.get("opportunity_category", "")
        if opportunity_categories and category not in opportunity_categories:
            result["opportunity_category"] = _best_fallback_category(observable, opportunity_categories)
        return {
            "opportunity_category": result.get("opportunity_category", "unknown"),
            "opportunity_score": int(result.get("opportunity_score", 5)),
            "business_summary": str(result.get("business_summary", "")),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return {
            "opportunity_category": _best_fallback_category(observable, opportunity_categories),
            "opportunity_score": 5,
            "business_summary": "",
        }


def _best_fallback_category(observable: dict, categories: list[str]) -> str:
    """Code-side fallback when the LLM returns an invalid category code."""
    if not categories:
        return "unknown"
    if not observable.get("has_website") and "no_website" in categories:
        return "no_website"
    status = observable.get("status_code")
    if status and status >= 400 and "broken_link" in categories:
        return "broken_link"
    if not observable.get("is_https") and "insecure_http" in categories:
        return "insecure_http"
    if not observable.get("has_mobile_viewport") and "no_mobile" in categories:
        return "no_mobile"
    return categories[-1]
