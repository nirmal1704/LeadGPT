from typing import TypedDict


class JobBrief(TypedDict):
    """
    Structured intake brief produced by intake_agent.py.

    All five required fields must be non-empty before the brief is considered
    complete and a job is submitted. `additional_notes` is optional (empty string
    if the user did not volunteer anything beyond the five required fields).
    """
    user_context: str       # who the user is / what their business does, in their own words
    offering: str           # what they want to sell or pitch to the leads
    lead_category: str      # the type or industry of businesses they want as leads
    location: str           # geography — city, region, country, "any area", etc.
    lead_count: int         # how many verified leads they want (hard target per Rule B)
    additional_notes: str   # optional extras the user volunteered; empty string if none


# Fields that MUST be non-empty / non-zero for the brief to be considered complete.
REQUIRED_FIELDS: list[str] = ["user_context", "offering", "lead_category", "location", "lead_count"]
