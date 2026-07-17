from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.routes_auth import get_current_user
from agents.intake_agent import process_intake

router = APIRouter(prefix="/intake", tags=["intake"])


class IntakeRequest(BaseModel):
    message: str
    partial_brief: dict = {}
    round_number: int = 0


@router.post("")
async def intake(body: IntakeRequest, user_id: str = Depends(get_current_user)):
    """
    Stateless intake endpoint. The caller holds and re-sends `partial_brief`
    and `round_number` on each turn. Returns either:
      {"status": "needs_info", "question": str, "partial_brief": dict, "round_number": int}
      {"status": "ready", "brief": dict, "assumptions": list[str]}
    """
    return await process_intake(
        message=body.message,
        partial_brief=body.partial_brief,
        round_number=body.round_number,
    )
