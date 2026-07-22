import logging

from graph.state import IntelligenceState
from db.client import supabase_client
from db.memory_store import log_job_event, update_job_progress, extract_domain

logger = logging.getLogger(__name__)

_LOW_PRIORITY_THRESHOLD = 3  # opportunity_score below this → is_low_priority = True


async def validate_data(state: IntelligenceState) -> dict:
    job_id = state.get("job_id", "")
    enriched = state.get("enriched_leads", [])

    validated: list[dict] = []
    seen_domains: set[str] = set()
    seen_names: set[str] = set()

    dropped_missing_fields = 0
    dropped_duplicate_name = 0
    dropped_duplicate_domain = 0

    log_job_event(job_id, f"Data validation starting — {len(enriched)} enriched leads to validate")

    for lead in enriched:
        if not _has_required_fields(lead):
            dropped_missing_fields += 1
            logger.debug("Validator: dropped '%s' — missing required fields", lead.get("name", "?"))
            continue

        name_key = lead.get("name", "").strip().lower()
        if name_key and name_key in seen_names:
            dropped_duplicate_name += 1
            continue
        if name_key:
            seen_names.add(name_key)

        domain = extract_domain(lead.get("website_url", ""))
        if domain:
            if domain in seen_domains:
                dropped_duplicate_domain += 1
                continue
            seen_domains.add(domain)

        score = lead.get("opportunity_score", 5)
        lead["is_low_priority"] = int(score) < _LOW_PRIORITY_THRESHOLD

        if not lead.get("opportunity_category"):
            lead["opportunity_category"] = "unknown"

        validated.append(lead)

    final_count = len(validated)
    total_dropped = dropped_missing_fields + dropped_duplicate_name + dropped_duplicate_domain
    log_job_event(
        job_id,
        f"Data validation complete — {final_count} verified leads kept, "
        f"{total_dropped} dropped "
        f"(missing fields: {dropped_missing_fields}, "
        f"duplicate name: {dropped_duplicate_name}, "
        f"duplicate domain: {dropped_duplicate_domain})"
    )
    update_job_progress(job_id, "building", final_count)

    return {
        "validated_leads": validated,
        "leads_found_so_far": final_count,
    }


def _has_required_fields(lead: dict) -> bool:
    """Keep a lead if it has a name and at least one reachable contact signal."""
    if not lead.get("name", "").strip():
        return False
    return any([
        lead.get("phone", "").strip(),
        lead.get("email", "").strip(),
        lead.get("social_media_url", "").strip(),
        lead.get("social_bio_text", "").strip(),
        lead.get("address", "").strip(),
    ])



