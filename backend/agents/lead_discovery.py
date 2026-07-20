import json
import logging
import urllib.parse

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from graph.state import IntelligenceState
from tools.rate_limiter import acquire_groq_slot
from tools.browser_operator import execute_browser_task
from db.memory_store import log_job_event, update_job_progress

logger = logging.getLogger(__name__)

_MAX_QUERIES_PER_ROUND = 4
_SAFETY_MULTIPLIER = 3  # stop at leads_requested × 3 even if still looping

_QUERY_GENERATION_PROMPT = """You are a web research agent for a lead-discovery platform.
Given a job brief and a list of opportunity categories, generate search queries to find
businesses in the target category and location that may match one of those categories.

Include a mix of:
- Google Maps queries:     "{lead_category}" "{location}"
- Google Search directory: "{lead_category}" site:justdial.com OR site:sulekha.com OR site:yellowpages.com
- Direct Google search:    "{lead_category} {location} contact"
- Social media dorks:      site:instagram.com "{lead_category}" "{location}"
- Category-specific:       "{lead_category} {location} no website" (for no_website category)

Return ONLY a valid JSON array of query strings. No explanation. No markdown.
Generate exactly 4 queries — each targeting a different source or angle."""

_EXTRACTION_PROMPT = """You are a structured data extraction agent.
From the browser search result text provided, extract ONLY business listings that
appear explicitly in the text. Do NOT invent or infer any field value.

Return a JSON array of objects. Each object must have:
  name:             the business name as it appears in the text (string, required)
  address:          full address if shown, else "" (string)
  phone:            phone number as shown, else "" (string)
  website_url:      URL of the business website if shown, else "" (string)
  source_url:       the URL of the page or search result where this business appeared (string)
  social_media_url: Instagram/LinkedIn profile URL if shown, else "" (string)

Rules:
- If a field is not present in the text, use "".
- Do not paraphrase or correct business names.
- Return ONLY valid JSON. No markdown. No explanation."""


async def discover_leads(state: IntelligenceState) -> dict:
    brief = state.get("job_brief", {})
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

        for query in queries[:_MAX_QUERIES_PER_ROUND]:
            if len(all_leads) >= leads_requested:
                break

            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            task_text = (
                f"Navigate directly to this URL: {search_url}\n"
                "Extract all visible business listings: name, address, phone, website URL. "
                "Return the extracted data as a JSON array."
            )
            raw = await execute_browser_task(task_text, use_stealth=True)
            batch = await _extract_leads(llm, raw, query)

            for lead in batch:
                norm = _norm(lead.get("name", ""))
                if not norm or norm in seen_names:
                    continue
                seen_names.add(norm)
                all_leads.append(lead)

        update_job_progress(job_id, "searching", len(all_leads))
        log_job_event(job_id, f"Discovery round {round_num} complete — {len(all_leads)} candidates so far")

        # Stop early if a full round added no new leads
        if len(all_leads) == len(existing_leads) and round_num > 1:
            log_job_event(job_id, "No new leads in last round — stopping early", level="warning")
            break

    log_job_event(job_id, f"Lead discovery finished — {len(all_leads)} unique candidates found")
    return {
        "discovered_leads": all_leads,
        "leads_found_so_far": len(all_leads),
    }


async def _generate_queries(llm: ChatGroq, brief: dict, state: IntelligenceState) -> list[str]:
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

    async with acquire_groq_slot(estimated_tokens=600):
        response = await llm.ainvoke([
            SystemMessage(content=_QUERY_GENERATION_PROMPT),
            HumanMessage(content=prompt_body),
        ])

    try:
        queries = json.loads(response.content)
        if isinstance(queries, list):
            return [str(q) for q in queries if q]
    except (json.JSONDecodeError, ValueError):
        pass

    return [f"{brief.get('lead_category', 'businesses')} {brief.get('location', '')} contact"]


async def _extract_leads(llm: ChatGroq, raw_result: str, source_url: str) -> list[dict]:
    if not raw_result.strip():
        return []

    async with acquire_groq_slot(estimated_tokens=1200):
        response = await llm.ainvoke([
            SystemMessage(content=_EXTRACTION_PROMPT),
            HumanMessage(content=f"Source URL: {source_url}\n\nBrowser result text:\n{raw_result[:5000]}"),
        ])

    try:
        leads = json.loads(response.content)
        if isinstance(leads, list):
            for lead in leads:
                for key in ("name", "address", "phone", "website_url", "source_url", "social_media_url"):
                    if not isinstance(lead.get(key), str):
                        lead[key] = ""
                if not lead.get("source_url"):
                    lead["source_url"] = source_url
            return leads
    except (json.JSONDecodeError, ValueError):
        pass

    return []


def _norm(name: str) -> str:
    """Normalise a business name for deduplication."""
    return name.strip().lower()
