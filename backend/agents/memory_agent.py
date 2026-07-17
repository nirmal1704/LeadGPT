from db.memory_store import check_memory, store_knowledge
from graph.state import IntelligenceState


async def check_and_store_memory(state: IntelligenceState) -> dict:
    objective = state.get("objective", "")

    if state.get("status") == "storing_memory":
        return _store_completed_run(state, objective)

    cached = check_memory(objective)
    if cached:
        return {
            "discovered_leads": cached.get("discovered_leads", []),
            "enriched_leads": cached.get("enriched_leads", []),
            "validated_leads": cached.get("validated_leads", []),
            "leads_found_so_far": len(cached.get("validated_leads", [])),
            "status": "memory_hit",
            "memory_context": {"source": "cache", "cached_data": cached},
        }

    return {
        "memory_context": {"source": "fresh_run"},
        "status": "running",
    }


def _store_completed_run(state: IntelligenceState, objective: str) -> dict:
    metadata = {
        "discovered_leads": state.get("discovered_leads", []),
        "enriched_leads": state.get("enriched_leads", []),
        "validated_leads": state.get("validated_leads", []),
    }
    store_knowledge(objective, metadata)
    return {"status": "completed"}
