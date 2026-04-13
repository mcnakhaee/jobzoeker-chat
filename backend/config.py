"""
Tool definitions for the OpenAI function-calling / Responses API.

Rules for keeping these in sync:
- The `name` field must exactly match the Python function name in the tool module.
- The `parameters.properties` keys must exactly match the function's keyword arguments.
- Required list must match non-optional parameters.
- When you change a function signature, update the definition here too.
"""


def _make_tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    """
    Build an OpenAI function-calling tool definition.

    Args:
        name:        Function name — must match the callable in the tool module.
        description: What the tool does (shown to the LLM).
        properties:  {param_name: (type, description)}
                     Use "string" for required strings, ["string", "null"] for optional.
        required:    Required param names. Defaults to all keys in properties.
    """
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {
                k: {"type": t, "description": d}
                for k, (t, d) in properties.items()
            },
            "required": required if required is not None else list(properties.keys()),
            "additionalProperties": False,
        },
        "strict": True,
    }


# ---------------------------------------------------------------------------
# Job search
# Dispatches to: tools/job_search.py :: find_similar_jobs(keyword, location)
# ---------------------------------------------------------------------------

SIMILAR_JOB_SEARCH_TOOL = _make_tool(
    name="find_similar_jobs",
    description=(
        "Search for job listings using a keyword and optional location. "
        "Returns a list of matching jobs with title, company, location, and description."
    ),
    properties={
        "keyword":  ("string",           "Job title, skill, or technology, e.g. 'ggplot2', 'machine learning'"),
        "location": (["string", "null"], "City or region, e.g. 'Amsterdam', 'remote'. Null to search everywhere."),
    },
    required=["keyword", "location"],  # strict mode requires all properties listed; use null for optional
)


# ---------------------------------------------------------------------------
# Notion — save jobs
# Dispatches to: tools/notion.py :: save_jobs_to_notion(database_name, jobs_summary)
# ---------------------------------------------------------------------------

SAVE_JOBS_TO_NOTION_TOOL = _make_tool(
    name="save_jobs_to_notion",
    description=(
        "Save a formatted summary of job search results to a Notion database. "
        "Creates the database if it does not already exist. "
        "Call this after find_similar_jobs when the user wants to save results."
    ),
    properties={
        "database_name": ("string", "Name for the Notion database, e.g. 'ggplot2 Jobs – Amsterdam'"),
        "jobs_summary":  ("string", "Formatted plain-text or markdown summary of the jobs to save"),
    },
)


# ---------------------------------------------------------------------------
# Notion — create freeform page
# Dispatches to: tools/notion.py :: create_notion_page(title, content)
# ---------------------------------------------------------------------------

CREATE_NOTION_PAGE_TOOL = _make_tool(
    name="create_notion_page",
    description=(
        "Create a new freeform page in Notion. "
        "Use this for cover letters, learning plans, company research notes, or "
        "any content that is not a structured job listing."
    ),
    properties={
        "title":   ("string", "Page title, e.g. 'Cover Letter – Booking.com Data Scientist'"),
        "content": ("string", "Page body as plain text or markdown"),
    },
)


# ---------------------------------------------------------------------------
# Cover letter
# Dispatches to: tools/cover_letter_generator.py :: compose_cover_letter(job_description, user_profile)
# ---------------------------------------------------------------------------

COVER_LETTER_GENERATOR_TOOL = _make_tool(
    name="compose_cover_letter",
    description=(
        "Write a tailored cover letter for a specific job. "
        "Requires the job description and the user's background. "
        "If the user profile is not available, the tool will ask the user for it."
    ),
    properties={
        "job_description": ("string", "Full text of the job posting"),
        "user_profile":    ("string", "User's skills, experience, and background. Pass empty string if unknown."),
    },
)


# ---------------------------------------------------------------------------
# Company info
# Dispatches to: tools/web_search.py :: search_company_info(company_name)
# ---------------------------------------------------------------------------

SEARCH_COMPANY_INFO_TOOL = _make_tool(
    name="search_company_info",
    description=(
        "Look up background information about a company by name: culture, recent news, "
        "glassdoor sentiment, tech stack. Use this before applying or writing a cover letter."
    ),
    properties={
        "company_name": ("string", "Company name, e.g. 'Booking.com', 'ASML'"),
    },
)


# ---------------------------------------------------------------------------
# ALL_TOOLS — pass this to the executor LLM call
# The planner does NOT use tools; it only receives this list as text in its prompt.
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    SIMILAR_JOB_SEARCH_TOOL,
    SAVE_JOBS_TO_NOTION_TOOL,
    CREATE_NOTION_PAGE_TOOL,
    COVER_LETTER_GENERATOR_TOOL,
    SEARCH_COMPANY_INFO_TOOL,
]


# TOOL_REGISTRY lives in tools/registry.py to avoid circular imports.
# executor.py imports from there, not from here.
