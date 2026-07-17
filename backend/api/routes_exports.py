import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.routes_auth import get_current_user
from db.client import supabase_client

router = APIRouter(prefix="/exports", tags=["exports"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/{job_id}/download")
async def download_export(job_id: str, user_id: str = Depends(get_current_user)):
    # Ownership check — prevents one user from downloading another user's export
    job_check = (
        supabase_client.table("scraping_jobs")
        .select("id")
        .eq("id", job_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not job_check.data:
        raise HTTPException(status_code=404, detail="Job not found")

    export_result = (
        supabase_client.table("exports")
        .select("*")
        .eq("job_id", job_id)
        .order("created_at", desc=True)
        .limit(1)
        .single()
        .execute()
    )
    if not export_result.data:
        raise HTTPException(status_code=404, detail="Export not ready — job may still be running")

    export = export_result.data
    file_path = export.get("storage_path", "")
    file_name = export.get("file_name") or os.path.basename(file_path) or f"{job_id}_leads.xlsx"

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Export file not found on disk. It may have been cleaned up after a container restart.",
        )

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("")
async def list_exports(user_id: str = Depends(get_current_user)):
    result = (
        supabase_client.table("exports")
        .select("*, scraping_jobs!inner(user_id)")
        .eq("scraping_jobs.user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []
