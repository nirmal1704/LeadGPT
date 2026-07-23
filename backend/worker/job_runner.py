import asyncio
from datetime import datetime, timezone

from worker.celery_app import celery_app
from graph.supervisor import intelligence_graph
from graph.state import IntelligenceState
from db.client import supabase_client
from db.memory_store import log_job_event


def _render_objective(brief: dict) -> str:
    """Human-readable one-liner for logs and memory lookup."""
    count = brief.get("lead_count", "?")
    category = brief.get("lead_category", "businesses")
    location = brief.get("location", "")
    parts = [f"Find {count} {category}"]
    if location:
        parts.append(f"in {location}")
    return " ".join(parts)


@celery_app.task(name="worker.job_runner.run_intelligence_job", bind=True)
def run_intelligence_job(
    self,
    job_id: str,
    brief: dict,
    user_id: str,
    project_id: str,
) -> dict:
    """
    Entry point called by POST /jobs via .delay().

    Args:
        job_id:     UUID of the scraping_jobs row (already created by the route).
        brief:      Serialised JobBrief dict (all six fields).
        user_id:    Supabase auth user ID.
        project_id: UUID of the associated project.
    """
    objective = _render_objective(brief)
    leads_requested = int(brief.get("lead_count", 10))

    _update_job_status(job_id, "running", current_stage="planning",
                       started_at=datetime.now(timezone.utc).isoformat())
    log_job_event(job_id, f"Starting job: {objective}")

    initial_state: IntelligenceState = {
        "job_brief": brief,
        "objective": objective,
        "plan": [],
        "opportunity_categories": [],
        "category_rules": {},
        "leads_requested": leads_requested,
        "leads_found_so_far": 0,
        "active_agents": [],
        "discovered_leads": [],
        "enriched_leads": [],
        "validated_leads": [],
        "memory_context": {},
        "export_path": "",
        "job_id": job_id,
        "user_id": user_id,
        "project_id": project_id,
        "status": "running",
        "error": None,
    }

    try:
        final_state = asyncio.run(intelligence_graph.ainvoke(
            initial_state,
            config={"recursion_limit": 100},
        ))
        _persist_results(job_id, final_state)

        lead_count = len(final_state.get("validated_leads", []))
        _update_job_status(
            job_id, "completed",
            current_stage="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            leads_found=lead_count,
        )
        log_job_event(job_id, f"Job completed. Leads found: {lead_count} of {leads_requested} requested.")

        return {
            "job_id": job_id,
            "status": "completed",
            "lead_count": lead_count,
            "export_path": final_state.get("export_path", ""),
        }

    except Exception as exc:
        _update_job_status(job_id, "failed", current_stage="failed")
        log_job_event(job_id, f"Job failed: {exc}", level="error")
        raise


def _persist_results(job_id: str, state: IntelligenceState) -> None:
    validated = state.get("validated_leads", [])
    # if validated:
        # store_leads(validated, job_id)


def _update_job_status(
    job_id: str,
    status: str,
    current_stage: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    leads_found: int | None = None,
) -> None:
    payload: dict = {"status": status}
    if current_stage is not None:
        payload["current_stage"] = current_stage
    if started_at:
        payload["started_at"] = started_at
    if completed_at:
        payload["completed_at"] = completed_at
    if leads_found is not None:
        payload["leads_found_so_far"] = leads_found

    supabase_client.table("scraping_jobs").update(payload).eq("id", job_id).execute()
