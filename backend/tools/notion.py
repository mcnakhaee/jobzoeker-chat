import os
import logging
from notion_client import AsyncClient
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)


def _make_client() -> AsyncClient:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN env var is not set")
    return AsyncClient(auth=token)

_client: AsyncClient | None = None

def get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# ---------------------------------------------------------------------------
# Tool functions — these are what the executor dispatches to
# Each matches exactly one tool definition in config.py
# ---------------------------------------------------------------------------

async def save_jobs_to_notion(database_name: str, jobs_summary: str) -> dict:
    """
    Save a formatted jobs summary to a Notion database.

    Looks for an existing database with `database_name` under the parent page.
    Creates one if it does not exist, then appends a new page entry.

    Args:
        database_name: Human-readable name for the Notion database (e.g. "ggplot2 Jobs – Amsterdam").
        jobs_summary:  Plain-text or markdown summary of the jobs to save.
                       The executor passes the LLM-formatted output of the job_search task.

    Returns:
        {"status": "ok", "page_id": "<id>", "database_name": "<name>"}
    """
    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
    if not parent_page_id:
        raise RuntimeError("NOTION_PARENT_PAGE_ID env var is not set")

    client = get_client()
    logger.info("notion.save_jobs database_name=%s", database_name)

    try:
        database_id = await _find_or_create_database(client, database_name, parent_page_id)

        page = await client.pages.create(
            parent={"database_id": database_id},
            properties={
                "title": {
                    "title": [{"text": {"content": database_name}}]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": jobs_summary[:2000]}  # Notion block limit
                            }
                        ]
                    }
                }
            ]
        )

        logger.info("notion.save_jobs.ok page_id=%s", page["id"])
        return {
            "status": "ok",
            "page_id": page["id"],
            "database_name": database_name,
        }

    except APIResponseError as e:
        logger.error("notion.save_jobs.error error=%s", e)
        return {"status": "error", "message": str(e)}


async def create_notion_page(title: str, content: str) -> dict:
    """
    Create a freeform Notion page under the parent page.

    Used for outputs that are not job listings — e.g. a cover letter,
    a learning plan, or a company research note.

    Args:
        title:   Page title.
        content: Page body as plain text (max ~2 000 chars per block).

    Returns:
        {"status": "ok", "page_id": "<id>", "title": "<title>"}
    """
    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
    if not parent_page_id:
        raise RuntimeError("NOTION_PARENT_PAGE_ID env var is not set")

    client = get_client()
    logger.info("notion.create_page title=%s", title)

    try:
        page = await client.pages.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            properties={
                "title": [{"type": "text", "text": {"content": title}}]
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": content[:2000]}
                            }
                        ]
                    }
                }
            ]
        )

        logger.info("notion.create_page.ok page_id=%s", page["id"])
        return {"status": "ok", "page_id": page["id"], "title": title}

    except APIResponseError as e:
        logger.error("notion.create_page.error error=%s", e)
        return {"status": "error", "message": str(e)}


async def _find_or_create_database(
    client: AsyncClient,
    database_name: str,
    parent_page_id: str,
) -> str:
    """Return the id of a database named `database_name`, creating it if needed."""
    search = await client.search(query=database_name)

    for result in search["results"]:
        if result["object"] == "database":
            db_title = result.get("title", [])
            if db_title and db_title[0]["plain_text"] == database_name:
                return result["id"]

    # Not found — create it
    db = await client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": database_name}}],
        properties={
            "title": {"title": {}},
        }
    )
    return db["id"]
