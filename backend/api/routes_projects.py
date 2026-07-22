from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.routes_auth import get_current_user
from db.client import supabase_client

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    company_name: str = ""
    default_offering: str = ""


@router.post("")
async def create_project(body: ProjectCreate, user_id: str = Depends(get_current_user)):
    result = supabase_client.table("projects").insert({
        "user_id": user_id,
        "name": body.name,
        "description": body.description,
        "company_name": body.company_name,
        "default_offering": body.default_offering,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create project")

    return {"project_id": result.data[0]["id"]}


@router.get("")
async def list_projects(user_id: str = Depends(get_current_user)):
    result = supabase_client.table("projects").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return result.data or []
