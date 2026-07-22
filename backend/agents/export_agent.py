import os

from graph.state import IntelligenceState
from tools.excel_exporter import export_to_excel
from db.client import supabase_client
from db.mongo_client import store_zipped_export
import zipfile

_EXPORTS_DIR = "/tmp/exports"


async def generate_export(state: IntelligenceState) -> dict:
    os.makedirs(_EXPORTS_DIR, exist_ok=True)

    leads = state.get("validated_leads", []) or state.get("enriched_leads", [])
    job_id = state.get("job_id", "unknown")
    job_brief = state.get("job_brief", {})
    opportunity_categories = state.get("opportunity_categories", [])
    category_rules = state.get("category_rules", {})

    file_path = os.path.join(_EXPORTS_DIR, f"{job_id}_leads.xlsx")
    export_to_excel(
        leads=leads,
        file_path=file_path,
        job_brief=job_brief,
        opportunity_categories=opportunity_categories,
        category_rules=category_rules,
    )

    zip_path = os.path.join(_EXPORTS_DIR, f"{job_id}_leads.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, os.path.basename(file_path))

    mongo_id = None
    with open(zip_path, "rb") as f:
        mongo_id = store_zipped_export(job_id, f.read())

    _record_export(job_id, zip_path, mongo_id)
    return {"export_path": zip_path}


def _record_export(job_id: str, file_path: str, mongo_id: str | None) -> None:
    try:
        supabase_client.table("exports").insert({
            "job_id": job_id,
            "file_name": os.path.basename(file_path),
            "file_type": "zip",
            "storage_path": mongo_id or file_path,
        }).execute()
    except Exception:
        pass
