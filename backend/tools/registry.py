"""
Maps tool names (as the LLM returns them in tool_call.name) to the async callables
the executor dispatches to.

Rules:
- Keys must exactly match the `name` field of the corresponding tool definition in config.py.
- Values must be async functions with signatures matching the tool's `parameters`.
- Add a new entry here whenever you add a new tool.
"""

from typing import Callable, Awaitable, Any

from tools.job_search import find_similar_jobs
from tools.notion import save_jobs_to_notion, create_notion_page
from tools.cover_letter_generator import compose_cover_letter
from tools.web_search import search_company_info

TOOL_REGISTRY: dict[str, Callable[..., Awaitable[Any]]] = {
    "find_similar_jobs":    find_similar_jobs,
    "save_jobs_to_notion":  save_jobs_to_notion,
    "create_notion_page":   create_notion_page,
    "compose_cover_letter": compose_cover_letter,
    "search_company_info":  search_company_info,
}
