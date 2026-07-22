from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.routes_auth import get_current_user
from db.client import supabase_client
from worker.job_runner import run_intelligence_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    brief: dict          # JobBrief serialised as dict from the frontend
    project_id: str


def _render_objective(brief: dict) -> str:
    """
    Produce a human-readable one-line summary of the brief for the
    scraping_jobs.objective column (used in job history / memory lookup).
    """
    count = brief.get("lead_count", "?")
    category = brief.get("lead_category", "businesses")
    location = brief.get("location", "")
    offering = brief.get("offering", "")
    parts = [f"Find {count} {category}"]
    if location:
        parts.append(f"in {location}")
    if offering:
        parts.append(f"— pitching {offering}")
    return " ".join(parts)


@router.post("")
async def create_job(body: JobCreate, user_id: str = Depends(get_current_user)):
    brief = body.brief

    # Inject project defaults if missing
    project_result = supabase_client.table("projects").select("company_name, default_offering").eq("id", body.project_id).single().execute()
    if project_result.data:
        if not brief.get("offering") and project_result.data.get("default_offering"):
            brief["offering"] = project_result.data["default_offering"]
        if not brief.get("company_name") and project_result.data.get("company_name"):
            brief["company_name"] = project_result.data["company_name"]

    objective = _render_objective(brief)
    leads_requested = int(brief.get("lead_count", 10))

    result = supabase_client.table("scraping_jobs").insert({
        "user_id": user_id,
        "project_id": body.project_id,
        "objective": objective,
        "status": "queued",
        "current_stage": "queued",
        "leads_found_so_far": 0,
        "leads_requested": leads_requested,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create job")

    job_id = result.data[0]["id"]

    task = run_intelligence_job.delay(
        job_id=job_id,
        brief=brief,
        user_id=user_id,
        project_id=body.project_id,
    )

    supabase_client.table("scraping_jobs").update(
        {"celery_task_id": task.id}
    ).eq("id", job_id).execute()

    return {"job_id": job_id}


@router.get("/{job_id}")
async def get_job(job_id: str, user_id: str = Depends(get_current_user)):
    job_result = (
        supabase_client.table("scraping_jobs")
        .select("*")
        .eq("id", job_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if not job_result.data:
        raise HTTPException(status_code=404, detail="Job not found")

    logs_result = (
        supabase_client.table("job_logs")
        .select("*")
        .eq("job_id", job_id)
        .order("created_at", desc=False)
        .limit(50)
        .execute()
    )

    return {
        "job": job_result.data,
        "logs": logs_result.data or [],
    }


@router.get("")
async def list_jobs(user_id: str = Depends(get_current_user)):
    result = (
        supabase_client.table("scraping_jobs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []
