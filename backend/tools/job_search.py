import logging
from services.rag import search_jobs

logger = logging.getLogger(__name__)


async def find_similar_jobs(keyword: str, location: str | None = None) -> dict:
    """
    Search for job listings using a keyword and optional location.

    Dispatches to the RAG service which queries ChromaDB for semantically
    similar jobs from the local index.

    Args:
        keyword:  Job title, skill, or technology, e.g. "ggplot2", "machine learning".
        location: City or region, e.g. "Amsterdam", "remote". None searches everywhere.

    Returns:
        {
          "status": "ok",
          "jobs": [
            {
              "title": str,
              "company": str,
              "location": str,
              "description": str,
              "url": str
            },
            ...
          ],
          "count": int
        }
        or
        {"status": "error", "message": str}
    """
    query = f"{keyword} {location or ''}".strip()
    logger.info("job_search.find_similar_jobs keyword=%s location=%s", keyword, location)

    try:
        jobs = await search_jobs(query=query, top_k=7, location=location)
        logger.info("job_search.find_similar_jobs.ok count=%s", len(jobs))
        return {"status": "ok", "jobs": jobs, "count": len(jobs)}
    except Exception as e:
        logger.error("job_search.find_similar_jobs.error error=%s", e)
        return {"status": "error", "message": str(e)}
