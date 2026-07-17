from datetime import datetime, timedelta, timezone

import tldextract

from config import settings
from db.client import supabase_client
from db.embedding_model import generate_embedding


def check_memory(objective: str) -> dict | None:
    """Check knowledge_base for a prior run matching this objective."""
    exact = (
        supabase_client.table("knowledge_base")
        .select("*")
        .eq("content", objective)
        .gte("created_at", _seven_days_ago())
        .limit(1)
        .execute()
    )
    if exact.data:
        return exact.data[0].get("metadata")

    embedding = generate_embedding(objective)
    semantic = supabase_client.rpc(
        "match_knowledge_base",
        {
            "query_embedding": embedding,
            "similarity_threshold": settings.MEMORY_SIMILARITY_THRESHOLD,
            "match_count": 1,
            "max_age_days": 7,
        },
    ).execute()

    if semantic.data:
        return semantic.data[0].get("metadata")

    return None


def store_leads(leads: list[dict], job_id: str) -> None:
    for lead in leads:
        domain = extract_domain(lead.get("website_url", ""))
        business_payload = {
            "name": lead.get("name", ""),
            "address": lead.get("address", ""),
            "phone": lead.get("phone", ""),
            "website_url": lead.get("website_url", ""),
            "source_url": lead.get("source_url", ""),
            "domain": domain or None,
        }
        result = (
            supabase_client.table("businesses")
            .upsert(business_payload, on_conflict="name,address")
            .execute()
        )
        if result.data:
            business_id = result.data[0]["id"]
            lead_payload = {
                "job_id": job_id,
                "business_id": business_id,
                "opportunity_category": lead.get("opportunity_category", ""),
                "opportunity_score": lead.get("opportunity_score", 0),
                "pitch_angle": lead.get("pitch_angle", ""),
            }
            supabase_client.table("leads").insert(lead_payload).execute()


def store_knowledge(objective: str, metadata: dict) -> None:
    embedding = generate_embedding(objective)
    supabase_client.table("knowledge_base").insert(
        {"content": objective, "embedding": embedding, "metadata": metadata}
    ).execute()


def log_job_event(job_id: str, message: str, level: str = "info") -> None:
    supabase_client.table("job_logs").insert(
        {"job_id": job_id, "message": message, "level": level}
    ).execute()


def update_job_progress(job_id: str, current_stage: str, leads_found: int) -> None:
    """Update the scraping_jobs row with live progress for the frontend progress view."""
    try:
        supabase_client.table("scraping_jobs").update({
            "current_stage": current_stage,
            "leads_found_so_far": leads_found,
        }).eq("id", job_id).execute()
    except Exception:
        pass


def extract_domain(url: str) -> str:
    """Extract the registrable domain (e.g. 'example.com') from a URL."""
    if not url:
        return ""
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return ""


def _seven_days_ago() -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    return cutoff.isoformat()
