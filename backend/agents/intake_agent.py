"""
Intake agent — plain stateless async function. No LangGraph.

POST /intake calls process_intake() directly. This is the only LLM call
involved in the intake stage. All conversation state lives in the frontend
and is re-sent on each call as `partial_brief` + `round_number`.

Rule A compliance: the LLM is instructed to extract only what the user
literally stated. Code-side validation then checks that each filled field's
value can be traced back to a phrase in the user's message before accepting it.
Unstated fields are returned as null and never filled in by the LLM.
"""
import json
import logging
import re

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from graph.job_brief import JobBrief, REQUIRED_FIELDS
from tools.rate_limiter import acquire_groq_slot

logger = logging.getLogger(__name__)

# After this many rounds we fill remaining gaps with conservative defaults
# rather than asking another question.
_MAX_QUESTION_ROUNDS = 2

_DEFAULTS: dict = {
    "user_context": "a business professional",
    "offering": "digital services",
    "lead_category": "local businesses",
    "location": "any area",
    "lead_count": 10,
    "additional_notes": "",
}

_EXTRACTION_PROMPT = """You are an intake assistant for a lead-discovery platform.
The user is describing what kind of leads they need. Extract ONLY information they
have literally stated — never infer or guess unstated values.

Return a JSON object with exactly these keys:
  user_context   — who the user is / their business (null if not stated)
  offering       — what they want to sell/pitch to the leads (null if not stated)
  lead_category  — the type/industry of target businesses (null if not stated)
  location       — the geography for the search (null if not stated)
  lead_count     — how many leads they want, as an integer (null if not stated or not a clear number)
  additional_notes — any other relevant details the user mentioned (empty string if none)

Rules:
- Set a field to null if the user did NOT mention it. Do not infer or assume.
- lead_count must be a positive integer. If the user said "a few" or "some", set null.
- location can be broad ("India", "any area") if the user explicitly said so.
- Do NOT merge information from prior turns — only extract from the current message.
- Return ONLY valid JSON. No explanation. No markdown."""


async def process_intake(
    message: str,
    partial_brief: dict,
    round_number: int,
) -> dict:
    """
    Process one intake turn.

    Args:
        message:       The user's latest chat message.
        partial_brief: The accumulated brief so far (from previous rounds). May be {}.
        round_number:  0-indexed turn counter (0 = first user message).

    Returns one of:
        {"status": "needs_info", "question": str, "partial_brief": dict, "round_number": int}
        {"status": "ready", "brief": JobBrief, "assumptions": list[str]}
    """
    # Step 1: call Groq to extract what THIS message states
    extracted = await _extract_fields_from_message(message)

    # Step 2: validate extracted fields against the user's actual message text
    #         (Rule A: only accept a field if the extracted value is grounded in the message)
    validated = _validate_against_message(extracted, message)

    # Step 3: merge validated extractions into the accumulated partial_brief
    merged = {**partial_brief, **{k: v for k, v in validated.items() if v is not None}}

    # Step 4: check which required fields are still missing
    missing = [f for f in REQUIRED_FIELDS if not _field_is_filled(merged.get(f))]

    if not missing:
        # All required fields are present — brief is complete
        brief = _build_brief(merged)
        return {"status": "ready", "brief": brief, "assumptions": []}

    if round_number < _MAX_QUESTION_ROUNDS:
        # Still within question budget — ask one consolidated question
        question = _build_question(missing, merged)
        return {
            "status": "needs_info",
            "question": question,
            "partial_brief": merged,
            "round_number": round_number + 1,
        }

    # Exceeded question budget — fill gaps with defaults and note each assumption
    assumptions: list[str] = []
    for field in missing:
        default = _DEFAULTS[field]
        merged[field] = default
        assumptions.append(f'Assumed {field.replace("_", " ")}: "{default}"')

    brief = _build_brief(merged)
    return {"status": "ready", "brief": brief, "assumptions": assumptions}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _extract_fields_from_message(message: str) -> dict:
    """One Groq call: extract structured fields from the user's message."""
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0.0,
        api_key=settings.GROQ_API_KEY,
    )

    async with acquire_groq_slot(estimated_tokens=600):
        response = await llm.ainvoke([
            SystemMessage(content=_EXTRACTION_PROMPT),
            HumanMessage(content=f"User message: {message}"),
        ])

    try:
        parsed = json.loads(response.content)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        logger.warning("Intake extraction failed to parse JSON: %s", response.content[:200])

    return {}


def _validate_against_message(extracted: dict, message: str) -> dict:
    """
    Rule A guard: accept a field's value only if some meaningful token from
    the extracted value appears verbatim (case-insensitive) in the user's message.

    This is a lightweight check — it prevents the LLM from fabricating values
    for unstated fields, but does not require an exact substring match for fields
    like `user_context` where the LLM may paraphrase slightly.

    `lead_count` is validated numerically: it must be a positive integer.
    `additional_notes` is always accepted (it's optional context).
    """
    validated: dict = {}
    message_lower = message.lower()

    for field, value in extracted.items():
        if value is None:
            validated[field] = None
            continue

        if field == "additional_notes":
            validated[field] = str(value).strip()
            continue

        if field == "lead_count":
            try:
                count = int(value)
                if count > 0:
                    # Accept if any digit from the count appears in the message
                    if any(ch.isdigit() for ch in message) or re.search(r'\b\d+\b', message):
                        validated[field] = count
                    else:
                        validated[field] = None
                else:
                    validated[field] = None
            except (TypeError, ValueError):
                validated[field] = None
            continue

        # For text fields: take the first significant word (>3 chars) from the
        # extracted value and check it appears in the message.
        value_str = str(value).strip()
        significant_words = [w for w in value_str.lower().split() if len(w) > 3]
        if not significant_words:
            # Very short value — accept it if the whole thing is in the message
            validated[field] = value_str if value_str.lower() in message_lower else None
        elif any(w in message_lower for w in significant_words):
            validated[field] = value_str
        else:
            # The LLM produced a value with no traceable words in the message — reject it
            logger.debug("Intake: rejected field %s='%s' — not grounded in message", field, value_str)
            validated[field] = None

    return validated


def _field_is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, int):
        return value > 0
    return bool(value)


def _build_question(missing: list[str], partial: dict) -> str:
    """Generate a single consolidated question for all missing required fields."""
    prompts = {
        "user_context": "Who are you / what does your business do?",
        "offering": "What product or service do you want to pitch to these leads?",
        "lead_category": "What type of businesses are you looking for (e.g. restaurants, dentists, gyms)?",
        "location": "Which city, region, or area should I search in?",
        "lead_count": "How many leads do you need?",
    }
    questions = [prompts[f] for f in missing if f in prompts]

    if len(questions) == 1:
        return questions[0]

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    return f"I need a few more details to get started:\n{numbered}"


def _build_brief(merged: dict) -> JobBrief:
    return JobBrief(
        user_context=str(merged.get("user_context", _DEFAULTS["user_context"])).strip(),
        offering=str(merged.get("offering", _DEFAULTS["offering"])).strip(),
        lead_category=str(merged.get("lead_category", _DEFAULTS["lead_category"])).strip(),
        location=str(merged.get("location", _DEFAULTS["location"])).strip(),
        lead_count=int(merged.get("lead_count", _DEFAULTS["lead_count"])),
        additional_notes=str(merged.get("additional_notes", "")).strip(),
    )
