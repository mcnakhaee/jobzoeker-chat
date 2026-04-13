import logging
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

COMPANY_INFO_PROMPT = """\
You are a research assistant. Provide a concise factual overview of the company
based on your training data. Cover: what the company does, approximate size, location,
tech stack or domain if known, and general employer reputation if known.
Keep the response to 3-5 sentences. If you have no reliable information about this
company, say so clearly — do not guess or invent details.
"""


async def search_company_info(company_name: str) -> dict:
    """
    Look up background information about a company.

    Uses the LLM's training knowledge to summarise what is publicly known
    about the company. This is a best-effort tool — information may be outdated
    for companies that changed significantly after the model's training cutoff.

    Args:
        company_name: Company name, e.g. "Booking.com", "ASML".

    Returns:
        {"status": "ok", "company": str, "summary": str}
        or
        {"status": "error", "message": str}
    """
    logger.info("web_search.search_company_info company=%s", company_name)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"status": "error", "message": "OPENAI_API_KEY env var is not set"}

    client = AsyncOpenAI(api_key=api_key)

    try:
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.1,
            messages=[
                {"role": "system", "content": COMPANY_INFO_PROMPT},
                {"role": "user", "content": f"Tell me about: {company_name}"},
            ],
        )
        summary = response.choices[0].message.content.strip()
        logger.info("web_search.search_company_info.ok company=%s", company_name)
        return {"status": "ok", "company": company_name, "summary": summary}

    except Exception as e:
        logger.error("web_search.search_company_info.error error=%s", e)
        return {"status": "error", "message": str(e)}
