from typing import TypedDict


class IntelligenceState(TypedDict):
    # Job identification
    job_id: str
    user_id: str
    project_id: str

    # Structured brief from intake agent
    job_brief: dict

    # Human-readable one-liner rendered from job_brief (used for memory lookup)
    objective: str

    # Planner outputs — set once, never mutated by downstream agents
    plan: list[str]
    opportunity_categories: list[str]  # e.g. ["no_website", "broken_link"]
    category_rules: dict               # {"no_website": "Business has no website", ...}

    # Lead count tracking
    leads_requested: int       # from job_brief.lead_count
    leads_found_so_far: int    # updated by lead_discovery and data_validator

    # Agent pipeline control
    active_agents: list[str]

    # Lead data flowing through the pipeline
    discovered_leads: list[dict]
    enriched_leads: list[dict]
    validated_leads: list[dict]

    # Semantic memory cache context
    memory_context: dict

    # Final output
    export_path: str    # absolute path to the generated Excel file

    # Job lifecycle
    status: str
    error: str | None
