from db.memory_store import check_memory, store_knowledge
from graph.state import IntelligenceState


async def check_and_store_memory(state: IntelligenceState) -> dict:
    objective = state.get("objective", "")

    if state.get("status") == "storing_memory":
        return _store_completed_run(state, objective)

    cached = check_memory(objective)
    if cached:
        return {
            "tactical_memory": cached.get("tactical_summary", "No tactical summary available."),
            "memory_context": {"source": "cache", "cached_data": cached},
        }

    return {
        "memory_context": {"source": "fresh_run"},
        "status": "running",
    }


def _store_completed_run(state: IntelligenceState, objective: str) -> dict:
    discovered = state.get("discovered_leads", [])
    
    # Generate a tactical summary based on the results
    tier_1_used = any(l.get("source", "").endswith("(JSON)") for l in discovered)
    tier_2_used = any(l.get("source", "").endswith("(Visual)") for l in discovered)
    
    tactical_summary = "Execution Summary: "
    if tier_1_used and not tier_2_used:
        tactical_summary += "Tier 1 HTTP extraction was highly successful. Avoid slow visual scraping."
    elif tier_2_used and not tier_1_used:
        tactical_summary += "Tier 1 was entirely blocked. Instruct lead_discovery to fall back to Tier 2.5 Visual Scraper immediately to save time."
    elif tier_1_used and tier_2_used:
        tactical_summary += "Tier 1 was partially blocked. Use a mix of HTTP and Visual scraping."
    else:
        tactical_summary += "No clear strategy data. Proceed normally."

    metadata = {
        "tactical_summary": tactical_summary,
        "leads_found": len(discovered),
    }
    store_knowledge(objective, metadata)
    return {"status": "completed"}
