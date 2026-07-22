import json

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from graph.state import IntelligenceState
from tools.rate_limiter import acquire_groq_slot

_PLANNER_PROMPT = """You are a research strategist for a lead-discovery platform.
Given a structured job brief and a tactical memory summary from past jobs, produce a JSON object with two keys:

"plan": an ordered array of 4-6 concise research steps (strings), tailored to the
  lead_category and location in the brief. Use the tactical memory to avoid strategies that recently failed.

"opportunity_categories": an array of category objects, where each object has:
  "code": a snake_case identifier (e.g. "no_website", "broken_link", etc.)
  "rule": a plain-English sentence describing the observable condition that makes a
          business qualify for this category (must be checkable by crawling the web —
          no subjective judgments).
  "score": integer 1-10 representing how strong an opportunity this is for the offering
           described in the brief (10 = best match, e.g. "no_website" for a web designer).

Pick 3-6 categories that are realistic for the lead_category and offering.
Common examples (adapt as needed):
  no_website, broken_link, insecure_http, no_mobile, outdated_design,
  no_social_presence, slow_load, no_online_booking, no_google_listing,
  no_ecommerce (for retailers), no_whatsapp_link (for local service businesses).

Return ONLY valid JSON. No explanation. No markdown."""


async def run_planner(state: IntelligenceState) -> dict:
    brief = state.get("job_brief", {})
    objective = state.get("objective", "")

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0.0,
        api_key=settings.GROQ_API_KEY,
    )

    prompt_body = (
        f"Job brief:\n"
        f"  Who we are: {brief.get('user_context', '')}\n"
        f"  What we offer: {brief.get('offering', '')}\n"
        f"  Target lead type: {brief.get('lead_category', '')}\n"
        f"  Location: {brief.get('location', '')}\n"
        f"  Lead count needed: {brief.get('lead_count', 10)}\n"
        f"  Additional notes: {brief.get('additional_notes', '')}\n\n"
        f"Tactical Memory from Past Jobs: {state.get('tactical_memory', 'None')}\n\n"
        f"Objective summary: {objective}"
    )

    async with acquire_groq_slot(estimated_tokens=1000):
        response = await llm.ainvoke([
            SystemMessage(content=_PLANNER_PROMPT),
            HumanMessage(content=prompt_body),
        ])

    return _parse_planner_output(response.content)


def _parse_planner_output(content: str) -> dict:
    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Expected dict")

        raw_plan = parsed.get("plan", [])
        plan = [str(s) for s in raw_plan if s] if isinstance(raw_plan, list) else [str(raw_plan)]

        raw_categories = parsed.get("opportunity_categories", [])
        opportunity_categories: list[str] = []
        category_rules: dict[str, str] = {}

        for item in raw_categories:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            rule = str(item.get("rule", "")).strip()
            if code and rule:
                opportunity_categories.append(code)
                category_rules[code] = rule

        # Fallback if LLM returned nothing usable
        if not opportunity_categories:
            opportunity_categories = ["no_website", "broken_link", "insecure_http", "no_mobile"]
            category_rules = {
                "no_website": "Business has no discoverable website via Google Search.",
                "broken_link": "Business website returns HTTP 4xx/5xx or fails to load.",
                "insecure_http": "Business website is served over HTTP, not HTTPS.",
                "no_mobile": "Business website lacks a mobile viewport meta tag.",
            }

        return {
            "plan": plan,
            "opportunity_categories": opportunity_categories,
            "category_rules": category_rules,
        }

    except Exception:
        return {
            "plan": [content.strip()],
            "opportunity_categories": ["no_website", "broken_link", "insecure_http"],
            "category_rules": {
                "no_website": "Business has no discoverable website.",
                "broken_link": "Business website fails to load.",
                "insecure_http": "Business website is not HTTPS.",
            },
        }
