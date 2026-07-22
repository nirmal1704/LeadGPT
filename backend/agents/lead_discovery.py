import json
import logging
import urllib.parse
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from graph.state import IntelligenceState
from tools.rate_limiter import acquire_groq_slot
from tools.source_extractors import extract_from_source
from tools.content_extractor import extract_with_stealth_browser
from tools.browser_operator import navigate_and_get_page_content
from db.memory_store import log_job_event, update_job_progress

logger = logging.getLogger(__name__)

_MAX_QUERIES_PER_ROUND = 4
_SAFETY_MULTIPLIER = 3  # stop at leads_requested × 3 even if still looping

_QUERY_GENERATION_PROMPT = """You are a web research agent for a lead-discovery platform.
Given a job brief, generate search queries to find businesses in the target category and location.

Available sources: google_maps, google_search, justdial, sulekha, indiamart, tradeindia, yellowpages, linkedin_dork, social_dorks, sebi_advisors

Return ONLY a valid JSON array of objects. Each object must have:
- "source": one of the available sources
- "query": the search string (do not include location in the query string itself, as it is passed separately)

Example:
[
  {"source": "google_maps", "query": "plumbers"},
  {"source": "justdial", "query": "plumbing services"},
  {"source": "linkedin_dork", "query": "plumbing contractor"}
]

Generate exactly 4 queries."""

async def discover_leads(state: IntelligenceState) -> dict:
    brief = state.get("job_brief", {})
    location = brief.get("location", "")
    leads_requested = state.get("leads_requested", 10)
    job_id = state.get("job_id", "")
    existing_leads = list(state.get("discovered_leads", []))

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0.0,
        api_key=settings.GROQ_API_KEY,
    )

    safety_ceiling = leads_requested * _SAFETY_MULTIPLIER
    round_num = 0
    all_leads: list[dict] = list(existing_leads)
    seen_names: set[str] = {_norm(l.get("name", "")) for l in all_leads}

    log_job_event(job_id, f"Lead discovery starting — target: {leads_requested} leads")
    update_job_progress(job_id, "searching", len(all_leads))

    while len(all_leads) < leads_requested and len(all_leads) < safety_ceiling:
        round_num += 1
        logger.info("[job %s] Discovery round %d — %d/%d leads so far",
                    job_id, round_num, len(all_leads), leads_requested)

        queries = await _generate_queries(llm, brief, state)

        for q_obj in queries[:_MAX_QUERIES_PER_ROUND]:
            if len(all_leads) >= leads_requested:
                break
                
            source = q_obj.get("source", "google_search")
            query = q_obj.get("query", "")
            if not query:
                continue

            # Tier 1: Hardcoded Fast Extractor
            batch = await extract_from_source(source, query, location)
            
            # Fallbacks are only for direct URLs that need scraping, but for search queries,
            # if Tier 1 yields nothing, it means no results found. However, if a source is totally blocked,
            # we could theoretically use Tier 2 to search. For simplicity, we just use the results.
            
            # If it was a google_search that yielded generic URLs, we might want to enrich them later.
            # The actual deep extraction happens in lead_enrichment.py.
            
            for lead in batch:
                norm = _norm(lead.get("name", ""))
                if not norm or norm in seen_names:
                    continue
                seen_names.add(norm)
                all_leads.append(lead)

        update_job_progress(job_id, "searching", len(all_leads))
        log_job_event(job_id, f"Discovery round {round_num} complete — {len(all_leads)} candidates so far")

        if len(all_leads) == len(existing_leads) and round_num > 1:
            log_job_event(job_id, "No new leads in last round — stopping early", level="warning")
            break

    log_job_event(job_id, f"Lead discovery finished — {len(all_leads)} unique candidates found")
    return {
        "discovered_leads": all_leads,
        "leads_found_so_far": len(all_leads),
    }


async def _generate_queries(llm: ChatGroq, brief: dict, state: IntelligenceState) -> list[dict]:
    categories = state.get("opportunity_categories", [])
    plan_text = "\n".join(state.get("plan", []))

    prompt_body = (
        f"Job brief:\n"
        f"  lead_category: {brief.get('lead_category', '')}\n"
        f"  location: {brief.get('location', '')}\n"
        f"  offering: {brief.get('offering', '')}\n"
        f"  additional_notes: {brief.get('additional_notes', '')}\n\n"
        f"Opportunity categories to target: {categories}\n\n"
        f"Research plan:\n{plan_text}"
    )

    async with acquire_groq_slot(estimated_tokens=500, model_tier="fast"):
        response = await llm.ainvoke([
            SystemMessage(content=_QUERY_GENERATION_PROMPT),
            HumanMessage(content=prompt_body),
        ])

    try:
        queries = json.loads(response.content)
        if isinstance(queries, list):
            return queries
    except (json.JSONDecodeError, ValueError):
        pass

    return [{"source": "google_maps", "query": brief.get('lead_category', 'businesses')}]

def _norm(name: str) -> str:
    """Normalise a business name for deduplication."""
    return name.strip().lower()
