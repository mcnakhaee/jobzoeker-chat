import logging
from openai import AsyncOpenAI
import os
from services.llm import call_llm
logger = logging.getLogger(__name__)


COVER_LETTER_PROMPT = """\
You are a professional cover letter writer. Write a tailored cover letter based on
the job description and the user's profile provided below.

## Rules
1. Write exactly three paragraphs:
   - Paragraph 1: Why you are interested in this specific role and company.
   - Paragraph 2: Your two or three most relevant skills or experiences, with a
     concrete example for at least one.
   - Paragraph 3: A brief closing that invites next steps.
2. Do not use a generic opening like "I am writing to apply for...".
3. Do not invent skills, experiences, or qualifications not present in the user profile.
4. Tone: confident but not arrogant. Avoid buzzwords like "passionate", "synergy",
   "rockstar".
5. Length: 200–280 words. Do not exceed 300 words.
6. If the user profile is empty or too vague to write a specific letter, respond with:
   "I need a bit more about your background. Could you share your key skills and
   relevant experience?"
"""


IMPUT_PROMPT = """
## Job description
{job_description}

## User profile
{user_profile}

"""


# ---------------------------------------------------------------------------
# Tool function — dispatched by the executor when task.tool == "cover_letter"
# ---------------------------------------------------------------------------

async def compose_cover_letter(job_description: str, user_profile: str) -> dict:
    """
    Generate a tailored cover letter for a job.

    Args:
        job_description: Full text of the job posting.
        user_profile:    User's skills, experience, and background as free text.
                         If empty, the LLM will ask the user for more information.

    Returns:
        {"status": "ok", "letter": "<cover letter text>"}
        or
        {"status": "needs_input", "message": "<clarification request>"}
    """
    logger.info("cover_letter.compose profile_len=%s", len(user_profile))

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    user_prompt = IMPUT_PROMPT.format(
        job_description=job_description,
        user_profile=user_profile if user_profile.strip() else "(not provided)",
    )

    response = await call_llm(
    user_prompt,
    COVER_LETTER_PROMPT,
    model =  "gpt-4.1-mini",
)
        
    letter = response.get("text", "").strip()
    return letter
