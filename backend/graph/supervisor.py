import json

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from config import settings
from graph.state import IntelligenceState
from tools.rate_limiter import acquire_groq_slot
from agents.planner import run_planner
from agents.memory_agent import check_and_store_memory
from agents.lead_discovery import discover_leads
from agents.lead_enrichment import enrich_leads
from agents.data_validator import validate_data
from agents.export_agent import generate_export

_AGENT_REGISTRY = {
    "planner": run_planner,
    "memory_agent": check_and_store_memory,
    "lead_discovery": discover_leads,
    "lead_enrichment": enrich_leads,
    "data_validator": validate_data,
    "export_agent": generate_export,
}

_SUPERVISOR_PROMPT = f"""You are the supervisor of a lead-discovery AI platform.
Available agents: {list(_AGENT_REGISTRY.keys())}

Agent responsibilities:
- planner: Generates the frozen per-job opportunity-category list and search strategy from the JobBrief
- memory_agent: Checks semantic cache for a prior run matching this objective; if hit, skips to export
- lead_discovery: Finds business leads via browser search; loops until the requested count is met
- lead_enrichment: Verifies contact details, checks website health, scores each lead
- data_validator: Deduplicates leads and filters out low-quality entries
- export_agent: Writes the final Excel file (always Excel, no other format)

Based on the objective, return a JSON array of agent names in ORDER.
Always start with planner.
Always include memory_agent before lead_discovery.
Always end with export_agent.
Return ONLY a valid JSON array. No explanation."""


async def run_supervisor(state: IntelligenceState) -> dict:
    active_agents = state.get("active_agents", [])

    if not active_agents:
        active_agents = await _plan_agent_sequence(state)
        return {"active_agents": active_agents, "status": "running"}

    if state.get("status") == "memory_hit":
        return {"active_agents": ["export_agent"], "status": "running"}

    return {"active_agents": active_agents}


async def _plan_agent_sequence(state: IntelligenceState) -> list[str]:
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0.0,
        api_key=settings.GROQ_API_KEY,
    )

    async with acquire_groq_slot(estimated_tokens=400):
        response = await llm.ainvoke([
            SystemMessage(content=_SUPERVISOR_PROMPT),
            HumanMessage(content=f"Objective: {state.get('objective', '')}"),
        ])

    try:
        agents = json.loads(response.content)
        if isinstance(agents, list):
            return [a for a in agents if a in _AGENT_REGISTRY]
    except (json.JSONDecodeError, ValueError):
        pass

    return [
        "planner", "memory_agent",
        "lead_discovery", "lead_enrichment", "data_validator",
        "export_agent",
    ]


def _route_next_agent(state: IntelligenceState) -> str:
    active = state.get("active_agents", [])
    if not active:
        return END
    return active[0]


def _make_agent_wrapper(agent_name: str, agent_fn):
    async def wrapped(state: IntelligenceState) -> dict:
        result = await agent_fn(state)
        remaining = state.get("active_agents", [])[1:]
        return {**result, "active_agents": remaining}
    wrapped.__name__ = agent_name
    return wrapped


def _build_graph() -> StateGraph:
    graph = StateGraph(IntelligenceState)

    graph.add_node("supervisor", run_supervisor)
    for name, fn in _AGENT_REGISTRY.items():
        graph.add_node(name, _make_agent_wrapper(name, fn))

    graph.set_entry_point("supervisor")

    all_node_names = list(_AGENT_REGISTRY.keys())
    routing_map = {name: name for name in all_node_names}
    routing_map[END] = END

    graph.add_conditional_edges("supervisor", _route_next_agent, routing_map)

    for name in all_node_names:
        graph.add_edge(name, "supervisor")

    return graph


_compiled_graph = _build_graph()
intelligence_graph = _compiled_graph.compile()
